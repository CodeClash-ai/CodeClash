#!/usr/bin/env python3
import argparse
import json
from dataclasses import dataclass
from pathlib import Path

from tqdm import tqdm

from codeclash.constants import LOCAL_LOG_DIR, RESULT_TIE


@dataclass
class ModelEloProfile:
    model: str
    arena: str
    rating: float
    rounds_played: int = 0


def expected_score(rating_a: float, rating_b: float) -> float:
    return 1 / (1 + 10 ** ((rating_b - rating_a) / 400))


def calculate_round_weight_linear(round_num: int, total_rounds: int) -> float:
    """Calculate linear weight for a round, with average weight = 1.0 across all rounds

    Args:
        round_num: Current round number (1-indexed. the first round that we show in the viewer
            is 0, but it's not a real round, so not included here)
        total_rounds: Total number of rounds in the game

    Returns:
        Weight value where early rounds have weight ~0.5 and late rounds have weight ~1.5
    """
    assert round_num >= 1
    assert round_num <= total_rounds
    # Linear: weight = 0.5 + (round_num / total_rounds)
    # This gives range [0.5, 1.5] with average = 1.0
    return 0.5 + (round_num / total_rounds)


def calculate_round_weight_exponential(round_num: int, total_rounds: int, alpha: float = 2.0) -> float:
    """Calculate exponential weight for a round, with average weight = 1.0 across all rounds

    Args:
        round_num: Current round number (1-indexed. the first round that we show in the viewer
            is 0, but it's not a real round, so not included here)
        total_rounds: Total number of rounds in the game
        alpha: Exponential factor (default 2.0 for quadratic weighting)

    Returns:
        Weight value with exponential progression favoring later rounds
    """
    assert round_num >= 1
    assert round_num <= total_rounds
    # Raw weight (exponential)
    raw_weight = (round_num / total_rounds) ** alpha

    # Normalization factor so average = 1.0
    # For α=2: average of x² from 0 to 1 is 1/3, so multiply by 3
    norm_factor = alpha + 1  # This makes average = 1.0

    return raw_weight * norm_factor


def update_profiles(prof_and_score: list[tuple[ModelEloProfile, float]], k_factor: float) -> None:
    """Update ELO profiles for two players based on their scores

    Args:
        prof_and_score: List of tuples [(ModelEloProfile, score), ...] for two players
        k_factor: Base K-factor for ELO calculation
    """
    p1_prof, p1_raw_score = prof_and_score[0]
    p2_prof, p2_raw_score = prof_and_score[1]

    # Normalize scores so they sum to 1.0 (required for proper ELO)
    total_score = p1_raw_score + p2_raw_score
    if total_score > 0:
        p1_score = p1_raw_score / total_score
        p2_score = p2_raw_score / total_score
    else:
        # If both players scored 0, treat as a tie
        p1_score = p2_score = 0.5

    expected_p1 = expected_score(p1_prof.rating, p2_prof.rating)

    # Apply round weighting to K-factor
    rating_change = k_factor * (p1_score - expected_p1)

    # Consistency:
    expected_p2 = expected_score(p2_prof.rating, p1_prof.rating)
    check = k_factor * (p2_score - expected_p2)
    assert abs(check + rating_change) < 1e-6, "Weighted ELO rating changes do not sum to zero!"

    p1_prof.rating += rating_change
    p2_prof.rating -= rating_change  # Zero-sum property


class SkipTournamentException(Exception):
    pass


class ELOCalculator:
    def __init__(self, *, k_factor: float, starting_elo: float, weighting_function: str, alpha: float):
        self._k_factor = k_factor
        self._starting_elo = starting_elo
        self._weighting_function = weighting_function
        self._alpha = alpha
        self._player_profiles = {}

    def _analyze_round(self, stats: dict, player2profile: dict, *, total_rounds: int, sims: int) -> None:
        """Update all profiles based on the results of one round"""
        # Calculate round weight
        current_round = stats["round_num"]
        if self._weighting_function == "linear":
            round_weight = calculate_round_weight_linear(current_round, total_rounds)
        elif self._weighting_function == "exponential":
            round_weight = calculate_round_weight_exponential(current_round, total_rounds, self._alpha)
        else:  # none
            round_weight = 1.0

        prof_and_score: list[tuple[ModelEloProfile, float]] = []
        valid_submits = sum(
            [x["valid_submit"] for x in stats["player_stats"].values() if x.get("valid_submit") is not None]
        )

        for k, v in stats["player_stats"].items():
            if k != RESULT_TIE:
                if v["score"] is None:
                    # Not sure why this happens, but just skip it
                    # Kilian: This is probably when we skip a round (might have fixed this, but probably in old logs)
                    continue
                _score = v["score"] * 1.0 / sims
                if valid_submits == 1 and v["valid_submit"]:
                    # FOR BACKWARDS COMPATIBILITY: If only one player submitted, give them full point
                    _score = 1.0
                prof = player2profile[k]
                prof.rounds_played += 1
                prof_and_score.append((prof, _score))

        # Update ELO ratings - should only happen once per match
        if len(prof_and_score) != 2:
            print(f"Skipping round {current_round} (wrong number of players)")
            raise SkipTournamentException

        weighted_k_factor = self._k_factor * round_weight
        update_profiles(prof_and_score, weighted_k_factor)

    def _analyze_tournament(self, tournament_log_folder: Path) -> None:
        """Update all profiles based on the results of one tournament"""
        with open(tournament_log_folder / "metadata.json") as f:
            metadata = json.load(f)
        try:
            players = metadata["config"]["players"]
            arena = metadata["config"]["game"]["name"]
        except KeyError:
            print(f"Skipping {tournament_log_folder} (malformed metadata.json)")
            raise SkipTournamentException

        if len(players) != 2:
            # Only process if there are exactly 2 players
            print(f"Skipping {tournament_log_folder} (wrong number of players)")
            raise SkipTournamentException

        # Initialize profiles
        player2profile = {}
        for player_config in players:
            player_name = player_config["name"]
            model = player_config["config"]["model"]["model_name"].strip("@")
            key = f"{arena}.{model}"
            if key not in self._player_profiles:
                self._player_profiles[key] = ModelEloProfile(model=model, arena=arena, rating=self._starting_elo)
            player2profile[player_name] = self._player_profiles[key]

        sims = metadata["game"]["config"]["sims_per_round"]

        # Determine total rounds for weighting calculation
        total_rounds = len([k for k in metadata["round_stats"].keys() if k != "0"])

        for idx, stats in metadata["round_stats"].items():
            idx = int(idx)
            if idx == 0:
                # Skip initial round
                continue

            assert idx == stats["round_num"], (idx, stats["round_num"])

            self._analyze_round(stats, player2profile, total_rounds=total_rounds, sims=sims)

    def analyze(self, log_dir: Path) -> None:
        print(f"Calculating weighted ELO ratings from logs in {log_dir} ...")
        print(f"Using K_FACTOR={self._k_factor}, STARTING_ELO={self._starting_elo}")
        print(
            f"Weighting function: {self._weighting_function}"
            + (f" (alpha={self._alpha})" if self._weighting_function == "exponential" else "")
        )
        for game_log_folder in tqdm([x.parent for x in log_dir.rglob("metadata.json")]):
            try:
                self._analyze_tournament(game_log_folder)
            except SkipTournamentException:
                print(f"Skipping {game_log_folder}")
                continue

    def print_results(self) -> None:
        print("=" * 50)
        print("Player ELO profiles:")
        lines = [
            f" - {profile.model} (Arena: {profile.arena}) - ELO: {profile.rating:.1f} (Games: {profile.rounds_played})"
            for profile in self._player_profiles.values()
        ]
        print("\n".join(sorted(lines)))

        # ELO per player across all games
        weighted_elo = {}
        total_games = {}
        for profile in self._player_profiles.values():
            mid = profile.model
            weighted_elo[mid] = weighted_elo.get(mid, 0) + profile.rating * profile.rounds_played
            total_games[mid] = total_games.get(mid, 0) + profile.rounds_played

        print("\nELO per player (across all games):")
        calc_avg_elo = lambda total_elo, games: total_elo / games
        lines = sorted(
            [
                f"{pid}: {calc_avg_elo(weighted_elo[pid], total_games[pid]):.1f} (Games: {total_games[pid]})"
                for pid in weighted_elo
                if total_games[pid] > 0
            ],
            key=lambda x: float(x.split(":")[1].split("(")[0]),
            reverse=True,
        )
        for i, line in enumerate(lines, 1):
            print(f"{i}. {line}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Calculate weighted ELO ratings with configurable weighting functions")
    parser.add_argument("-d", "--log_dir", type=Path, help="Path to game logs (Default: logs/)", default=LOCAL_LOG_DIR)
    parser.add_argument("-k", "--k_factor", type=float, help="K-Factor for ELO calculation (Default: 32)", default=32)
    parser.add_argument(
        "-s", "--starting_elo", type=float, help="Starting ELO for new players (Default: 1200)", default=1200
    )
    parser.add_argument(
        "-w",
        "--weighting_function",
        choices=["none", "linear", "exponential"],
        default="none",
        help="Weighting function for rounds: 'linear' for gradual increase, 'exponential' for accelerating importance (Default: none)",
    )
    parser.add_argument(
        "-a",
        "--alpha",
        type=float,
        default=2.0,
        help="Alpha parameter for exponential weighting (Default: 2.0, ignored for linear weighting)",
    )
    args = parser.parse_args()
    calculator = ELOCalculator(
        k_factor=args.k_factor,
        starting_elo=args.starting_elo,
        weighting_function=args.weighting_function,
        alpha=args.alpha,
    )
    calculator.analyze(args.log_dir)
    calculator.print_results()
