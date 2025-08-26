import json
import time
from pathlib import Path

from codeclash.agents.abstract import Player
from codeclash.constants import OUTPUTS_LOGS, OUTPUTS_RESULTS
from codeclash.games.abstract import CodeGame
from codeclash.utils.environment import assert_zero_exit_code


class BattleSnakeGame(CodeGame):
    name: str = "BattleSnake"

    def __init__(self, config, *, tournament_id: str, local_output_dir: Path):
        super().__init__(
            config, tournament_id=tournament_id, local_output_dir=local_output_dir
        )
        self.run_cmd_round: str = "./battlesnake play"
        for arg, val in self.game_config.get("args", {}).items():
            if isinstance(val, bool):
                if val:
                    self.run_cmd_round += f" --{arg}"
            else:
                self.run_cmd_round += f" --{arg} {val}"

    def determine_winner(
        self, result_outputs: list[str], agents: list[Player]
    ) -> dict[str, str]:
        winners = []
        for ro in result_outputs:
            lines = ro.strip().split("\n")
            # Get the last line which contains the game result
            last_line = lines[-1] if lines else ""
            self.logger.debug(f"Last line: {last_line}")
            winner = json.loads(last_line)["winnerName"]
            winners.append(winner)
        winner = max(set(winners), key=winners.count)
        return {"winner": winner}

    def execute_round(self, agents: list[Player]) -> dict[str, list[str]]:
        cmd = []
        for idx, agent in enumerate(agents):
            port = 8001 + idx
            # Start server in background - just add & to run in background!
            self.environment.execute(
                f"PORT={port} python main.py &", cwd=f"/{agent.name}"
            )
            cmd.append(f"--url http://0.0.0.0:{port} -n {agent.name}")

        time.sleep(3)  # Give servers time to start

        try:
            log_outputs, result_outputs = [], []
            for idx in range(self.game_config["sims_per_round"]):
                # Create temporary output file for results
                output_file = f"battlesnake_output_{idx}_{int(time.time())}.json"
                cmd_str = " ".join(cmd) + f" -o {output_file}"
                self.logger.info(f"Running command: {self.run_cmd_round} {cmd_str}")

                response = assert_zero_exit_code(
                    self.environment.execute(
                        f"{self.run_cmd_round} {cmd_str}",
                        cwd=f"{self.environment.config.cwd}/game",
                    )
                )

                # Read the output file for result information
                result_response = self.environment.execute(f"cat game/{output_file}")
                result_output = result_response["output"]
                log_outputs.append(response["output"])
                result_outputs.append(result_output)

                # Clean up the output file
                self.environment.execute(f"rm -f game/{output_file}")

                time.sleep(0.1)

            return {OUTPUTS_LOGS: log_outputs, OUTPUTS_RESULTS: result_outputs}
        finally:
            # Kill all python servers when done
            self.environment.execute("pkill -f 'python main.py' || true")
