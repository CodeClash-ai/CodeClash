import json
import time

from codeclash.agents.abstract import Player
from codeclash.games.abstract import CodeGame
from codeclash.utils.environment import assert_zero_exit_code


class BattleSnakeGame(CodeGame):
    name: str = "BattleSnake"

    def __init__(self, config):
        super().__init__(config)
        self.run_cmd_round: str = "./battlesnake play"
        for arg, val in config.get("args", {}).items():
            if isinstance(val, bool):
                if val:
                    self.run_cmd_round += f" --{arg}"
            else:
                self.run_cmd_round += f" --{arg} {val}"

    def determine_winner(self, agents: list[Player]):
        response = assert_zero_exit_code(
            self.environment.execute(f"tail -1 {self.round_log_path}")
        )
        winner = json.loads(response["output"].strip("\n"))["winnerName"]
        self.scoreboard.append((self.round, winner))

    def execute_round(self, agents: list[Player]):
        cmd = []
        for idx, agent in enumerate(agents):
            port = 8001 + idx
            # Start server in background - just add & to run in background!
            self.environment.execute(
                f"PORT={port} python main.py &", cwd=f"/{agent.name}"
            )
            cmd.append(f"--url http://0.0.0.0:{port} -n {agent.name}")

        time.sleep(3)  # Give servers time to start

        cmd.append(f"-o {self.round_log_path}")
        cmd = " ".join(cmd)
        print(f"Running command: {cmd}")

        # todo: should probably keep output somewhere?
        try:
            assert_zero_exit_code(
                self.environment.execute(
                    f"{self.run_cmd_round} {cmd}",
                    cwd=f"{self.environment.config.cwd}/game",
                )
            )
        finally:
            # Kill all python servers when done
            self.environment.execute("pkill -f 'python main.py' || true")
