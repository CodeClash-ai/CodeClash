#!/usr/bin/env python3
import argparse
import json
from collections import defaultdict
from pathlib import Path

import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np
from tqdm import tqdm

from codeclash.constants import LOCAL_LOG_DIR


def main(log_dir: Path):
    print(f"Creating win rate heatmap from logs in {log_dir}...")

    # Track round-level wins: (model1, model2) -> [wins, total_rounds]
    results = defaultdict(lambda: [0, 0])

    for metadata_file in tqdm(list(log_dir.rglob("metadata.json"))):
        try:
            metadata = json.load(open(metadata_file))
            p2m = {x["name"]: x["config"]["model"]["model_name"].strip("@") for x in metadata["config"]["players"]}

            if len(p2m) != 2:
                continue

            # Process each round (skip round 0)
            for round_id, round_data in metadata["round_stats"].items():
                if round_id == "0":
                    continue

                winner = round_data.get("winner")
                if winner in p2m:
                    winner_model = p2m[winner]
                    loser_model = next(m for m in p2m.values() if m != winner_model)

                    results[(winner_model, loser_model)][0] += 1  # win
                    results[(winner_model, loser_model)][1] += 1  # total
                    results[(loser_model, winner_model)][1] += 1  # total for loser
        except:
            continue

    # Build matrix
    models = sorted({m for pair in results.keys() for m in pair})
    clean_names = [m.split("/")[-1] for m in models]
    n = len(models)

    matrix = np.full((n, n), np.nan)
    for i, m1 in enumerate(models):
        for j, m2 in enumerate(models):
            if i != j and results[(m1, m2)][1] > 0:
                matrix[i, j] = results[(m1, m2)][0] / results[(m1, m2)][1]

    # Plot
    fig, ax = plt.subplots(figsize=(10, 8))
    cmap = mcolors.LinearSegmentedColormap.from_list("br", ["#3498db", "#ffffff", "#e74c3c"])

    masked = np.ma.masked_where(np.isnan(matrix), matrix)
    im = ax.imshow(masked, cmap=cmap, vmin=0, vmax=1)

    # Add percentages
    for i in range(n):
        for j in range(n):
            if not np.isnan(matrix[i, j]):
                color = "white" if abs(matrix[i, j] - 0.5) > 0.3 else "black"
                ax.text(j, i, f"{matrix[i, j]:.0%}", ha="center", va="center", color=color, fontweight="bold")

    ax.set_xticks(range(n))
    ax.set_yticks(range(n))
    ax.set_xticklabels(clean_names, rotation=45, ha="right")
    ax.set_yticklabels(clean_names)
    ax.set_title("Model Win Rate Heatmap (Round Level)\n(Row beats Column)", fontsize=14, fontweight="bold")

    plt.colorbar(im, label="Win Rate")
    plt.tight_layout()
    plt.savefig("heatmap_win_rates.png", dpi=300, bbox_inches="tight")
    print("Heatmap saved to heatmap_win_rates.png")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create model win rate heatmap")
    parser.add_argument("-d", "--log_dir", type=Path, default=LOCAL_LOG_DIR, help="Path to logs")
    args = parser.parse_args()
    main(args.log_dir)
