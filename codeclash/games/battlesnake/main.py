import json
import time
from pathlib import Path

from codeclash.agents.abstract import Player
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
        self, result_output: str, agents: list[Player]
    ) -> dict[str, str]:
        self.logger.debug(f"Determining winner from result output: {result_output}")
        lines = result_output.strip().split("\n")
        # Get the last line which contains the game result
        last_line = lines[-1] if lines else ""
        self.logger.debug(f"Last line: {last_line}")
        winner = json.loads(last_line)["winnerName"]
        self.logger.debug(f"Concluding winner: {winner}")
        return {"winner": winner}

    def execute_round(self, agents: list[Player]) -> dict[str, str]:
        cmd = []
        for idx, agent in enumerate(agents):
            port = 8001 + idx
            # Start server in background - just add & to run in background!
            self.environment.execute(
                f"PORT={port} python main.py &", cwd=f"/{agent.name}"
            )
            cmd.append(f"--url http://0.0.0.0:{port} -n {agent.name}")

        time.sleep(3)  # Give servers time to start

        # Create temporary output file for results
        output_file = f"battlesnake_output_{int(time.time())}.json"
        cmd_str = " ".join(cmd) + f" -o {output_file}"
        self.logger.info(f"Running command: {self.run_cmd_round} {cmd_str}")

        try:
            response = assert_zero_exit_code(
                self.environment.execute(
                    f"{self.run_cmd_round} {cmd_str}",
                    cwd=f"{self.environment.config.cwd}/game",
                )
            )

            # Read the output file for result information
            result_response = self.environment.execute(f"cat game/{output_file}")
            result_output = result_response["output"]

            # Clean up the output file
            self.environment.execute(f"rm -f game/{output_file}")

            return {"log_output": response["output"], "result_output": result_output}
        finally:
            # Kill all python servers when done
            self.environment.execute("pkill -f 'python main.py' || true")
