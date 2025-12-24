"""Bridge Arena for CodeClash."""

import json
import shlex
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed

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
        self.run_cmd = "python3 /workspace/run_game.py"

    def validate_code(self, agent: Player) -> tuple[bool, str | None]:
        """Validate agent code has required functions."""
        if self.submission not in agent.environment.execute("ls")["output"]:
            return False, f"No {self.submission} file found in root directory"

        content = agent.environment.execute(f"cat {self.submission}")["output"]

        # Check for required function definitions
        required_functions = ["def get_bid(", "def play_card("]

        missing = []
        for func in required_functions:
            if func not in content:
                missing.append(func)

        if missing:
            return False, f"Missing required functions: {', '.join(missing)}"

        return True, None

    def _run_single_simulation(self, agents: list[Player], idx: int, cmd: str):
        """Run a single Bridge game simulation."""
        full_cmd = f"{cmd} -o {self.log_env / f'sim_{idx}.json'}"

        try:
            response = self.environment.execute(full_cmd, timeout=60)
        except subprocess.TimeoutExpired:
            self.logger.warning(f"Bridge simulation {idx} timed out")
            return ""

        if response["returncode"] != 0:
            self.logger.warning(
                f"Bridge simulation {idx} failed with exit code {response['returncode']}:\n{response['output']}"
            )
        return response["output"]

    def execute_round(self, agents: list[Player]):
        """Execute a round of Bridge games."""
        sims = self.game_config.get("sims_per_round", 10)
        self.logger.info(f"Running {sims} Bridge simulations with 4 players")

        # Build agent paths for the command
        agent_paths = []
        for agent in agents:
            agent_paths.append(f"/{agent.name}/{self.submission}")

        # Build base command
        cmd = f"{self.run_cmd} {shlex.join(agent_paths)}"

        # Run simulations in parallel
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = [
                executor.submit(self._run_single_simulation, agents, idx, f"{cmd} --seed {idx} --dealer {idx % 4}")
                for idx in range(sims)
            ]
            for future in tqdm(as_completed(futures), total=len(futures), desc="Bridge simulations"):
                future.result()

    def get_results(self, agents: list[Player], round_num: int, stats: RoundStats):
        """Parse results and determine winners."""
        # Initialize team scores
        team_scores = {"NS": 0.0, "EW": 0.0}
        games_played = 0

        # Parse all simulation logs
        for idx in range(self.game_config.get("sims_per_round", 10)):
            log_file = self.log_round(round_num) / f"sim_{idx}.json"

            if not log_file.exists():
                self.logger.warning(f"Log file {log_file} not found, skipping")
                continue

            try:
                with open(log_file) as f:
                    result = json.load(f)

                # Check for error
                if "error" in result:
                    self.logger.warning(f"Simulation {idx} had error: {result['error']}")
                    continue

                # Extract VP scores for each team
                vp_scores = result.get("normalized_score", {})
                if vp_scores:
                    team_scores["NS"] += vp_scores.get("NS", 0.0)
                    team_scores["EW"] += vp_scores.get("EW", 0.0)
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
        team_scores["NS"] /= games_played
        team_scores["EW"] /= games_played

        # Determine winning team
        if abs(team_scores["NS"] - team_scores["EW"]) < 0.01:  # Tie threshold
            stats.winner = RESULT_TIE
        elif team_scores["NS"] > team_scores["EW"]:
            stats.winner = f"{agents[0].name}/{agents[2].name}"
        else:
            stats.winner = f"{agents[1].name}/{agents[3].name}"

        # Assign scores to individual players based on their team
        for position, agent in enumerate(agents):
            team = "NS" if position % 2 == 0 else "EW"
            score = team_scores[team]
            stats.scores[agent.name] = score
            stats.player_stats[agent.name].score = score

        self.logger.info(
            f"Round {round_num} results - NS: {team_scores['NS']:.3f}, "
            f"EW: {team_scores['EW']:.3f}, Winner: {stats.winner}"
        )
