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


def expected_score(rating_a, rating_b):
    return 1 / (1 + 10 ** ((rating_b - rating_a) / 400))


def calculate_round_weight_linear(round_num, total_rounds):
    """Calculate linear weight for a round, with average weight = 1.0 across all rounds

    Args:
        round_num: Current round number (1-indexed)
        total_rounds: Total number of rounds in the game

    Returns:
        Weight value where early rounds have weight ~0.5 and late rounds have weight ~1.5
    """
    # Linear: weight = 0.5 + (round_num / total_rounds)
    # This gives range [0.5, 1.5] with average = 1.0
    return 0.5 + (round_num / total_rounds)


def calculate_round_weight_exponential(round_num, total_rounds, alpha=2.0):
    """Calculate exponential weight for a round, with average weight = 1.0 across all rounds

    Args:
        round_num: Current round number (1-indexed)
        total_rounds: Total number of rounds in the game
        alpha: Exponential factor (default 2.0 for quadratic weighting)

    Returns:
        Weight value with exponential progression favoring later rounds
    """
    # Raw weight (exponential)
    raw_weight = (round_num / total_rounds) ** alpha

    # Normalization factor so average = 1.0
    # For α=2: average of x² from 0 to 1 is 1/3, so multiply by 3
    norm_factor = alpha + 1  # This makes average = 1.0

    return raw_weight * norm_factor


def update_profiles(prof_and_score, round_weight, k_factor):
    """Update ELO profiles for two players based on their scores and round weight

    Args:
        prof_and_score: List of tuples [(ModelEloProfile, score), ...] for two players
        round_weight: Weight for the current round (affects K-factor)
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
    weighted_k_factor = k_factor * round_weight
    rating_change = weighted_k_factor * (p1_score - expected_p1)

    expected_p2 = expected_score(p2_prof.rating, p1_prof.rating)
    check = weighted_k_factor * (p2_score - expected_p2)
    assert abs(check + rating_change) < 1e-6, "Weighted ELO rating changes do not sum to zero!"

    p1_prof.rating += rating_change
    p2_prof.rating -= rating_change  # Zero-sum property


def main(log_dir: Path, k_factor: int, starting_elo: int, weighting_function: str, alpha: float):
    print(f"Calculating weighted ELO ratings from logs in {log_dir} ...")
    print(f"Using K_FACTOR={k_factor}, STARTING_ELO={starting_elo}")
    print(
        f"Weighting function: {weighting_function}"
        + (f" (alpha={alpha})" if weighting_function == "exponential" else "")
    )
    player_profiles = {}
    for game_log_folder in tqdm([x.parent for x in log_dir.rglob("game.log")]):
        arena = game_log_folder.name.split(".")[1]
        with open(game_log_folder / "metadata.json") as f:
            metadata = json.load(f)
        try:
            p2m = {x["name"]: x["config"]["model"]["model_name"].strip("@") for x in metadata["config"]["players"]}
        except KeyError:
            print(f"Skipping {game_log_folder} (malformed metadata.json)")
            continue

        # Initialize profiles
        for model in p2m.values():
            key = f"{arena}.{model}"
            if key not in player_profiles:
                player_profiles[key] = ModelEloProfile(model=model, arena=arena, rating=starting_elo)

        sims = metadata["game"]["config"]["sims_per_round"]

        # Determine total rounds for weighting calculation
        total_rounds = len([k for k in metadata["round_stats"].keys() if k != "0"])

        if len(p2m) != 2:
            # Only process if there are exactly 2 players
            continue

        for idx, stats in metadata["round_stats"].items():
            if idx == "0":
                # Skip initial round
                continue

            # Calculate round weight
            current_round = int(idx)
            if weighting_function == "linear":
                round_weight = calculate_round_weight_linear(current_round, total_rounds)
            elif weighting_function == "exponential":
                round_weight = calculate_round_weight_exponential(current_round, total_rounds, alpha)
            else:  # none
                round_weight = 1.0

            prof_and_score = []
            valid_submits = sum(
                [x["valid_submit"] for x in stats["player_stats"].values() if x.get("valid_submit") is not None]
            )

            for k, v in stats["player_stats"].items():
                if k != RESULT_TIE:
                    if v["score"] is None:
                        # Not sure why this happens, but just skip it
                        continue
                    s = v["score"] * 1.0 / sims
                    if valid_submits == 1 and v["valid_submit"]:
                        # FOR BACKWARDS COMPATIBILITY: If only one player submitted, give them full point
                        s = 1.0
                    prof = player_profiles[f"{arena}.{p2m[k]}"]
                    prof.rounds_played += 1
                    prof_and_score.append((prof, s))

            # Update ELO ratings - should only happen once per match
            if len(prof_and_score) != 2:
                continue
            update_profiles(prof_and_score, round_weight, k_factor)

    print("=" * 50)
    print("Player ELO profiles:")
    lines = [
        f" - {profile.model} (Arena: {profile.arena}) - ELO: {profile.rating:.1f} (Games: {profile.rounds_played})"
        for profile in player_profiles.values()
    ]
    print("\n".join(sorted(lines)))

    # ELO per player across all games
    weighted_elo = {}
    total_games = {}
    for profile in player_profiles.values():
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
    parser.add_argument("-k", "--k_factor", type=int, help="K-Factor for ELO calculation (Default: 32)", default=32)
    parser.add_argument(
        "-s", "--starting_elo", type=int, help="Starting ELO for new players (Default: 1200)", default=1200
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
    main(**vars(args))
