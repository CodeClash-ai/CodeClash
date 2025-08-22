import re
from typing import Any

from codeclash.constants import DIR_WORK, RESULT_TIE
from codeclash.games.abstract import CodeGame


class BattleCodeGame(CodeGame):
    name: str = "BattleCode"

    def __init__(self, config, **kwargs):
        super().__init__(config, **kwargs)
        assert len(config["players"]) == 2, "BattleCode is a two-player game"
        self.run_cmd_round: str = "python run.py run"
        for arg, val in self.game_config.get("args", {}).items():
            if isinstance(val, bool):
                if val:
                    self.run_cmd_round += f" --{arg}"
            else:
                self.run_cmd_round += f" --{arg} {val}"

    def determine_winner(self, agents: list[Any]):
        response = self.environment.execute(f"tail -3 {self.round_log_path} | head -1")
        winner = re.search(r"\s\((.*)\)\swins\s\(", response["output"]).group(1)
        winner = {"A": agents[0].name, "B": agents[1].name}.get(winner, RESULT_TIE)
        self.scoreboard.append((self.round, winner))

    def execute_round(self, agents: list[Any]):
        for agent in agents:
            src, dest = f"/{agent.name}/src/mysubmission/", str(
                DIR_WORK / "src" / agent.name
            )
            self.environment.execute(f"cp -r {src} {dest}")
        args = [
            f"--p{idx+1}-dir src --p{idx+1} {agent.name}"
            for idx, agent in enumerate(agents)
        ]
        cmd = f"{self.run_cmd_round} {' '.join(args)} > {self.round_log_path}"
        self.logger.info(f"Running command: {cmd}")
        response = self.environment.execute(cmd)
        assert response["returncode"] == 0, response
