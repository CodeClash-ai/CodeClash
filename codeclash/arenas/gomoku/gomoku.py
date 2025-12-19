import re

from codeclash.agents.player import Player
from codeclash.arenas.arena import CodeArena, RoundStats
from codeclash.constants import RESULT_TIE
from codeclash.utils.environment import assert_zero_exit_code

GOMOKU_LOG = "result.log"


class GomokuArena(CodeArena):
    name: str = "Gomoku"
    submission: str = "main.py"
    description: str = """Your bot (`main.py`) controls a Gomoku player on a 15x15 board.
Players take turns placing stones. Win by connecting 5 stones in a row (horizontally, vertically, or diagonally).
Black plays first.

Your bot must implement:
    def get_move(board: list[list[int]], color: str) -> tuple[int, int]

Board representation: 0=empty, 1=black, 2=white
Color: "black" or "white"
"""

    def __init__(self, config, **kwargs):
        super().__init__(config, **kwargs)
        assert len(config["players"]) == 2, "Gomoku is a two-player game"

    def execute_round(self, agents: list[Player]) -> None:
        args = [f"/{agent.name}/{self.submission}" for agent in agents]
        cmd = (
            f"python engine.py {' '.join(args)} -r {self.game_config['sims_per_round']} > {self.log_env / GOMOKU_LOG};"
        )
        self.logger.info(f"Running game: {cmd}")
        assert_zero_exit_code(self.environment.execute(cmd))

    def get_results(self, agents: list[Player], round_num: int, stats: RoundStats):
        with open(self.log_round(round_num) / GOMOKU_LOG) as f:
            round_log = f.read()
        lines = round_log.split("FINAL_RESULTS")[-1].splitlines()

        scores = {}
        for line in lines:
            match = re.search(r"Bot\_(\d)\_main:\s(\d+)\srounds\swon", line)
            if match:
                bot_id = match.group(1)
                rounds_won = int(match.group(2))
                scores[agents[int(bot_id) - 1].name] = rounds_won

        # Handle draws
        draw_match = re.search(r"Draws:\s(\d+)", round_log)
        if draw_match:
            draws = int(draw_match.group(1))
            if draws > 0:
                scores[RESULT_TIE] = draws

        stats.winner = max(scores, key=scores.get) if scores else "unknown"
        # Check for tie (equal scores)
        if scores:
            max_score = max(scores.values())
            winners_with_max = [k for k, v in scores.items() if v == max_score and k != RESULT_TIE]
            if len(winners_with_max) > 1:
                stats.winner = RESULT_TIE

        stats.scores = scores
        for player, score in scores.items():
            if player != RESULT_TIE:
                stats.player_stats[player].score = score

    def validate_code(self, agent: Player) -> tuple[bool, str | None]:
        if self.submission not in agent.environment.execute("ls")["output"]:
            return False, f"No {self.submission} file found in the root directory"

        bot_content = agent.environment.execute(f"cat {self.submission}")["output"]

        if "def get_move(" not in bot_content:
            return (
                False,
                f"{self.submission} must define a get_move(board, color) function. "
                "See the game description for the required signature.",
            )

        return True, None
