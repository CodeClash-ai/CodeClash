import subprocess
import time
from pathlib import Path

from codeclash.agents.abstract import Player
from codeclash.constants import OUTPUTS_LOGS, OUTPUTS_RESULTS
from codeclash.games.abstract import CodeGame
from codeclash.utils.environment import copy_to_container


class RoboCodeGame(CodeGame):
    name: str = "RoboCode"

    def __init__(self, config, *, tournament_id: str, local_output_dir: Path):
        super().__init__(
            config, tournament_id=tournament_id, local_output_dir=local_output_dir
        )
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

    def determine_winner(
        self, result_outputs: list[str], agents: list[Player]
    ) -> dict[str, str]:
        result_output = result_outputs[0]  # Get the first (and only) element
        self.logger.debug(f"Determining winner from result output: {result_output}")
        lines = result_output.strip().split("\n")
        # Get the second line which contains the winner info (closer to original)
        winner_line = lines[2] if len(lines) >= 3 else ""
        self.logger.debug(f"Winner line: {winner_line}")
        if winner_line:
            winner = winner_line.split()[1].rsplit(".", 1)[0]
            self.logger.debug(f"Concluding winner: {winner}")
            return {"winner": winner}
        else:
            self.logger.debug("No winner line found, returning unknown")
            return {"winner": "unknown"}

    def execute_round(self, agents: list[Player]) -> dict[str, list[str]]:
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
        with open(battle_file, "w") as f:
            f.write(
                f"""#Battle Properties
{self._get_battle_config()}
robocode.battle.selectedRobots={selected_robots}
"""
            )
        copy_to_container(self.environment, battle_file, f"battles/{battle_file}")
        subprocess.run(f"rm -f {battle_file}", shell=True)

        # Run battle with results output to file
        results_file = f"results_{int(time.time())}.txt"
        cmd = f"{self.run_cmd_round} -battle {battle_file} -results {results_file}"
        self.logger.info(f"Running command: {cmd}")
        response = self.environment.execute(cmd)
        assert response["returncode"] == 0, response

        # Read the results file to get result output
        cat_response = self.environment.execute(f"cat {results_file}")
        result_output = cat_response["output"]

        # Clean up the results file
        self.environment.execute(f"rm -f {results_file}")

        return {OUTPUTS_LOGS: [response["output"]], OUTPUTS_RESULTS: [result_output]}
