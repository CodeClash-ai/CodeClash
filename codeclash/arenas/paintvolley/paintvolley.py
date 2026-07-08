import re

from codeclash.agents.player import Player
from codeclash.arenas.arena import CodeArena, RoundStats
from codeclash.constants import RESULT_TIE
from codeclash.utils.environment import assert_zero_exit_code

PAINTVOLLEY_LOG = "result.log"


class PaintVolleyArena(CodeArena):
    name: str = "PaintVolley"
    submission: str = "main.py"
    description: str = """Your bot (`main.py`) controls a helmet-wearing character in PaintVolley, a
territory-painting game. Characters patrol the bottom of a rectangular field while balls fly around
bouncing off all four walls (no gravity). Each tick, every ball paints the tile it is over in its own
color. Balls start neutral and paint nothing; when a ball lands on your helmet it turns your color and
bounces upward, so it then paints for you until an opponent steals it. The helmet-contact point sets
the exit angle (center = straight up, edges = steep), so you aim where paint goes. Most tiles owned
when the tick budget runs out wins.

Your bot must implement:
    def get_action(obs: dict) -> str

Return one of: "LEFT", "RIGHT", "JUMP", "JUMP_LEFT", "JUMP_RIGHT", "NONE".
Invalid/crashing/slow actions are treated as "NONE" for that tick.

`obs` is the full deterministic state each tick: obs["tick"]/["max_ticks"], obs["field"]
(width/height/cols/rows), obs["rules"] (every physics constant, so you can forward-simulate),
obs["you"] (id/color), obs["players"] (id, color, x, y, on_ground), obs["balls"]
(x, y, vx, vy, color where color is the owner id or -1 for neutral), obs["tiles"]
(tiles[row][col] = owner id or -1), and obs["scores"]. Origin is top-left; up is -y.
"""

    def __init__(self, config, **kwargs):
        super().__init__(config, **kwargs)
        assert len(config["players"]) >= 2, "PaintVolley needs at least two players"

    def execute_round(self, agents: list[Player]) -> None:
        args = [f"/{agent.name}/{self.submission}" for agent in agents]
        cmd = (
            f"python engine.py {' '.join(args)} -r {self.game_config['sims_per_round']} "
            f"-o {self.log_env} > {self.log_env / PAINTVOLLEY_LOG};"
        )
        self.logger.info(f"Running game: {cmd}")
        assert_zero_exit_code(self.environment.execute(cmd))

    def get_results(self, agents: list[Player], round_num: int, stats: RoundStats):
        with open(self.log_round(round_num) / PAINTVOLLEY_LOG) as f:
            round_log = f.read()
        lines = round_log.split("FINAL_RESULTS")[-1].splitlines()

        # Engine prints: "Bot_<i>: <wins> games won, <avg> avg_tiles (<name>)".
        # Score a bot by games won (1-indexed bot id maps to agents[id-1]).
        scores: dict[str, float] = {}
        for line in lines:
            match = re.search(r"Bot_(\d+):\s+(\d+)\s+games\s+won", line)
            if match:
                bot_id = int(match.group(1))
                wins = int(match.group(2))
                if 1 <= bot_id <= len(agents):
                    scores[agents[bot_id - 1].name] = wins

        draw_match = re.search(r"Draws:\s+(\d+)", round_log)
        if draw_match and int(draw_match.group(1)) > 0:
            scores[RESULT_TIE] = int(draw_match.group(1))

        if scores:
            real = {k: v for k, v in scores.items() if k != RESULT_TIE}
            max_score = max(real.values()) if real else 0
            winners = [k for k, v in real.items() if v == max_score]
            stats.winner = winners[0] if len(winners) == 1 else RESULT_TIE
        else:
            stats.winner = "unknown"

        stats.scores = scores
        for player, score in scores.items():
            if player != RESULT_TIE:
                stats.player_stats[player].score = score

    def validate_code(self, agent: Player) -> tuple[bool, str | None]:
        if self.submission not in agent.environment.execute("ls")["output"]:
            return False, f"No {self.submission} file found in the root directory"

        bot_content = agent.environment.execute(f"cat {self.submission}")["output"]
        if "def get_action(" not in bot_content:
            return (
                False,
                f"{self.submission} must define a get_action(obs) function. "
                "See the game description for the required signature.",
            )

        return True, None
