import subprocess

from codeclash.constants import DIR_LOGS
from codeclash.games.abstract import CodeGame


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

    def setup(self):
        self.game_server = self.get_codebase()

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
        self.logger.info(f"▶️ Running {self.name} round {self.round}...")

        compiled = []
        for agent in agents:
            # Create destination directory for agent robots
            agent_robot_dir = self.game_server / "robots" / agent.name
            agent_robot_dir.mkdir(parents=True, exist_ok=True)

            for idx, cmd in enumerate(
                [
                    f"cp -r {agent.codebase}/robots/custom/* robots/{agent.name}/",
                    f"find robots/{agent.name}/ -name '*.java' -exec sed -i '' 's/custom/{agent.name}/g' {{}} +",
                    # On Linux, use the following line instead:
                    # f"find robots/{agent.name}/ -name '*.java' -exec sed -i 's/custom/{agent.name}/g' {{}} +",
                    f'javac -cp "libs/robocode.jar" robots/{agent.name}/*.java',
                ]
            ):
                self.logger.info(f"Running command: {cmd}")
                result = subprocess.run(cmd, shell=True, cwd=self.game_server)
                if idx == 2:
                    compiled.append(result.returncode == 0)

        # Create .battle file
        battle_file = (
            self.game_server / f"battles/{self.game_id}-round{self.round}.battle"
        )

        selected_robots = ",".join([f"{agent.name}.MyTank*" for agent in agents])
        with open(battle_file, "w") as f:
            f.write(
                f"""#Battle Properties
{self._get_battle_config()}
robocode.battle.selectedRobots={selected_robots}
"""
            )

        cmd = (
            f"{self.run_cmd_round} -battle {battle_file} -results {self.round_log_path}"
        )

        subprocess.run(f"touch {self.round_log_path}", shell=True, cwd=self.game_server)
        self.logger.info(f"Running command: {cmd}")

        try:
            subprocess.run(cmd, shell=True, cwd=self.game_server)
        finally:
            pass

        self.logger.info(f"✅ Completed {self.name} round {self.round}")

        # Copy round log to agents' codebases
        for agent in agents:
            copy_path = agent.codebase / DIR_LOGS / self.round_log_path.name
            copy_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.round_log_path, "rb") as src_file:
                with open(copy_path, "wb") as dest_file:
                    dest_file.write(src_file.read())
