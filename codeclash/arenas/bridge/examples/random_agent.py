"""
Example random Bridge agent.

This bot makes random legal moves for both bidding and playing.
Use this as a template for your own Bridge bot.
"""

import random


def get_bid(game_state):
    """
    Make a bidding decision.

    Args:
        game_state: Dictionary containing:
            - position: Your position (0=North, 1=East, 2=South, 3=West)
            - hand: List of cards in your hand (e.g., ["AS", "KH", "7D"])
            - bids: List of previous bids
            - legal_bids: List of legal bids you can make

    Returns:
        A bid string (e.g., "PASS", "1H", "2NT", "3S")
    """
    legal_bids = game_state.get("legal_bids", ["PASS"])

    # Simple strategy: PASS 80% of the time, random bid 20%
    if random.random() < 0.8 or len(legal_bids) == 1:
        return "PASS"

    # Filter out PASS and choose a random bid
    non_pass_bids = [b for b in legal_bids if b != "PASS"]
    if non_pass_bids:
        return random.choice(non_pass_bids)
    return "PASS"


def play_card(game_state):
    """
    Play a card.

    Args:
        game_state: Dictionary containing:
            - position: Your position (0=North, 1=East, 2=South, 3=West)
            - hand: List of cards currently in your hand
            - current_trick: List of cards played so far in current trick
            - legal_cards: List of legal cards you can play
            - contract: The current contract (level, suit, declarer)
            - tricks_won: Tricks won by each team so far

    Returns:
        A card string (e.g., "AS", "7H", "KD")
    """
    legal_cards = game_state.get("legal_cards", game_state.get("hand", []))

    if not legal_cards:
        # Should never happen, but fallback to first card in hand
        hand = game_state.get("hand", [])
        return hand[0] if hand else "AS"

    # Play a random legal card
    return random.choice(legal_cards)
