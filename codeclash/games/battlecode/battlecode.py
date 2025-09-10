import random
import re
from pathlib import Path
from typing import Any

from codeclash.constants import DIR_WORK, RESULT_TIE
from codeclash.games.game import CodeGame, RoundStats

BC_LOG = "sim.log"


class BattleCodeGame(CodeGame):
    name: str = "BattleCode"

    def __init__(self, config, *, tournament_id: str, local_output_dir: Path):
        super().__init__(config, tournament_id=tournament_id, local_output_dir=local_output_dir)
        assert len(config["players"]) == 2, "BattleCode is a two-player game"
        self.run_cmd_round: str = "python run.py run"
        for arg, val in self.game_config.get("args", {}).items():
            if isinstance(val, bool):
                if val:
                    self.run_cmd_round += f" --{arg}"
            else:
                self.run_cmd_round += f" --{arg} {val}"

    def get_results(self, agents: list[Any], round_num: int) -> RoundStats:
        winners = []
        with open(self.log_round(round_num) / BC_LOG) as f:
            lines = f.read().strip().split("\n")
        # Get the third-to-last line which contains the winner info
        winner_line = lines[-3] if len(lines) >= 3 else ""
        self.logger.debug(f"Winner line: {winner_line}")
        match = re.search(r"\s\((.*)\)\swins\s\(", winner_line)
        if match:
            winner_key = match.group(1)
            self.logger.debug(f"Winner key from match: {winner_key}")
            # Map A/B to actual agent names (much closer to original code)
            winner = {"A": agents[0].name, "B": agents[1].name}.get(winner_key, RESULT_TIE)
            winners.append(winner)
        else:
            winners.append(RESULT_TIE)
        return RoundStats(
            winner=max(set(winners), key=winners.count),
            scores={agent.name: winners.count(agent.name) for agent in agents},
        )

    def execute_round(self, agents: list[Any]):
        for agent in agents:
            src, dest = f"/{agent.name}/src/mysubmission/", str(DIR_WORK / "src" / agent.name)
            self.environment.execute(f"cp -r {src} {dest}")
        random.shuffle(agents)  # Start position matters in BattleCode! Shuffle to be fair.
        args = [f"--p{idx + 1}-dir src --p{idx + 1} {agent.name}" for idx, agent in enumerate(agents)]
        cmd = f"{self.run_cmd_round} {' '.join(args)}"
        self.logger.info(f"Running game: {cmd}")

        response = self.environment.execute(cmd + f" > {self.log_env / BC_LOG}")
        assert response["returncode"] == 0, response
