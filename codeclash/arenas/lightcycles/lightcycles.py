import re

from codeclash.agents.player import Player
from codeclash.arenas.arena import CodeArena, RoundStats
from codeclash.constants import RESULT_TIE
from codeclash.utils.environment import assert_zero_exit_code

LIGHTCYCLES_LOG = "result.log"


class LightCyclesArena(CodeArena):
    name: str = "LightCycles"
    submission: str = "main.py"
    description: str = """Your bot (`main.py`) drives a cycle in LightCycles, a Tron light-cycles game. Each
player rides around a bordered grid leaving a solid trail behind. The board may contain static rock
obstacles too. Every tick all cycles move one cell simultaneously; you crash (and are eliminated) if you
move into a wall/border, a rock, any trail (yours or an opponent's), or the same cell as another cycle (a
head-on). The last cycle riding wins; if all remaining cycles crash on the same tick it's a draw; at the
tick cap the most territory (trail cells) wins.

Your bot must implement:
    def get_move(obs: dict) -> str

Return one of "N", "S", "E", "W" (up/down/right/left). Reversing into your own neck is ignored (you go
straight); an invalid/crashing/slow move also makes you continue straight.

`obs` gives the full deterministic state each tick: obs["tick"]/["max_ticks"], obs["width"]/["height"],
obs["you"] (your id), obs["players"] (list of {id, x, y, dir, alive}), and obs["grid"]
(grid[y][x] = player id >=0, -1 empty, or -2 rock; off-grid is a wall). Origin is top-left; N is -y.
"""

    def __init__(self, config, **kwargs):
        super().__init__(config, **kwargs)
        assert len(config["players"]) >= 2, "LightCycles needs at least two players"

    def execute_round(self, agents: list[Player]) -> None:
        args = [f"/{agent.name}/{self.submission}" for agent in agents]
        cmd = (
            f"python engine.py {' '.join(args)} -r {self.game_config['sims_per_round']} "
            f"-o {self.log_env} > {self.log_env / LIGHTCYCLES_LOG};"
        )
        self.logger.info(f"Running game: {cmd}")
        assert_zero_exit_code(self.environment.execute(cmd))

    def get_results(self, agents: list[Player], round_num: int, stats: RoundStats):
        with open(self.log_round(round_num) / LIGHTCYCLES_LOG) as f:
            round_log = f.read()
        lines = round_log.split("FINAL_RESULTS")[-1].splitlines()

        # Engine prints: "Bot_<i>: <wins> games won (<name>)". Score = games won.
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
        if "def get_move(" not in bot_content:
            return (
                False,
                f"{self.submission} must define a get_move(obs) function. "
                "See the game description for the required signature.",
            )

        return True, None
