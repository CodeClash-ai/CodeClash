from codeclash.games.abstract import CodeGame
from codeclash.games.utils import copy_between_containers


class RobotRumbleGame(CodeGame):
    name: str = "RobotRumble"
    url_gh: str = "git@github.com:emagedoc/RobotRumble.git"

    def __init__(self, config):
        super().__init__(config)
        self.run_cmd_round: str = "./rumblebot run term"

    def run_round(self, agents: list[any]):
        super().run_round(agents)
        cmd = self.run_cmd_round

        args = [f"/{agent.name}/robot.py" for agent in agents]
        cmd = f"{self.run_cmd_round} {' '.join(args)} > {self.round_log_path}"
        print(f"Running command: {cmd}")
        self.container.execute(cmd)
        print(f"Round {self.round} completed.")
