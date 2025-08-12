from typing import Any

from codeclash.games.abstract import CodeGame


class BattleCodeGame(CodeGame):
    name: str = "BattleCode"

    def __init__(self, config):
        super().__init__(config)
        assert len(config["players"]) == 2, "BattleCode is a two-player game"
        self.run_cmd_round: str = "python run.py run"
    
    def determine_winner(self, agents: list[Any]):
        response = self.environment.execute(f"tail -2 {self.round_log_path}")
        self.scoreboard.append((self.round, "BLAH")) # TODO
    
    def execute_round(self, agents: list[Any]):
        args = [f"/{agent.name}/src/" for agent in agents]
        cmd = f"{self.run_cmd_round}" # TODO
        response = self.environment.execute(cmd)
        assert response["returncode"] == 0, response