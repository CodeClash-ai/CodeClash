"""Card deck management for Bridge."""

import random

# Card representation: "AS" = Ace of Spades, "7H" = 7 of Hearts
SUITS = ['S', 'H', 'D', 'C']  # Spades, Hearts, Diamonds, Clubs
RANKS = ['A', 'K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2']

# Rank values for comparison
RANK_VALUES = {
    'A': 14, 'K': 13, 'Q': 12, 'J': 11, 'T': 10,
    '9': 9, '8': 8, '7': 7, '6': 6, '5': 5, '4': 4, '3': 3, '2': 2
}


def create_deck() -> list[str]:
    """Create a standard 52-card deck."""
    return [rank + suit for suit in SUITS for rank in RANKS]


def shuffle_and_deal(seed: int = None) -> dict[int, list[str]]:
    """Shuffle deck and deal 13 cards to each of 4 players."""
    deck = create_deck()
    if seed is not None:
        random.seed(seed)
    random.shuffle(deck)

    return {
        0: sorted(deck[0:13], key=lambda c: (SUITS.index(c[1]), -RANK_VALUES[c[0]])),
        1: sorted(deck[13:26], key=lambda c: (SUITS.index(c[1]), -RANK_VALUES[c[0]])),
        2: sorted(deck[26:39], key=lambda c: (SUITS.index(c[1]), -RANK_VALUES[c[0]])),
        3: sorted(deck[39:52], key=lambda c: (SUITS.index(c[1]), -RANK_VALUES[c[0]])),
    }


def get_suit(card: str) -> str:
    """Extract suit from card."""
    return card[1]


def get_rank(card: str) -> str:
    """Extract rank from card."""
    return card[0]


def compare_cards(card1: str, card2: str, trump_suit: str | None, lead_suit: str) -> int:
    """
    Compare two cards to determine winner.

    Returns:
        1 if card1 wins, -1 if card2 wins, 0 if equal (shouldn't happen)
    """
    suit1, rank1 = get_suit(card1), get_rank(card1)
    suit2, rank2 = get_suit(card2), get_rank(card2)

    # Trump beats non-trump
    if trump_suit:
        if suit1 == trump_suit and suit2 != trump_suit:
            return 1
        if suit2 == trump_suit and suit1 != trump_suit:
            return -1

    # Must follow suit - if one follows and one doesn't, follower wins
    if suit1 == lead_suit and suit2 != lead_suit:
        return 1
    if suit2 == lead_suit and suit1 != lead_suit:
        return -1

    # Both same suit (or both trump) - compare ranks
    if RANK_VALUES[rank1] > RANK_VALUES[rank2]:
        return 1
    if RANK_VALUES[rank1] < RANK_VALUES[rank2]:
        return -1

    return 0


def is_valid_card(card: str) -> bool:
    """Check if card string is valid."""
    if len(card) != 2:
        return False
    rank, suit = card[0], card[1]
    return rank in RANKS and suit in SUITS
