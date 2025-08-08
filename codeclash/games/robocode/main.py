import subprocess

from codeclash.games.abstract import CodeGame
from codeclash.games.utils import copy_between_containers, copy_file_to_container


class RoboCodeGame(CodeGame):
    name: str = "RoboCode"
    url_gh: str = "git@github.com:emagedoc/RoboCode.git"

    def __init__(self, config):
        super().__init__(config)
        self.run_cmd_round: str = "./robocode.sh"
        for arg, val in config.get("args", {}).items():
            if isinstance(val, bool):
                if val:
                    self.run_cmd_round += f" -{arg}"
            else:
                self.run_cmd_round += f" -{arg} {val}"

    def _get_battle_config(self) -> str:
        default_battle_config = {
            "battle": {
                "numRounds": 10,
                "gunCoolingRate": 0.1,
                "rules": {"inactivityTime": 450, "hideEnemyNames": True},
            },
            "battleField": {"width": 800, "height": 600},
        }
        user_battle_config = self.config.get("battle", {})

        def merge_dicts(default, user):
            for key, value in user.items():
                if isinstance(value, dict) and key in default:
                    merge_dicts(default[key], value)
                else:
                    default[key] = value

        merge_dicts(default_battle_config, user_battle_config)

        # Turn battle config dict into strings
        battle_lines = ["#Battle Properties"]

        def dict_to_lines(d, prefix=""):
            for key, value in d.items():
                if isinstance(value, dict):
                    dict_to_lines(value, prefix + key + ".")
                else:
                    battle_lines.append(f"robocode.{prefix}{key}={value}")

        dict_to_lines(default_battle_config)
        return "\n".join(battle_lines)

    def run_round(self, agents: list[any]):
        super().run_round(agents)

        for agent in agents:
            # Copy the agent codebase into the game codebase and compile it
            for cmd in [
                f"mkdir -p robots/{agent.name}",
                f"cp -r /{agent.name}/robots/custom/* robots/{agent.name}/",
                f"find robots/{agent.name}/ -name '*.java' -exec sed -i 's/custom/{agent.name}/g' {{}} +",
                f'javac -cp "libs/robocode.jar" robots/{agent.name}/*.java',
            ]:
                self.container.execute(cmd)

        # Create .battle file
        selected_robots = ",".join([f"{agent.name}.MyTank*" for agent in agents])
        battle_file = f"{self.game_id}-round{self.round}.battle"
        with open(battle_file, "w") as f:
            f.write(
                f"""#Battle Properties
{self._get_battle_config()}
robocode.battle.selectedRobots={selected_robots}
"""
            )
        copy_file_to_container(self.container, battle_file, f"battles/{battle_file}")
        subprocess.run(f"rm -f {battle_file}", shell=True)

        # Run battle
        cmd = (
            f"{self.run_cmd_round} -battle {battle_file} -results {self.round_log_path}"
        )
        print(f"Running command: {cmd}")
        self.container.execute(cmd)

        print(f"✅ Completed {self.name} round {self.round}")

        # Copy round log to agents' codebases
        for agent in agents:
            copy_between_containers(
                self.container,
                agent.container,
                self.round_log_path,
                f"{agent.container.config.cwd}/logs/round_{self.round}.log",
            )
            print(f"Copied round logs to {agent.name}'s codebase.")
