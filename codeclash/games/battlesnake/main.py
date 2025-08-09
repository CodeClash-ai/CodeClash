import re
import time
from typing import Any

from codeclash.games.abstract import CodeGame


class BattleSnakeGame(CodeGame):
    name: str = "BattleSnake"
    url_gh: str = "git@github.com:emagedoc/BattleSnake.git"

    def __init__(self, config):
        super().__init__(config)
        self.run_cmd_round: str = "./battlesnake play"
        for arg, val in config.get("args", {}).items():
            if isinstance(val, bool):
                if val:
                    self.run_cmd_round += f" --{arg}"
            else:
                self.run_cmd_round += f" --{arg} {val}"

    def execute_round(self, agents: list[Any]):
        cmd = self.run_cmd_round

        for idx, agent in enumerate(agents):
            port = 8001 + idx
            # Start server in background - just add & to run in background!
            self.container.execute(
                f"PORT={port} python main.py &", cwd=f"/{agent.name}"
            )
            cmd += f" --url http://0.0.0.0:{port} -n {agent.name}"

        time.sleep(3)  # Give servers time to start

        cmd += f" -o {self.round_log_path}"
        print(f"Running command: {cmd}")

        try:
            result = self.container.execute(
                cmd,
                cwd=f"{self.container.config.cwd}/game",
            )
            assert result["returncode"] == 0
            winner = re.search(r"\.\s(.*)\swas\sthe\swinner\.", result["output"]).group(
                1
            )
            self.scoreboard.append((self.round, winner))
        finally:
            # Kill all python servers when done
            self.container.execute("pkill -f 'python main.py' || true")

        print(f"Round {self.round} completed.")
