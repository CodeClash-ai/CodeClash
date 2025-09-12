import re
from pathlib import Path

from codeclash.agents.player import Player
from codeclash.constants import DIR_WORK, RESULT_TIE
from codeclash.games.game import CodeGame, RoundStats

BC_LOG = "sim.log"
BC_FOLDER = "mysubmission"
BC_TIE = "Reason: The winning team won arbitrarily (coin flip)."


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

    def execute_round(self, agents: list[Player]):
        for agent in agents:
            src, dest = f"/{agent.name}/src/{BC_FOLDER}/", str(DIR_WORK / "src" / agent.name)
            self.environment.execute(f"cp -r {src} {dest}")
        args = [f"--p{idx + 1}-dir src --p{idx + 1} {agent.name}" for idx, agent in enumerate(agents)]
        cmd = f"{self.run_cmd_round} {' '.join(args)}"
        self.logger.info(f"Running game: {cmd}")

        response = self.environment.execute(cmd + f" > {self.log_env / BC_LOG}")
        assert response["returncode"] == 0, response

    def get_results(self, agents: list[Player], round_num: int, stats: RoundStats):
        with open(self.log_round(round_num) / BC_LOG) as f:
            lines = f.read().strip().split("\n")
        # Get the third-to-last line which contains the winner info
        assert len(lines) >= 3, "Log file does not contain enough lines to determine winner"
        winner_line = lines[-3]
        reason_line = lines[-2]
        self.logger.debug(f"Winner line: {winner_line}")
        self.logger.debug(f"Reason line: {reason_line}")
        match = re.search(r"\s\((.*)\)\swins\s\(", winner_line)
        if match and reason_line != BC_TIE:
            winner_key = match.group(1)
            self.logger.debug(f"Winner key from match: {winner_key}")
            # Map A/B to actual agent names (much closer to original code)
            winner = {"A": agents[0].name, "B": agents[1].name}.get(winner_key, RESULT_TIE)
        else:
            winner = RESULT_TIE

        stats.winner = winner
        stats.scores = {agent.name: (1 if agent.name == winner else 0) for agent in agents}
        for player, score in stats.scores.items():
            stats.player_stats[player].score = score

    def validate_code(self, agent: Player) -> tuple[bool, str | None]:
        if BC_FOLDER not in agent.environment.execute("ls src")["output"]:
            return False, f"There should be a `src/{BC_FOLDER}/` directory"
        if "bot.py" not in agent.environment.execute(f"ls src/{BC_FOLDER}")["output"]:
            return False, f"There should be a `src/{BC_FOLDER}/bot.py` file"
        bot_content = agent.environment.execute(f"cat src/{BC_FOLDER}/bot.py")["output"].splitlines()
        if "def turn():" not in bot_content:
            return False, f"There should be a `turn()` function implemented in `src/{BC_FOLDER}/bot.py`"
        return True, None
