import re
from pathlib import Path
from typing import Any

from tqdm.auto import tqdm

from codeclash.constants import DIR_WORK, RESULT_TIE
from codeclash.games.game import CodeGame, RoundStats
from codeclash.utils.environment import copy_from_container


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

    def copy_logs_from_env(self, round_num):
        super().copy_logs_from_env(round_num)
        copy_from_container(
            container=self.environment,
            src_path="/testbed/logs",
            dest_path=self.log_local / "rounds" / str(round_num),
        )

    def get_stats(self, agents: list[Any]) -> RoundStats:
        winners = []
        for sim_file in [f"logs/sim_{idx}.log" for idx in range(self.game_config["sims_per_round"])]:
            ro = self.environment.execute(f"cat {sim_file}")["output"]
            lines = ro.strip().split("\n")
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
        args = [f"--p{idx + 1}-dir src --p{idx + 1} {agent.name}" for idx, agent in enumerate(agents)]
        cmd = f"{self.run_cmd_round} {' '.join(args)}"
        self.logger.info(f"Running game: {cmd}")

        self.environment.execute("rm -rf logs; mkdir logs")
        for idx in tqdm(range(self.game_config["sims_per_round"])):
            response = self.environment.execute(cmd + f" > logs/sim_{idx}.log")
            assert response["returncode"] == 0, response
