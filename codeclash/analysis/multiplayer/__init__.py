"""
Multi-player tournament analysis tools.

Analyses that compare 2-player vs N-player tournament dynamics.
"""

from codeclash.analysis.multiplayer.win_change_rate import analyze_win_change_rate
from codeclash.analysis.multiplayer.win_share import analyze_winner_share

__all__ = [
    "analyze_win_change_rate",
    "analyze_winner_share",
]
