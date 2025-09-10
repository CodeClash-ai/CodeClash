import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from tqdm.auto import tqdm

from codeclash.agents.player import Player
from codeclash.constants import RESULT_TIE
from codeclash.games.game import CodeGame, RoundStats
from codeclash.utils.environment import assert_zero_exit_code, copy_from_container


class BattleSnakeGame(CodeGame):
    name: str = "BattleSnake"

    def __init__(self, config, *, tournament_id: str, local_output_dir: Path):
        super().__init__(config, tournament_id=tournament_id, local_output_dir=local_output_dir)
        self.run_cmd_round: str = "./battlesnake play"
        for arg, val in self.game_config.get("args", {}).items():
            if isinstance(val, bool):
                if val:
                    self.run_cmd_round += f" --{arg}"
            else:
                self.run_cmd_round += f" --{arg} {val}"

    def _wait_for_ports(self, ports: list[int], timeout: float = 3.0) -> None:
        """Wait for all ports to be available, up to timeout seconds."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            for port in ports:
                result = self.environment.execute(f"nc -z 0.0.0.0 {port}")
                if result["returncode"] != 0:
                    break
            else:
                # All ports are ready (loop completed without break)
                return

            time.sleep(0.1)

    def copy_logs_from_env(self, round_num):
        super().copy_logs_from_env(round_num)
        copy_from_container(
            container=self.environment,
            src_path=f"{self.environment.config.cwd}/game/logs",
            dest_path=self.log_local / "rounds" / str(round_num),
        )

    def get_stats(self, agents: list[Player]) -> RoundStats:
        scores = {}
        for idx in range(self.game_config["sims_per_round"]):
            ro = self.environment.execute(f"cat game/logs/sim_{idx}.jsonl")["output"]
            lines = ro.strip().split("\n")
            results = json.loads(lines[-1]) if lines else {}  # Get the last line which contains the game result
            winner = RESULT_TIE if results["isDraw"] else results["winnerName"]
            scores[winner] = scores.get(winner, 0) + 1

        winner = max(scores, key=scores.get)
        winner = RESULT_TIE if list(scores.values()).count(scores[winner]) > 1 else winner
        return RoundStats(winner=winner, scores=scores)

    def execute_round(self, agents: list[Player]):
        self.logger.debug("Starting game servers")
        cmd = []
        ports = []
        for idx, agent in enumerate(agents):
            port = 8001 + idx
            ports.append(port)
            # Surprisingly slow despite using &
            # Start server in background - just add & to run in background!
            self.environment.execute(f"PORT={port} python main.py &", cwd=f"/{agent.name}")
            cmd.append(f"--url http://0.0.0.0:{port} -n {agent.name}")

        self.logger.debug(f"Waiting for ports: {ports}")
        self._wait_for_ports(ports)
        self.logger.debug("All ports are ready")

        try:
            cmd = self.run_cmd_round + " " + " ".join(cmd)
            self.logger.info(f"Running game: {cmd}")
            self.environment.execute("rm -rf logs; mkdir logs", cwd=f"{self.environment.config.cwd}/game")

            # Use ThreadPoolExecutor for parallel execution
            with ThreadPoolExecutor(20) as executor:
                # Submit all simulations to the thread pool
                futures = [
                    executor.submit(self._run_single_simulation, cmd, idx)
                    for idx in range(self.game_config["sims_per_round"])
                ]

                # Collect results as they complete
                for future in tqdm(as_completed(futures), total=len(futures)):
                    future.result()
        finally:
            # Kill all python servers when done
            self.environment.execute("pkill -f 'python main.py' || true")

    def _run_single_simulation(self, cmd: str, idx: int) -> tuple[str, str]:
        """Run a single battlesnake simulation and return log and result outputs."""
        assert_zero_exit_code(
            self.environment.execute(
                cmd + f" -o logs/sim_{idx}.jsonl",
                cwd=f"{self.environment.config.cwd}/game",
            )
        )
