from codeclash.games.abstract import CodeGame
from codeclash.games.utils import copy_between_containers


class CoreWarGame(CodeGame):
    name: str = "CoreWar"
    url_gh: str = "git@github.com:emagedoc/CoreWar.git"

    def __init__(self, config):
        super().__init__(config)
        self.run_cmd_round: str = "./src/pmars"
        for arg, val in config.get("args", {}).items():
            if isinstance(val, bool):
                if val:
                    self.run_cmd_round += f" -{arg}"
            else:
                self.run_cmd_round += f" -{arg} {val}"

    def run_round(self, agents: list[any]):
        cmd = self.run_cmd_round

        args = [f"/{agent.name}/warriors/warrior.red" for agent in agents]
        cmd = f"{self.run_cmd_round} {' '.join(args)} > {self.round_log_path}"
        print(f"Running command: {cmd}")
        self.container.execute(cmd)
        print(f"Round {self.round} completed.")
