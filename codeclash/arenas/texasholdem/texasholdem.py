import re

from codeclash.agents.player import Player
from codeclash.arenas.arena import CodeArena, RoundStats
from codeclash.constants import RESULT_TIE
from codeclash.utils.environment import assert_zero_exit_code

LOG_FILE = "result.log"


class TexasHoldemArena(CodeArena):
    name: str = "TexasHoldem"
    submission: str = "main.py"
    variant: str = "classic"  # Can be overridden by subclasses
    description: str = """Texas Hold'em is a heads-up (2-player) No-Limit poker game where each player receives 2 private hole cards and shares 5 community cards.

Players bet based on hand strength across 4 betting rounds (preflop, flop, turn, river).
The best 5-card hand from the 7 available cards wins the pot.

Your bot must implement a `get_move(state)` function that returns one of:
- 'fold': Give up the hand
- 'check': Pass when no bet to call
- 'call': Match the current bet
- 'raise <amount>': Raise to a specified total amount
- 'all_in': Bet all remaining chips

The state object contains:
- hole_cards: Your 2 private cards (e.g., ['As', 'Kh'])
- community_cards: Current board cards (0-5)
- pot: Total pot size
- current_bet: Amount to call
- player_stack: Your remaining chips
- opponent_stack: Opponent's chips
- player_bet: Your bet this round
- opponent_bet: Opponent's bet this round
- position: 'button' or 'big_blind'
- round_name: 'preflop', 'flop', 'turn', 'river'
- min_raise: Minimum raise amount
- is_first_action: True if first to act this betting round
- variant: 'classic' or 'short_deck'

Cards use 2-character notation: rank (23456789TJQKA) + suit (cdhs).
Example: 'As' = Ace of spades, 'Th' = Ten of hearts.

Hand rankings (highest to lowest):
1. Royal Flush  2. Straight Flush  3. Four of a Kind  4. Full House
5. Flush  6. Straight  7. Three of a Kind  8. Two Pair  9. Pair  10. High Card
"""

    def __init__(self, config, **kwargs):
        super().__init__(config, **kwargs)
        assert len(config["players"]) == 2, "TexasHoldem requires exactly 2 players"

    def execute_round(self, agents: list[Player]) -> None:
        args = [f"/{agent.name}/{self.submission}" for agent in agents]
        variant_arg = f"--variant {self.variant}" if self.variant else ""
        cmd = f"python engine.py {' '.join(args)} -r {self.game_config['sims_per_round']} {variant_arg} > {self.log_env / LOG_FILE};"
        self.logger.info(f"Running game: {cmd}")
        assert_zero_exit_code(self.environment.execute(cmd))

    def get_results(self, agents: list[Player], round_num: int, stats: RoundStats):
        with open(self.log_round(round_num) / LOG_FILE) as f:
            round_log = f.read()
        lines = round_log.split("FINAL_RESULTS")[-1].splitlines()

        scores = {}
        for line in lines:
            match = re.search(r"Bot\_(\d)\_main:\s(\d+)\srounds\swon", line)
            if match:
                bot_id = match.group(1)
                rounds_won = int(match.group(2))
                scores[agents[int(bot_id) - 1].name] = rounds_won

        draw_match = re.search(r"Draws:\s(\d+)", round_log)
        if draw_match and int(draw_match.group(1)) > 0:
            scores[RESULT_TIE] = int(draw_match.group(1))

        stats.winner = max(scores, key=scores.get) if scores else "unknown"
        stats.scores = scores
        for player, score in scores.items():
            if player != RESULT_TIE:
                stats.player_stats[player].score = score

    def validate_code(self, agent: Player) -> tuple[bool, str | None]:
        if self.submission not in agent.environment.execute("ls")["output"]:
            return False, f"No {self.submission} file found"

        bot_content = agent.environment.execute(f"cat {self.submission}")["output"]
        if "def get_move(" not in bot_content:
            return False, "Missing required function: def get_move(state)"

        return True, None


class ShortDeckHoldemArena(TexasHoldemArena):
    """Short-deck (Six-plus) Hold'em variant with 36-card deck."""

    name: str = "ShortDeckHoldem"
    variant: str = "short_deck"
    description: str = """Short-deck (Six-plus) Hold'em is a heads-up (2-player) No-Limit poker variant using a 36-card deck (6 through Ace, removing 2-5).

Key differences from classic Texas Hold'em:
- 36-card deck (ranks 6-A only, no 2-5)
- FLUSH BEATS FULL HOUSE (flushes are harder to make with fewer cards per suit)
- A-6-7-8-9 is the lowest straight (wheel)

Your bot must implement a `get_move(state)` function that returns one of:
- 'fold': Give up the hand
- 'check': Pass when no bet to call
- 'call': Match the current bet
- 'raise <amount>': Raise to a specified total amount
- 'all_in': Bet all remaining chips

The state object contains:
- hole_cards: Your 2 private cards (e.g., ['As', 'Kh'])
- community_cards: Current board cards (0-5)
- pot: Total pot size
- current_bet: Amount to call
- player_stack: Your remaining chips
- opponent_stack: Opponent's chips
- player_bet: Your bet this round
- opponent_bet: Opponent's bet this round
- position: 'button' or 'big_blind'
- round_name: 'preflop', 'flop', 'turn', 'river'
- min_raise: Minimum raise amount
- is_first_action: True if first to act this betting round
- variant: 'short_deck'

Cards use 2-character notation: rank (6789TJQKA) + suit (cdhs).
Example: 'As' = Ace of spades, 'Th' = Ten of hearts, '6c' = Six of clubs.

Short-deck hand rankings (highest to lowest):
1. Royal Flush  2. Straight Flush  3. Four of a Kind  4. FLUSH (beats full house!)
5. Full House  6. Straight  7. Three of a Kind  8. Two Pair  9. Pair  10. High Card
"""
