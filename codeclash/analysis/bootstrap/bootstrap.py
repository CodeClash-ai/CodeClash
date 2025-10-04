import random
from collections import Counter
from dataclasses import dataclass
from typing import Literal

random.seed(42)

TIE = "tie"
ELO_DENOM = 400


@dataclass
class Player:
    name: str
    true_elo: float
    measured_elo: float


def expected_score(rating_a: float, rating_b: float) -> float:
    """Calculate expected score for player A against player B."""
    return 1 / (1 + 10 ** ((rating_b - rating_a) / ELO_DENOM))


def update_elo(*, current_rating: float, expected_score: float, actual_score: float, k: float = 32) -> float:
    """
    Update Elo rating based on game outcome.

    actual: 1.0 for win, 0.5 for draw, 0.0 for loss
    k: K-factor, typically 32 for regular players, 16 for masters
    """
    return current_rating + k * (actual_score - expected_score)


# Modeling limitation, draw probability probably usually depends on score difference
class Game:
    def __init__(self, name: str, draw_probability: float = 0.0, repetitions: int = 1):
        """
        Args:
            name: The name of the game.
            draw_probability: The probability of a tie in the game.
            repetitions: The number of times to play the game.
        """
        self.name = name
        assert 0 <= draw_probability <= 1
        self.draw_probability = draw_probability
        self.repetitions = repetitions

    def play_game(self, players: list[Player]) -> dict[str, int]:
        """
        Returns:
            dictionary of number of times each player won or tied
        """
        assert len(players) == 2
        p1_elo = players[0].true_elo
        p2_elo = players[1].true_elo
        p_tie = self.draw_probability
        win_prob_a_no_tie = expected_score(p1_elo, p2_elo)
        win_prob_b_no_tie = 1 - win_prob_a_no_tie
        win_prob_a = win_prob_a_no_tie * (1 - p_tie)
        win_prob_b = win_prob_b_no_tie * (1 - p_tie)
        results = []
        for _ in range(self.repetitions):
            single_result = random.choices(
                [players[0].name, players[1].name, TIE], weights=[win_prob_a, win_prob_b, p_tie]
            )[0]
            results.append(single_result)
        return dict(Counter(results))


class Tournament:
    def __init__(
        self,
        game: Game,
        *,
        n_rounds: int,
        k: float = 32,
        update_strategy: Literal["per_round", "per_tournament"] = "per_round",
    ):
        self.game = game
        self.n_rounds = n_rounds
        self.k = k
        self.update_strategy = update_strategy

    def run_tournament(self, players: list[Player]):
        """Runs tournament with the players and updates their measured elo."""
        assert len(players) == 2
        results = []
        for _round in range(self.n_rounds):
            results.append(self.game.play_game(players))
        if self.update_strategy == "per_round":
            self._update_elo_per_round(players, results)
        elif self.update_strategy == "per_tournament":
            self._update_elo_per_tournament(players, results)
        else:
            raise ValueError(f"Invalid update strategy: {self.update_strategy}")

    def _update_elo_per_round(self, players: list[Player], results: list[dict[str, int]]):
        for result in results:
            p1 = players[0]
            p2 = players[1]
            p1_expected = expected_score(p1.measured_elo, p2.measured_elo)
            p2_expected = expected_score(p2.measured_elo, p1.measured_elo)
            n_games = sum(result.values())
            n_ties = result.get(TIE, 0)
            p1_actual = (result.get(p1.name, 0) + 0.5 * n_ties) / n_games
            p2_actual = (result.get(p2.name, 0) + 0.5 * n_ties) / n_games
            p1.measured_elo = update_elo(
                current_rating=p1.measured_elo, expected_score=p1_expected, actual_score=p1_actual, k=self.k
            )
            p2.measured_elo = update_elo(
                current_rating=p2.measured_elo, expected_score=p2_expected, actual_score=p2_actual, k=self.k
            )

    def _update_elo_per_tournament(self, players: list[Player], results: list[dict[str, int]]):
        assert len(players) == 2
        n_rounds = len(results)
        aggregated_scores = {p.name: 0 for p in players}
        for result in results:
            for p in players:
                score = (result.get(p.name, 0) + 0.5 * result.get(TIE, 0)) / sum(result.values())
                aggregated_scores[p.name] += score / n_rounds
        p1 = players[0]
        p2 = players[1]
        p1_expected = expected_score(p1.measured_elo, p2.measured_elo)
        p2_expected = expected_score(p2.measured_elo, p1.measured_elo)
        p1_actual = aggregated_scores[p1.name]
        p2_actual = aggregated_scores[p2.name]
        p1.measured_elo = update_elo(
            current_rating=p1.measured_elo, expected_score=p1_expected, actual_score=p1_actual, k=self.k
        )
        p2.measured_elo = update_elo(
            current_rating=p2.measured_elo, expected_score=p2_expected, actual_score=p2_actual, k=self.k
        )


class TwoPlayerBasedLeaderboard:
    def __init__(self, tournaments: list[Tournament]):
        self.tournaments = tournaments

    def run(self, players: list[Player]):
        for tournament in self.tournaments:
            for i_player in range(len(players)):
                for j_player in range(i_player + 1, len(players)):
                    tournament.run_tournament([players[i_player], players[j_player]])
