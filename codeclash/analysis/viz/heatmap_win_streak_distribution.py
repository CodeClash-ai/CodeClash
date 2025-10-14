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

OUTPUT_FILE = ASSETS_DIR / "heatmap_win_streak_distribution.png"


def main(log_dir: Path, xlim: int = 15):
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

    max_streaks = []
    for model in models:
        streaks = win_streaks[model]
        max_streaks.append(max(streaks) if streaks else 0)

    # Use xlim as the display maximum
    display_columns = xlim
    streak_matrix = np.zeros((len(models), display_columns))

    for i, model in enumerate(models):
        streaks = win_streaks[model]
        for streak_len in streaks:
            if streak_len < xlim:
                streak_matrix[i, streak_len - 1] += 1
            else:
                # Aggregate all streaks >= xlim into the last column
                streak_matrix[i, xlim - 1] += 1

    # Normalize by total streaks for each model
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
            if streak_len < xlim:
                absolute_counts[i, streak_len - 1] += 1
            else:
                # Aggregate all streaks >= xlim into the last column
                absolute_counts[i, xlim - 1] += 1

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

    plt.xlabel("Win Streak Length", fontproperties=FONT_BOLD, fontsize=18)

    # Create x-axis labels with the last one as "xlim+"
    x_labels = [str(i) for i in range(1, xlim)] + [f"{xlim}+"]
    plt.xticks(range(display_columns), x_labels, fontproperties=FONT_BOLD, fontsize=14)
    plt.yticks(range(len(models)), [MODEL_TO_DISPLAY_NAME[m] for m in models], fontproperties=FONT_BOLD, fontsize=14)
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
