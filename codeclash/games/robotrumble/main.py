from codeclash.constants import RESULT_TIE
from codeclash.games.abstract import CodeGame


class RobotRumbleGame(CodeGame):
    name: str = "RobotRumble"

    def __init__(self, config):
        super().__init__(config)
        assert len(config["players"]) == 2, "RobotRumble is a two-player game"
        self.run_cmd_round: str = "./rumblebot run term"

    def determine_winner(self, agents: list[any]):
        response = self.container.execute(f"tail -2 {self.round_log_path}")
        if "Blue won" in response["output"]:
            self.scoreboard.append((self.round, agents[0].name))
        elif "Red won" in response["output"]:
            self.scoreboard.append((self.round, agents[1].name))
        elif "it was a tie" in response["output"]:
            self.scoreboard.append((self.round, RESULT_TIE))

    def execute_round(self, agents: list[any]):
        args = [f"/{agent.name}/robot.py" for agent in agents]
        cmd = f"{self.run_cmd_round} {' '.join(args)} > {self.round_log_path}"
        print(f"Running command: {cmd}")
        response = self.container.execute(cmd)
        assert response["returncode"] == 0
