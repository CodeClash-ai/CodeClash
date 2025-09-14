from scipy.stats import binomtest

from codeclash.constants import RESULT_TIE


def calculate_p_value(scores: dict[str, int]) -> float:
    """Calculate the p-value for the statistical significance of the winner.

    Input: scores as a dictionary of player names and number of games won.
    Special case: 'Tie' (constants.RESULT_TIE) is a tie between all players.

    Ties (RESULT_TIE) are excluded by conditioning on decisive games.

    Uses an exact one-sided binomial test for the top player's share vs 1/K,
    Bonferroni-corrected for choosing the winner post hoc among K players.
    Returns 1.0 if there is no unique winner or no decisive games.
    """
    player_wins = {p: c for p, c in scores.items() if p != RESULT_TIE}
    decisive_games = sum(player_wins.values())
    n_players = len(player_wins)
    assert n_players > 1, "At least two players are required to calculate significance"
    if not player_wins or not decisive_games:
        # No winner
        return 1.0
    top_player_wins = max(player_wins.values())
    if sum(c == top_player_wins for c in player_wins.values()) != 1:
        # Multiple players have the same number of wins
        # Definitely not significant
        return 1.0
    # Null-hypothesis: The top player wins 1/n_players of the games
    p0 = 1.0 / n_players
    p_one = binomtest(top_player_wins, decisive_games, p=p0, alternative="greater").pvalue
    # Bonferonni correction: Imagine a game with 100 players. And let's assume that there's one
    # player that wins 10 games, and everyone else 0 or 1. The p-value would probably look pretty convincing
    # However, since we have so many players, it's actually not unlikely that _some_ player will win 10 games
    # by chance. So essentially by selecting the winner post-hoc in a multiple-comparison setting, we've inflated
    # the significance. Bonferonni correction is a simple way to account for this.
    p_bonferonni = p_one * n_players
    return min(1.0, p_bonferonni)
