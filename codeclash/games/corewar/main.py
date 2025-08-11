import re

from codeclash.games.abstract import CodeGame


class CoreWarGame(CodeGame):
    name: str = "CoreWar"

    def __init__(self, config):
        super().__init__(config)
        self.run_cmd_round: str = "./src/pmars"
        for arg, val in config.get("args", {}).items():
            if isinstance(val, bool):
                if val:
                    self.run_cmd_round += f" -{arg}"
            else:
                self.run_cmd_round += f" -{arg} {val}"

    def determine_winner(self, agents: list[any]):
        scores = []
        n = len(agents) * 2
        response = self.container.execute(f"tail -{n} {self.round_log_path}")
        for line in response["output"].splitlines():
            match = re.search(r".*\sby\s.*\sscores\s(\d+)", line)
            if match:
                scores.append(int(match.group(1)))
        winner = agents[scores.index(max(scores))].name
        self.scoreboard.append((self.round, winner))

    def execute_round(self, agents: list[any]):
        args = [f"/{agent.name}/warriors/warrior.red" for agent in agents]
        cmd = f"{self.run_cmd_round} {' '.join(args)} > {self.round_log_path}"
        print(f"Running command: {cmd}")
        response = self.container.execute(cmd)
        assert response["returncode"] == 0
