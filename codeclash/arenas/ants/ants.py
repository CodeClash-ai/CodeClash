import re

from codeclash.agents.player import Player
from codeclash.arenas.arena import CodeArena, RoundStats
from codeclash.constants import RESULT_TIE
from codeclash.utils.environment import assert_zero_exit_code

ANTS_LOG = "result.log"


class AntsArena(CodeArena):
    name: str = "Ants"
    submission: str = "main.py"
    description: str = """Your bot (`main.py`) commands a swarm of ants in Ants, a fog-of-war RTS on a toroidal
(wrap-around) grid, in the spirit of the 2010 Ants AI Challenge. Every turn all ants move one cell at
once. You only see the map within your ants' view radius (fog of war). Combat is focus-fire: an ant dies
unless it has strictly fewer enemies within attack range than every enemy attacking it (so gang up to
win fights). Food within spawn radius of exactly one player's ants is gathered and spawns a new ant on a
hill. Move an ant onto an enemy hill to raze it -- razing enemy hills is the objective. Most hills razed
(tiebreak: ants alive) wins.

Your bot must implement:
    def do_turn(obs: dict) -> list

Return a list of moves, each [row, col, dir] with dir in "N","S","E","W" (N = row-1); the ant at
(row, col) steps that way. Un-ordered ants stay; moving into water is ignored; two ants onto one cell
both die. do_turn runs in one long-lived process, so you may keep state (a remembered map) in globals.

`obs` is your fog-limited view: obs["turn"]/["max_turns"], obs["rows"]/["cols"] (toroidal),
obs["viewradius2"]/["attackradius2"]/["spawnradius2"], obs["you"], obs["my_ants"], obs["my_hills"],
and (only where visible) obs["enemy_ants"], obs["enemy_hills"], obs["food"], obs["water"].
Distances are toroidal: dr=min(|dr|,rows-|dr|), dc likewise, compare dr*dr+dc*dc to the radius2 values.
"""

    def __init__(self, config, **kwargs):
        super().__init__(config, **kwargs)
        assert len(config["players"]) >= 2, "Ants needs at least two players"

    def execute_round(self, agents: list[Player]) -> None:
        args = [f"/{agent.name}/{self.submission}" for agent in agents]
        cmd = (
            f"python engine.py {' '.join(args)} -r {self.game_config['sims_per_round']} "
            f"-o {self.log_env} > {self.log_env / ANTS_LOG};"
        )
        self.logger.info(f"Running game: {cmd}")
        assert_zero_exit_code(self.environment.execute(cmd))

    def get_results(self, agents: list[Player], round_num: int, stats: RoundStats):
        with open(self.log_round(round_num) / ANTS_LOG) as f:
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
        if "def do_turn(" not in bot_content:
            return (
                False,
                f"{self.submission} must define a do_turn(obs) function. "
                "See the game description for the required signature.",
            )

        return True, None
