"""Figgie Arena for CodeClash.

Figgie is a card trading game invented at Jane Street in 2013.
It simulates open-outcry commodities trading.
"""

import re

from codeclash.agents.player import Player
from codeclash.arenas.arena import CodeArena, RoundStats
from codeclash.constants import RESULT_TIE
from codeclash.utils.environment import assert_zero_exit_code

FIGGIE_LOG = "result.log"


class FiggieArena(CodeArena):
    name: str = "Figgie"
    submission: str = "main.py"
    description: str = """Figgie is a card trading game invented at Jane Street in 2013.
It simulates open-outcry commodities trading where players buy and sell cards to accumulate the goal suit.

Game Rules:
- 4 or 5 players, each starting with $350
- 4 players: $50 ante, 10 cards each
- 5 players: $40 ante, 8 cards each
- Pot is always $200
- Deck: one 12-card suit, two 10-card suits, one 8-card suit
- Goal suit: same color as 12-card suit, contains 8 or 10 cards
- At end: $10 per goal suit card, remainder to player(s) with most goal suit cards

Your bot (main.py) must implement:

    def get_action(state: dict) -> dict

state contains:
- position: your player index (0-3 or 0-4)
- hand: dict of suit -> count of cards you hold
- money: your current money
- bids: dict of suit -> {price, player} or None
- offers: dict of suit -> {price, player} or None
- trades: list of completed trades
- num_players: number of players (4 or 5)
- turn: current turn number

Return one of:
- {"type": "pass"}
- {"type": "bid", "suit": "spades", "price": 5}
- {"type": "offer", "suit": "spades", "price": 10}
- {"type": "buy", "suit": "spades"}
- {"type": "sell", "suit": "spades"}

Suits: "spades", "clubs", "hearts", "diamonds"
"""

    def __init__(self, config, **kwargs):
        super().__init__(config, **kwargs)
        num_players = len(config.get("players", []))
        if num_players not in [4, 5]:
            raise ValueError(f"Figgie requires 4 or 5 players, got {num_players}")

    def execute_round(self, agents: list[Player]) -> None:
        args = [f"/{agent.name}/{self.submission}" for agent in agents]
        cmd = (
            f"python engine.py {' '.join(args)} -r {self.game_config['sims_per_round']} > {self.log_env / FIGGIE_LOG};"
        )
        self.logger.info(f"Running game: {cmd}")
        assert_zero_exit_code(self.environment.execute(cmd))

    def get_results(self, agents: list[Player], round_num: int, stats: RoundStats):
        with open(self.log_round(round_num) / FIGGIE_LOG) as f:
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

        if "def get_action(" not in bot_content:
            return (
                False,
                f"{self.submission} must define a get_action(state) function. "
                "See the game description for the required signature.",
            )

        return True, None
