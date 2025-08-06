import subprocess
from pathlib import Path

from codeclash.games.abstract import CodeGame
from codeclash.games.utils import clone


class RobotRumbleGame(CodeGame):
    name: str = "RobotRumble"

    robot_file: str = "robot.py"
    url_server: str = "git@github.com:emagedoc/RobotRumble.git"
    url_starter: str = "git@github.com:emagedoc/RobotRumble-starter.git"

    def __init__(self, config):
        super().__init__(config)
        self.run_cmd_round: str = "./rumblebot run term"

    def setup(self):
        self.logger.info(f"🤖 Setting up {self.name} game environment...")
        self.server_path = clone(self.url_server)
        self.artifacts.append(self.server_path)
        self.logger.info(f"✅ Cloned {self.name} server")

    def setup_codebase(self, dest: str) -> Path:
        dest = clone(self.url_starter, dest)
        self.artifacts.append(dest)
        return dest

    def run_round(self, agents: list[any]) -> Path:
        super().run_round(agents)
        self.logger.info(f"▶️ Running {self.name} round {self.round}...")
        cmd = self.run_cmd_round

        args = []
        for _, agent in enumerate(agents):
            subprocess.run(
                f"cp -r {agent.codebase}/{self.robot_file} {agent.name}.py",
                shell=True,
                cwd=self.server_path,
            )
            args.append(f"{agent.name}.py")

        cmd = f"{self.run_cmd_round} {' '.join(args)}"
        subprocess.run(f"touch {self.round_log_path}", shell=True)
        self.logger.info(f"Running command: {cmd}")

        try:
            result = subprocess.run(
                cmd, shell=True, cwd=self.server_path, capture_output=True, text=True
            )
            with open(self.round_log_path, "w") as f:
                f.write(result.stdout)
                if result.stderr:
                    f.write("\n\nErrors:\n")
                    f.write(result.stderr)
        finally:
            pass

        self.logger.info(f"✅ Completed {self.name} round {self.round}")
        return self.round_log_path
