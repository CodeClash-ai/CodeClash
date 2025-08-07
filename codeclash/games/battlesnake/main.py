import time
from typing import Any

from codeclash.constants import DIR_WORK
from codeclash.games.abstract import CodeGame
from codeclash.games.utils import copy_between_containers


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

    def setup(self):
        self.container = self.get_container()

    def run_round(self, agents: list[Any]):
        super().run_round(agents)
        print(f"▶️ Running {self.name} round {self.round}...")

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
        self.container.execute(f"touch {self.round_log_path}")
        print(f"Running command: {cmd}")

        try:
            self.container.execute(
                cmd,
                cwd=f"{self.container.config.cwd}/game",
            )
        finally:
            # Kill all python servers when done
            self.container.execute("pkill -f 'python main.py' || true")

        print(f"Round {self.round} completed.")

        # Copy round logs to agent codebases
        for agent in agents:
            copy_between_containers(
                self.container,
                agent.container,
                self.round_log_path,
                DIR_WORK / "logs" / f"round_{self.round}.log",
            )
            print(f"Copied round logs to {agent.name}'s codebase.")
