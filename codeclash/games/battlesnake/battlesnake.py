import json
import random
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from tqdm.auto import tqdm

from codeclash.agents.player import Player
from codeclash.constants import RESULT_TIE
from codeclash.games.game import CodeGame, RoundStats


class BattleSnakeGame(CodeGame):
    name: str = "BattleSnake"

    def __init__(self, config, **kwargs):
        super().__init__(config, **kwargs)
        self.run_cmd_round: str = "./battlesnake play"
        for arg, val in self.game_config.get("args", {}).items():
            if isinstance(val, bool):
                if val:
                    self.run_cmd_round += f" --{arg}"
            else:
                self.run_cmd_round += f" --{arg} {val}"
        self._failed_to_start_player = []

    def _wait_for_ports(self, requested_ports: list[int], timeout: float = 60.0) -> list[int]:
        """Wait for ports to be served, up to timeout seconds.

        Returns:
            List of ports that are actually served after timeout.
        """
        start_time = time.time()
        available_ports = set()

        while time.time() - start_time < timeout:
            for port in set(requested_ports) - available_ports:
                result = self.environment.execute(f"wget -S --spider --timeout=1 http://localhost:{port}/ 2>&1")
                if result["returncode"] == 0 or "200 OK" in result["output"] or "HTTP/" in result["output"]:
                    available_ports.add(port)

            if len(available_ports) == len(requested_ports):
                return list(available_ports)

            time.sleep(0.1)

        return list(available_ports)

    def _run_single_simulation(self, player2port: dict[str, int], idx: int) -> str:
        """Run a single battlesnake simulation and return log and result outputs."""
        # Build command with player URLs in randomized order
        players = list(player2port.items())
        random.shuffle(players)

        cmd_args = []
        for player_name, port in players:
            cmd_args.append(f"--url http://0.0.0.0:{port} -n {player_name}")

        cmd = self.run_cmd_round + " " + " ".join(cmd_args) + f" -o {self.log_env / f'sim_{idx}.jsonl'}"

        # https://github.com/emagedoc/CodeClash/issues/62 (timeouts)
        try:
            output = self.environment.execute(
                cmd,
                cwd=f"{self.environment.config.cwd}/game",
                timeout=120,  # this should rarely ever reach this timeout
            )
        except subprocess.TimeoutError:
            self.logger.warning(f"Battlesnake simulation timed out: {cmd}")
            return ""
        if output["returncode"] != 0:
            self.logger.warning(
                f"Battlesnake simulation failed with exit code {output['returncode']}:\n{output['output']}"
            )
        return output["output"]

    def execute_round(self, agents: list[Player]):
        self._failed_to_start_player = []
        assert len(agents) > 1, "Battlesnake requires at least two players"
        self.logger.debug("Starting game servers")
        player2port = {}
        for idx, agent in enumerate(agents):
            port = 8001 + idx
            player2port[agent.name] = port
            # Surprisingly slow despite using &
            # Start server in background - just add & to run in background!
            self.environment.execute(f"PORT={port} python main.py &", cwd=f"/{agent.name}")

        self.logger.debug(f"Waiting for ports: {player2port}")
        available_ports = self._wait_for_ports(list(player2port.values()))

        if not available_ports:
            raise RuntimeError("All games failed to start")

        if len(available_ports) == 1:
            missing_ports = set(player2port.values()) - set(available_ports)
            missing_player = next(player for player, port in player2port.items() if port in missing_ports)
            self.logger.warning(f"Player {missing_player} failed to start")
            self._failed_to_start_player.append(missing_player)
            return

        if len(available_ports) < len(agents):
            raise RuntimeError(f"Only {len(available_ports)} players started: {available_ports}")

        self.logger.debug("All ports are ready")

        try:
            self.logger.info(f"Running game with players: {list(player2port.keys())}")

            # Use ThreadPoolExecutor for parallel execution
            with ThreadPoolExecutor(20) as executor:
                # Submit all simulations to the thread pool
                futures = [
                    executor.submit(self._run_single_simulation, player2port, idx)
                    for idx in range(self.game_config["sims_per_round"])
                ]

                # Collect results as they complete
                for future in tqdm(as_completed(futures), total=len(futures)):
                    future.result()
        finally:
            # Kill all python servers when done
            self.environment.execute("pkill -f 'python main.py' || true")

    def get_results(self, agents: list[Player], round_num: int, stats: RoundStats):
        scores = {}
        available_players = [player.name for player in agents if player.name not in self._failed_to_start_player]
        if len(available_players) > 1:
            # We ran the game
            for idx in range(self.game_config["sims_per_round"]):
                try:
                    with open(self.log_round(round_num) / f"sim_{idx}.jsonl") as f:
                        lines = f.read().strip().split("\n")
                        results = json.loads(lines[-1])  # Get the last line which contains the game result
                        winner = RESULT_TIE if results["isDraw"] else results["winnerName"]
                        scores[winner] = scores.get(winner, 0) + 1
                except FileNotFoundError:
                    self.logger.warning(f"Simulation {idx} not found, skipping")
                except json.JSONDecodeError:
                    self.logger.warning(f"Simulation {idx} is not a valid JSON, skipping")
        else:
            self.logger.warning(f"Only one player ({available_players[0]}) started, giving them the win")
            # We didn't run a game, so we just give the one player the win
            available_player = available_players[0]
            scores = {available_player: self.game_config["sims_per_round"]}

        winner = max(scores, key=scores.get)
        winner = RESULT_TIE if list(scores.values()).count(scores[winner]) > 1 else winner
        stats.winner = winner
        stats.scores = scores
        for player, score in scores.items():
            if player != RESULT_TIE:
                stats.player_stats[player].score = score

    def validate_code(self, agent: Player) -> tuple[bool, str | None]:
        if "main.py" not in agent.environment.execute("ls")["output"]:
            return False, "No main.py file found in the root directory"
        bot_content = agent.environment.execute("cat main.py")["output"].splitlines()
        error_msg = []
        for func in [
            "def info(",
            "def start(",
            "def end(",
            "def move(",
        ]:
            if func not in bot_content:
                error_msg.append(f"There should be a `{func}` function implemented in `main.py`")
        if len(error_msg) > 0:
            return False, "\n".join(error_msg + ["Don't change the function signatures!"])
        return True, None
