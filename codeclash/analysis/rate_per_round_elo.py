import argparse
import json
from dataclasses import dataclass
from pathlib import Path

from matplotlib import pyplot as plt
from tqdm import tqdm

from codeclash.analysis.rate_elo import (
    calculate_round_weight_exponential,
    calculate_round_weight_linear,
    update_profiles,
)
from codeclash.constants import LOCAL_LOG_DIR, RESULT_TIE


@dataclass
class ModelRoundEloProfile:
    model: str
    arena: str
    rating: float
    round_idx: int
    rounds_played: int = 0


def main(log_dir: Path, k_factor: int, starting_elo: int, weighting_function: str, alpha: float):
    print(f"Calculating weighted ELO ratings from logs in {log_dir} ...")
    print(f"Using K_FACTOR={k_factor}, STARTING_ELO={starting_elo}")
    print(
        f"Weighting function: {weighting_function}"
        + (f" (alpha={alpha})" if weighting_function == "exponential" else "")
    )
    player_round_profiles = {}
    for game_log_folder in tqdm([x.parent for x in log_dir.rglob("game.log")]):
        arena = game_log_folder.name.split(".")[1]
        metadata = json.load(open(game_log_folder / "metadata.json"))
        try:
            p2m = {x["name"]: x["config"]["model"]["model_name"].strip("@") for x in metadata["config"]["players"]}
        except KeyError:
            print(f"Skipping {game_log_folder} (malformed metadata.json)")
            continue

        if len(p2m) != 2:
            # Only process if there are exactly 2 players:
            continue

        sims = metadata["game"]["config"]["sims_per_round"]

        # Determine total rounds for weighting calculation
        total_rounds = len([k for k in metadata["round_stats"].keys() if k != "0"])

        for idx, stats in metadata["round_stats"].items():
            if idx == "0":
                # Skip initial round
                continue

            # Initialize profiles
            for model in p2m.values():
                key = f"{arena}.{model}.{idx}"
                if key not in player_round_profiles:
                    player_round_profiles[key] = ModelRoundEloProfile(
                        model=model, arena=arena, rating=starting_elo, round_idx=int(idx)
                    )

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
                        # If only one player submitted, give them full score
                        s = 1.0
                    prof = player_round_profiles[f"{arena}.{p2m[k]}.{idx}"]
                    prof.rounds_played += 1
                    prof_and_score.append((prof, s))

            if len(prof_and_score) != 2:
                # Should always be 2 players here
                continue
            update_profiles(prof_and_score, round_weight, k_factor)

    lines = {
        pid: [[] for _ in range(15)]
        for pid in {x.rsplit(".", 1)[0].split(".", 1)[-1] for x in player_round_profiles.keys()}
    }
    for pid, profile in player_round_profiles.items():
        k = pid.rsplit(".", 1)[0].split(".", 1)[-1]
        if 1 <= profile.round_idx <= 15:
            lines[k][profile.round_idx - 1].append(profile)

    print("=" * 50)
    print("Player ELO progression per round:")

    def aggregate_elos_across_games(profiles):
        return sum([p.rating * p.rounds_played for p in profiles]) / sum([p.rounds_played for p in profiles])

    for pid, elos in lines.items():
        lines[pid] = [aggregate_elos_across_games(r) for r in elos]
        print(f" - {pid}: " + ", ".join([f"{e:.1f}" for e in lines[pid]]))

    # Create line chart of ELO progression per player
    plt.figure(figsize=(10, 6))
    for pid, elos in lines.items():
        plt.plot(range(1, 16), elos, marker="o", label=pid)
    plt.title("ELO Progression per Round")
    plt.xlabel("Round")
    plt.ylabel("ELO Rating")
    plt.xticks(range(1, 16))
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig("elo_progression_per_round.png")
    print("ELO progression chart saved to elo_progression_per_round.png")


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
