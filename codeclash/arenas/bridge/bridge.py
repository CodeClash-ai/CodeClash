"""Bridge Arena for CodeClash."""

import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from tqdm.auto import tqdm

from codeclash.agents.player import Player
from codeclash.arenas.arena import CodeArena, RoundStats
from codeclash.constants import RESULT_TIE


class BridgeArena(CodeArena):
    name: str = "Bridge"
    submission: str = "bridge_agent.py"
    description: str = """Bridge is a 4-player trick-taking card game played in teams.

Teams: North/South (positions 0/2) vs East/West (positions 1/3)

Your bot (bridge_agent.py) must implement these functions:
- get_bid(game_state) -> str: Make bidding decisions, return bid string like "1H", "2NT", "PASS"
- play_card(game_state) -> str: Play a card, return card string like "AS", "7H"

game_state is a dict containing:
- position: Your position (0=North, 1=East, 2=South, 3=West)
- hand: List of cards in your hand (e.g., ["AS", "KH", "7D"])
- bids: List of previous bids
- legal_bids: List of legal bids you can make (during bidding)
- legal_cards: List of legal cards you can play (during playing)
- current_trick: Cards played so far in current trick
- contract: The current contract (if bidding is complete)
"""
    default_args: dict = {
        "sims_per_round": 10,
    }

    def __init__(self, config, **kwargs):
        # Validate player count before initializing (to avoid Docker build on invalid config)
        num_players = len(config.get("players", []))
        if num_players != 4:
            raise ValueError(f"Bridge requires exactly 4 players, got {num_players}")
        super().__init__(config, **kwargs)

    def validate_code(self, agent: Player) -> tuple[bool, str | None]:
        """Validate agent code has required functions."""
        if self.submission not in agent.environment.execute("ls")["output"]:
            return False, f"No {self.submission} file found in root directory"

        content = agent.environment.execute(f"cat {self.submission}")["output"]

        # Check for required function definitions
        required_functions = [
            "def get_bid(",
            "def play_card("
        ]

        missing = []
        for func in required_functions:
            if func not in content:
                missing.append(func)

        if missing:
            return False, f"Missing required functions: {', '.join(missing)}"

        return True, None

    def _run_single_simulation(self, agents: list[Player], idx: int):
        """Run a single Bridge game simulation."""
        game_server_path = str(Path(self.environment.config.cwd) / "game_server")
        try:
            # Import BridgeGame from game_server (cloned from CodeClash-ai/Bridge repo)
            sys.path.insert(0, game_server_path)
            from game import BridgeGame

            # Create game with random seed for reproducibility
            game = BridgeGame(seed=idx, dealer=idx % 4)

            # Add players at positions 0-3 (North, East, South, West)
            for position, agent in enumerate(agents):
                game.add_player(position, agent.name)

            # Start game (deals cards)
            if not game.start_game():
                self.logger.error(f"Simulation {idx}: Failed to start game")
                return

            # Import agent modules dynamically
            agent_modules = []
            for agent in agents:
                agent_path = Path(agent.environment.config.cwd) / self.submission
                spec = __import__(
                    'importlib.util'
                ).util.spec_from_file_location(f"agent_{agent.name}", agent_path)
                module = __import__('importlib.util').util.module_from_spec(spec)
                spec.loader.exec_module(module)
                agent_modules.append(module)

            # Bidding phase
            while game.phase == 'bidding':
                current_pos = game.current_player
                state = game.get_state(current_pos)

                # Prepare game_state for agent
                agent_state = {
                    'position': current_pos,
                    'hand': state.get('hand', game.hands.get(current_pos, [])),
                    'bids': state['bids'],
                    'legal_bids': game.get_legal_bids(current_pos),
                    'dealer': state['dealer'],
                    'vulnerability': state['vulnerability'],
                }

                # Get bid from agent
                try:
                    bid = agent_modules[current_pos].get_bid(agent_state)
                except Exception as e:
                    self.logger.error(f"Simulation {idx}: Agent {agents[current_pos].name} error in get_bid: {e}")
                    bid = "PASS"

                # Make bid
                if not game.make_bid(current_pos, bid):
                    self.logger.warning(
                        f"Simulation {idx}: Invalid bid '{bid}' from {agents[current_pos].name}, defaulting to PASS"
                    )
                    game.make_bid(current_pos, "PASS")

            # Playing phase
            while game.phase == 'playing':
                current_pos = game.current_player
                state = game.get_state(current_pos)

                # Prepare game_state for agent
                agent_state = {
                    'position': current_pos,
                    'hand': state.get('hand', game.hands.get(current_pos, [])),
                    'current_trick': state['current_trick'],
                    'legal_cards': game.get_legal_cards(current_pos),
                    'contract': state['contract'],
                    'tricks_won': state['tricks_won'],
                }

                # Get card from agent
                try:
                    card = agent_modules[current_pos].play_card(agent_state)
                except Exception as e:
                    self.logger.error(f"Simulation {idx}: Agent {agents[current_pos].name} error in play_card: {e}")
                    legal = game.get_legal_cards(current_pos)
                    card = legal[0] if legal else "AS"

                # Play card
                if not game.play_card(current_pos, card):
                    self.logger.warning(
                        f"Simulation {idx}: Invalid card '{card}' from {agents[current_pos].name}, using first legal card"
                    )
                    legal = game.get_legal_cards(current_pos)
                    if legal:
                        game.play_card(current_pos, legal[0])

            # Save result to JSON log
            result = game.get_result()
            log_file = self.log_env / f"sim_{idx}.json"
            with open(log_file, 'w') as f:
                json.dump(result, f, indent=2)

        except Exception as e:
            self.logger.error(f"Simulation {idx} failed with error: {e}")
        finally:
            # Clean up sys.path
            if game_server_path in sys.path:
                sys.path.remove(game_server_path)

    def execute_round(self, agents: list[Player]):
        """Execute a round of Bridge games."""
        sims = self.game_config['sims_per_round']
        self.logger.info(f"Running {sims} Bridge simulations with 4 players")

        # Run simulations in parallel
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [
                executor.submit(self._run_single_simulation, agents, idx)
                for idx in range(sims)
            ]
            for future in tqdm(as_completed(futures), total=len(futures), desc="Bridge simulations"):
                future.result()

    def get_results(self, agents: list[Player], round_num: int, stats: RoundStats):
        """Parse results and determine winners."""
        # Initialize team scores
        team_scores = {'NS': 0.0, 'EW': 0.0}
        games_played = 0

        # Parse all simulation logs
        for idx in range(self.game_config['sims_per_round']):
            log_file = self.log_round(round_num) / f"sim_{idx}.json"

            if not log_file.exists():
                self.logger.warning(f"Log file {log_file} not found, skipping")
                continue

            try:
                with open(log_file) as f:
                    result = json.load(f)

                # Extract VP scores for each team
                vp_scores = result.get('normalized_score', {})
                if vp_scores:
                    team_scores['NS'] += vp_scores.get('NS', 0.0)
                    team_scores['EW'] += vp_scores.get('EW', 0.0)
                    games_played += 1
            except (json.JSONDecodeError, KeyError) as e:
                self.logger.warning(f"Error parsing {log_file}: {e}")
                continue

        if games_played == 0:
            self.logger.error("No valid game results found")
            stats.winner = RESULT_TIE
            for agent in agents:
                stats.scores[agent.name] = 0.0
                stats.player_stats[agent.name].score = 0.0
            return

        # Average the scores
        team_scores['NS'] /= games_played
        team_scores['EW'] /= games_played

        # Determine winning team
        if abs(team_scores['NS'] - team_scores['EW']) < 0.01:  # Tie threshold
            stats.winner = RESULT_TIE
        elif team_scores['NS'] > team_scores['EW']:
            stats.winner = f"{agents[0].name}/{agents[2].name}"
        else:
            stats.winner = f"{agents[1].name}/{agents[3].name}"

        # Assign scores to individual players based on their team
        for position, agent in enumerate(agents):
            team = 'NS' if position % 2 == 0 else 'EW'
            score = team_scores[team]
            stats.scores[agent.name] = score
            stats.player_stats[agent.name].score = score

        self.logger.info(
            f"Round {round_num} results - NS: {team_scores['NS']:.3f}, "
            f"EW: {team_scores['EW']:.3f}, Winner: {stats.winner}"
        )
