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
        super().run_round(agents)
        cmd = self.run_cmd_round

        args = [f"/{agent.name}/warriors/warrior.red" for agent in agents]
        cmd = f"{self.run_cmd_round} {' '.join(args)} > {self.round_log_path}"
        print(f"Running command: {cmd}")
        self.container.execute(cmd)
        print(f"Round {self.round} completed.")

        # Copy round log to agents' codebases
        for agent in agents:
            copy_between_containers(
                self.container,
                agent.container,
                self.round_log_path,
                f"{agent.container.config.cwd}/logs/round_{self.round}.log",
            )
            print(f"Copied round log to {agent.name}'s container.")
