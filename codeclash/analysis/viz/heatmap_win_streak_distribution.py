#!/usr/bin/env python3
import argparse
import json
from collections import defaultdict
from pathlib import Path

import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np
from tqdm import tqdm

from codeclash.analysis.viz.utils import ASSETS_DIR, FONT_BOLD, MODEL_TO_DISPLAY_NAME
from codeclash.constants import LOCAL_LOG_DIR

OUTPUT_FILE = ASSETS_DIR / "heatmap_win_streak_distribution.pdf"


def main(log_dir: Path, xlim: int = 15):
    win_streaks = defaultdict(list)

    for metadata_file in tqdm(list(log_dir.rglob("metadata.json")), desc="Processing tournaments"):
        try:
            metadata = json.load(open(metadata_file))
            p2m = {
                x["name"]: x["config"]["model"]["model_name"].strip("@").split("/")[-1]
                for x in metadata["config"]["players"]
            }

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

    max_streaks = []
    for model in models:
        streaks = win_streaks[model]
        max_streaks.append(max(streaks) if streaks else 0)

    # Use xlim as the display maximum, start from streak length 2
    display_columns = xlim - 1  # Exclude length 1, so columns represent 2 through xlim
    streak_matrix = np.zeros((len(models), display_columns))

    for i, model in enumerate(models):
        streaks = win_streaks[model]
        for streak_len in streaks:
            # Skip streaks of length 1
            if streak_len == 1:
                continue
            # Map streak_len 2 to column 0, 3 to column 1, etc.
            if streak_len < xlim:
                streak_matrix[i, streak_len - 2] += 1
            else:
                # Aggregate all streaks >= xlim into the last column
                streak_matrix[i, display_columns - 1] += 1

    # Normalize by total streaks for each model (excluding length 1)
    for i in range(len(models)):
        total = np.sum(streak_matrix[i, :])
        if total > 0:
            streak_matrix[i, :] = streak_matrix[i, :] / total * 100

    plt.figure(figsize=(6, 6))
    cmap = mcolors.LinearSegmentedColormap.from_list("br", ["#ffffff", "#3498db"])
    plt.imshow(streak_matrix, cmap=cmap, aspect="auto")

    # Keep track of absolute counts for labels
    absolute_counts = np.zeros((len(models), display_columns))
    for i, model in enumerate(models):
        streaks = win_streaks[model]
        for streak_len in streaks:
            # Skip streaks of length 1
            if streak_len == 1:
                continue
            # Map streak_len 2 to column 0, 3 to column 1, etc.
            if streak_len < xlim:
                absolute_counts[i, streak_len - 2] += 1
            else:
                # Aggregate all streaks >= xlim into the last column
                absolute_counts[i, display_columns - 1] += 1

    # Add percentage and absolute count labels to ALL cells
    for i in range(len(models)):
        for j in range(display_columns):
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
                fontsize=12,
                fontproperties=FONT_BOLD,
            )

    plt.xlabel("Consecutive Rounds Won", fontproperties=FONT_BOLD, fontsize=18)

    # Create x-axis labels starting from 2, with the last one as "xlim+"
    x_labels = [str(i) for i in range(2, xlim)] + [f"{xlim}+"]
    plt.xticks(range(display_columns), x_labels, fontproperties=FONT_BOLD, fontsize=14)

    # Create y-axis labels with total streak counts (excluding length 1)
    y_labels = []
    for model in models:
        total_streaks = sum(1 for streak_len in win_streaks[model] if streak_len >= 2)
        display_name = MODEL_TO_DISPLAY_NAME[model]
        y_labels.append(f"{display_name}\n(n={total_streaks})")

    plt.yticks(range(len(models)), y_labels, fontproperties=FONT_BOLD, fontsize=14)
    # plt.colorbar(im, label="Percentage of Streaks")
    plt.tight_layout()
    plt.savefig(OUTPUT_FILE, dpi=300, bbox_inches="tight")
    print(f"Win streak distribution heatmap saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyze model win streak distributions")
    parser.add_argument("-d", "--log_dir", type=Path, default=LOCAL_LOG_DIR, help="Path to logs")
    parser.add_argument("-x", "--xlim", type=int, default=15, help="Max win streak length to display")
    args = parser.parse_args()
    main(**vars(args))
