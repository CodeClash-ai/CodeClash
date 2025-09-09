import re
import time
from pathlib import Path

from codeclash.agents.player import Player
from codeclash.games.game import CodeGame, RoundStats
from codeclash.utils.environment import assert_zero_exit_code, copy_from_container, create_file_in_container


class RoboCodeGame(CodeGame):
    name: str = "RoboCode"

    def __init__(self, config, *, tournament_id: str, local_output_dir: Path):
        super().__init__(config, tournament_id=tournament_id, local_output_dir=local_output_dir)
        self.run_cmd_round: str = "./robocode.sh"
        for arg, val in self.game_config.get("args", {}).items():
            if isinstance(val, bool):
                if val:
                    self.run_cmd_round += f" -{arg}"
            else:
                self.run_cmd_round += f" -{arg} {val}"

    def _get_battle_config(self) -> str:
        default_battle_config = {
            "battle": {
                "numRounds": self.game_config.get("sims_per_round", 100),
                "gunCoolingRate": 0.1,
                "rules": {"inactivityTime": 450, "hideEnemyNames": True},
            },
            "battleField": {"width": 800, "height": 600},
        }
        user_battle_config = self.game_config.get("battle", {})

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

    def copy_logs_from_env(self, round_num: int) -> None:
        super().copy_logs_from_env(round_num)
        copy_from_container(
            container=self.environment,
            src_path="/testbed/logs",
            dest_path=self.log_local / "rounds" / str(round_num),
        )

    def get_stats(self, agents: list[Player]) -> RoundStats:
        result_output = self.environment.execute("cat logs/results.txt")["output"]
        print(result_output)
        lines = result_output.strip().split("\n")

        scores = {}
        for line in lines:
            line = line.strip()
            if not re.match(r"^\d", line):
                continue
            match = re.search(r"(\d+)\S+\:\s(\S+)\s+(\d+)", line)
            if match:
                player = match.group(2).rsplit(".", 1)[0]
                score = int(match.group(3))
                scores[player] = score
                if int(match.group(1)) == 1:
                    winner = player

        return RoundStats(winner=winner, scores=scores, details={"stdout": "\n".join(lines)})

    def execute_round(self, agents: list[Player]):
        for agent in agents:
            # Copy the agent codebase into the game codebase and compile it
            for cmd in [
                f"mkdir -p robots/{agent.name}",
                f"cp -r /{agent.name}/robots/custom/* robots/{agent.name}/",
                f"find robots/{agent.name}/ -name '*.java' -exec sed -i 's/custom/{agent.name}/g' {{}} +",
                f'javac -cp "libs/robocode.jar" robots/{agent.name}/*.java',
            ]:
                self.environment.execute(cmd)

        # Create .battle file
        selected_robots = ",".join([f"{agent.name}.MyTank*" for agent in agents])
        # Use timestamp for unique battle file name since rounds are managed by tournament
        battle_file = f"{self.game_id}-battle{int(time.time())}.battle"
        battle_content = f"""#Battle Properties
{self._get_battle_config()}
robocode.battle.selectedRobots={selected_robots}
"""
        create_file_in_container(self.environment, content=battle_content, dest_path=f"battles/{battle_file}")

        # Run battle with results output to file
        cmd = f"mkdir -p logs; {self.run_cmd_round} -battle {battle_file} -results logs/results.txt"
        self.logger.info(f"Running game: {cmd}")
        assert_zero_exit_code(self.environment.execute(cmd))
