import json
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from tqdm.auto import tqdm

from codeclash.agents.player import Player
from codeclash.constants import RESULT_TIE
from codeclash.games.game import CodeGame, RoundData, RoundStats
from codeclash.utils.environment import assert_zero_exit_code


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

    def get_stats(self, result_outputs: list[str], agents: list[Player]) -> RoundStats:
        scores = {}
        for ro in result_outputs:
            lines = ro.strip().split("\n")
            results = json.loads(lines[-1]) if lines else {}  # Get the last line which contains the game result
            winner = RESULT_TIE if results["isDraw"] else results["winnerName"]
            scores[winner] = scores.get(winner, 0) + 1

        winner = max(scores, key=scores.get)
        winner = RESULT_TIE if list(scores.values()).count(scores[winner]) > 1 else winner
        return RoundStats(winner=winner, scores=scores)

    def execute_round(self, agents: list[Player]) -> RoundData:
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
            log_outputs, result_outputs = [], []
            cmd = self.run_cmd_round + " " + " ".join(cmd)
            self.logger.info(f"Running game: {cmd}")

            # Use ThreadPoolExecutor for parallel execution
            with ThreadPoolExecutor(20) as executor:
                # Submit all simulations to the thread pool
                futures = [
                    executor.submit(self._run_single_simulation, cmd) for _ in range(self.game_config["sims_per_round"])
                ]

                # Collect results as they complete
                for future in tqdm(as_completed(futures), total=len(futures)):
                    log_output, result_output = future.result()
                    log_outputs.append(log_output)
                    result_outputs.append(result_output)

            return RoundData(logs=log_outputs, results=result_outputs)
        finally:
            # Kill all python servers when done
            self.environment.execute("pkill -f 'python main.py' || true")

    def _run_single_simulation(self, cmd: str) -> tuple[str, str]:
        """Run a single battlesnake simulation and return log and result outputs."""
        # Create temporary output file for results
        output_file = f"battlesnake_output_{uuid.uuid4().hex}.json"

        # Run game
        response = assert_zero_exit_code(
            self.environment.execute(
                cmd + f" -o {output_file}",
                cwd=f"{self.environment.config.cwd}/game",
            )
        )

        # Read the output file for result information
        result_response = self.environment.execute(f"cat game/{output_file}")
        result_output = result_response["output"]

        # Clean up the output file
        self.environment.execute(f"rm -f game/{output_file}")

        return response["output"], result_output
