import argparse
import json
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from tqdm import tqdm

from codeclash.constants import LOCAL_LOG_DIR


def main(log_dir: Path):
    win_streaks = defaultdict(list)

    for metadata_file in tqdm(list(log_dir.rglob("metadata.json")), desc="Processing tournaments"):
        try:
            metadata = json.load(open(metadata_file))
            p2m = {x["name"]: x["config"]["model"]["model_name"].strip("@") for x in metadata["config"]["players"]}

            if len(p2m) != 2:
                continue

            # Skip tournaments where both players use the same model
            models_in_tournament = list(p2m.values())
            if len(set(models_in_tournament)) < 2:
                continue

            round_stats = metadata.get("round_stats", {})

            # Track consecutive wins for each model
            current_streaks = defaultdict(int)
            models = list(p2m.values())

            # Process rounds in order (skip round 0)
            for round_id in sorted(round_stats.keys(), key=int):
                if round_id == "0":
                    continue

                round_data = round_stats[round_id]
                winner = round_data.get("winner")

                if winner in p2m:
                    winner_model = p2m[winner]

                    # Update streaks
                    for model in models:
                        if model == winner_model:
                            current_streaks[model] += 1
                        else:
                            if current_streaks[model] > 0:
                                win_streaks[model].append(current_streaks[model])
                                current_streaks[model] = 0

            # Record any remaining streaks at tournament end
            for model in models:
                if current_streaks[model] > 0:
                    win_streaks[model].append(current_streaks[model])
        except:
            continue

    # Create heatmap visualization
    models = sorted(win_streaks.keys())
    clean_names = [m.split("/")[-1] for m in models]

    max_streaks = []
    for model in models:
        streaks = win_streaks[model]
        max_streaks.append(max(streaks) if streaks else 0)

    max_streak_overall = max(max_streaks) if max_streaks else 1
    # Limit display to reasonable maximum (tournament length)
    max_streak_overall = min(max_streak_overall, 15)
    streak_matrix = np.zeros((len(models), max_streak_overall))

    for i, model in enumerate(models):
        streaks = win_streaks[model]
        for streak_len in streaks:
            if streak_len <= max_streak_overall:
                streak_matrix[i, streak_len - 1] += 1

    # Normalize by total streaks for each model
    for i in range(len(models)):
        total = np.sum(streak_matrix[i, :])
        if total > 0:
            streak_matrix[i, :] = streak_matrix[i, :] / total * 100

    plt.figure(figsize=(15, 8))
    im = plt.imshow(streak_matrix, cmap="Reds", aspect="auto")

    # Keep track of absolute counts for labels
    absolute_counts = np.zeros((len(models), max_streak_overall))
    for i, model in enumerate(models):
        streaks = win_streaks[model]
        for streak_len in streaks:
            if streak_len <= max_streak_overall:
                absolute_counts[i, streak_len - 1] += 1

    # Add percentage and absolute count labels to ALL cells
    for i in range(len(models)):
        for j in range(max_streak_overall):
            percentage = streak_matrix[i, j]
            count = int(absolute_counts[i, j])
            text = f"{percentage:.1f}%\n({count})"
            plt.text(
                j,
                i,
                text,
                ha="center",
                va="center",
                color="white" if percentage > 40 else "black",
                fontweight="bold",
                fontsize=7,
            )

    plt.xlabel("Win Streak Length")
    plt.ylabel("Model")
    plt.title("Win Streak Distribution (%)", fontweight="bold")
    plt.xticks(range(max_streak_overall), range(1, max_streak_overall + 1))
    plt.yticks(range(len(models)), clean_names)
    plt.colorbar(im, label="Percentage of Streaks")
    plt.tight_layout()
    plt.savefig("heatmap_win_streak_distribution.png", dpi=300, bbox_inches="tight")
    print("Win streak distribution heatmap saved to heatmap_win_streak_distribution.png")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyze model win streak distributions")
    parser.add_argument("-d", "--log_dir", type=Path, default=LOCAL_LOG_DIR, help="Path to logs")
    args = parser.parse_args()
    main(args.log_dir)
