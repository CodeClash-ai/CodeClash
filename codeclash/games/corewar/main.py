import re

from codeclash.agents.abstract import Player
from codeclash.games.abstract import CodeGame


class CoreWarGame(CodeGame):
    name: str = "CoreWar"

    def __init__(self, config):
        super().__init__(config)
        self.run_cmd_round: str = "./src/pmars"
        for arg, val in self.game_config.get("args", {}).items():
            if isinstance(val, bool):
                if val:
                    self.run_cmd_round += f" -{arg}"
            else:
                self.run_cmd_round += f" -{arg} {val}"

    def determine_winner(self, agents: list[Player]):
        scores = []
        n = len(agents) * 2
        response = self.environment.execute(f"tail -{n} {self.round_log_path}")
        for line in response["output"].splitlines():
            match = re.search(r".*\sby\s.*\sscores\s(\d+)", line)
            if match:
                scores.append(int(match.group(1)))
        winner = agents[scores.index(max(scores))].name
        self.scoreboard.append((self.round, winner))

    def execute_round(self, agents: list[Player]):
        args = [f"/{agent.name}/warriors/warrior.red" for agent in agents]
        cmd = f"{self.run_cmd_round} {' '.join(args)} > {self.round_log_path}"
        self.logger.info(f"Running command: {cmd}")
        response = self.environment.execute(cmd)
        assert response["returncode"] == 0, response
