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


def main(log_dir: Path, unit: str = "rounds", output_file: Path = ASSETS_DIR / "heatmap_win_rates.png"):
    print(f"Creating win rate heatmap from logs in {log_dir}...")

    # Track round-level wins: (model1, model2) -> [wins, total_rounds]
    results = defaultdict(lambda: [0, 0])

    for metadata_file in tqdm(list(log_dir.rglob("metadata.json"))):
        try:
            metadata = json.load(open(metadata_file))
            p2m = {
                x["name"]: x["config"]["model"]["model_name"].strip("@").split("/")[-1]
                for x in metadata["config"]["players"]
            }

            if len(p2m) != 2:
                continue

            # Process each round (skip round 0)
            tracker = defaultdict(int)
            for round_id, round_data in metadata["round_stats"].items():
                if round_id == "0":
                    continue

                winner = round_data.get("winner")
                if winner in p2m:
                    winner_model = p2m[winner]
                    loser_model = next(m for m in p2m.values() if m != winner_model)

                    if unit == "rounds":
                        results[(winner_model, loser_model)][0] += 1  # win
                        results[(winner_model, loser_model)][1] += 1  # total
                        results[(loser_model, winner_model)][1] += 1  # total for loser
                    elif unit == "tournaments":
                        tracker[winner_model] += 1

            if unit == "tournaments":
                winner = max(tracker, key=tracker.get)
                loser = min(tracker, key=tracker.get)
                results[(winner, loser)][0] += 1  # win
                results[(winner, loser)][1] += 1  # total
                results[(loser, winner)][1] += 1  # total for loser
        except:
            continue

    # Build matrix
    models = sorted({m for pair in results.keys() for m in pair})
    clean_names = [MODEL_TO_DISPLAY_NAME[m.split("/")[-1]] for m in models]
    n = len(models)

    matrix = np.full((n, n), np.nan)
    for i, m1 in enumerate(models):
        for j, m2 in enumerate(models):
            if i != j and results[(m1, m2)][1] > 0:
                matrix[i, j] = results[(m1, m2)][0] / results[(m1, m2)][1]

    # Plot
    FONT_BOLD.set_size(18)
    _, ax = plt.subplots(figsize=(10, 8))
    cmap = mcolors.LinearSegmentedColormap.from_list("br", ["#e74c3c", "#ffffff", "#3498db"])
    masked = np.ma.masked_where(np.isnan(matrix), matrix)
    ax.imshow(masked, cmap=cmap, vmin=0, vmax=1)

    # Add percentages
    for i in range(n):
        for j in range(n):
            if not np.isnan(matrix[i, j]):
                color = "white" if abs(matrix[i, j] - 0.5) > 0.3 else "black"
                ax.text(
                    j,
                    i,
                    f"{matrix[i, j]:.0%}",
                    ha="center",
                    va="center",
                    color=color,
                    fontweight="bold",
                    fontproperties=FONT_BOLD,
                )

    ax.set_xticks(range(n))
    ax.set_yticks(range(n))
    ax.set_xticklabels(clean_names, rotation=45, ha="right", fontproperties=FONT_BOLD)
    ax.set_yticklabels(clean_names, fontproperties=FONT_BOLD)

    # plt.colorbar(im, label="Win Rate")
    plt.tight_layout()
    if unit == "tournaments":
        suffix = output_file.suffix or ".png"
        output_file = output_file.with_name(f"{output_file.stem}_tournaments{suffix}")
    plt.savefig(output_file, dpi=300, bbox_inches="tight")
    print(f"Heatmap saved to {output_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create model win rate heatmap")
    parser.add_argument("-d", "--log_dir", type=Path, default=LOCAL_LOG_DIR, help="Path to logs")
    parser.add_argument("-u", "--unit", type=str, default="rounds", help="Unit of analysis: rounds or tournaments")
    parser.add_argument(
        "-o", "--output_file", type=Path, default=ASSETS_DIR / "heatmap_win_rates.png", help="Output file path"
    )
    args = parser.parse_args()
    main(**vars(args))
