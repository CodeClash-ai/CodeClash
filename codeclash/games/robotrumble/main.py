import subprocess
from pathlib import Path

from codeclash.constants import LOGS_DIR
from codeclash.games.abstract import CodeGame


class RobotRumbleGame(CodeGame):
    name: str = "RobotRumble"
    url_gh: str = "git@github.com:emagedoc/RobotRumble.git"

    def __init__(self, config):
        super().__init__(config)
        self.run_cmd_round: str = "./rumblebot run term"

    def setup(self):
        self.game_server = self.get_codebase()

    def run_round(self, agents: list[any]):
        super().run_round(agents)
        self.logger.info(f"▶️ Running {self.name} round {self.round}...")
        cmd = self.run_cmd_round

        args = []
        for _, agent in enumerate(agents):
            subprocess.run(
                f"cp -r {agent.codebase}/robot.py {agent.name}.py",
                shell=True,
                cwd=self.game_server,
            )
            args.append(f"{agent.name}.py")

        cmd = f"{self.run_cmd_round} {' '.join(args)}"
        subprocess.run(f"touch {self.round_log_path}", shell=True)
        self.logger.info(f"Running command: {cmd}")

        try:
            result = subprocess.run(
                cmd, shell=True, cwd=self.game_server, capture_output=True, text=True
            )
            with open(self.round_log_path, "w") as f:
                f.write(result.stdout)
                if result.stderr:
                    f.write("\n\nErrors:\n")
                    f.write(result.stderr)
        finally:
            pass

        self.logger.info(f"✅ Completed {self.name} round {self.round}")

        # Copy round log to agents' codebases
        for agent in agents:
            copy_path = agent.codebase / LOGS_DIR / self.round_log_path.name
            copy_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.round_log_path, "rb") as src_file:
                with open(copy_path, "wb") as dest_file:
                    dest_file.write(src_file.read())
