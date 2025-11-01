#!/usr/bin/env python3
"""CDF plot of total created files at round 15 per model."""

import argparse
import json

import matplotlib.pyplot as plt

from codeclash.analysis.viz.scatter_codebase_organization import (
    ASSETS_SUBFOLDER,
    DATA_CACHE,
)
from codeclash.analysis.viz.utils import FONT_BOLD, MODEL_TO_COLOR, MODEL_TO_DISPLAY_NAME


def calculate_total_created_files_at_round(data: list, target_round: int = 15) -> dict[str, list[int]]:
    """Calculate total created files at a specific round for each player-tournament."""
    model_to_total_files = {}

    for entry in data:
        player = entry["player"]
        file_history = entry["file_history"]

        # Count files created at or before target_round
        total_files = 0
        for _, history in file_history.items():
            for round_num, op, _, _ in history:
                if op == "created" and round_num <= target_round:
                    total_files += 1
                    break

        if player not in model_to_total_files:
            model_to_total_files[player] = []
        model_to_total_files[player].append(total_files)

    return model_to_total_files


def plot_cdf_total_created_files(model_to_total_files: dict[str, list[int]], target_round: int = 15):
    """Create CDF plot of total created files at target_round per model."""
    plt.figure(figsize=(6, 6))

    for model, total_files_list in sorted(model_to_total_files.items()):
        sorted_files = sorted(total_files_list)
        yvals = [i / len(sorted_files) for i in range(len(sorted_files))]

        plt.step(
            sorted_files,
            yvals,
            label=MODEL_TO_DISPLAY_NAME.get(model, model),
            where="post",
            color=MODEL_TO_COLOR.get(model, "#333333"),
            linewidth=2.5,
        )

    LIM = 100
    plt.xlim(0, LIM)

    FONT_BOLD.set_size(14)
    plt.xticks(range(0, LIM + 1, 10), fontproperties=FONT_BOLD)
    plt.yticks([i / 10 for i in range(11)], [f"{i * 10}%" for i in range(11)], fontproperties=FONT_BOLD)

    FONT_BOLD.set_size(18)
    plt.xlabel(f"Total Created Files at Round {target_round}", fontproperties=FONT_BOLD)
    plt.ylabel("Cumulative Probability", fontproperties=FONT_BOLD)

    # Add minor ticks
    plt.gca().minorticks_on()

    plt.legend(prop=FONT_BOLD)
    plt.grid(True, which="major", alpha=0.6)

    output_file = ASSETS_SUBFOLDER / f"cdf_total_created_files_round{target_round}.pdf"
    plt.savefig(output_file, bbox_inches="tight")
    print(f"Saved CDF plot to {output_file}")


def main():
    parser = argparse.ArgumentParser(description="CDF plot of total created files at a specific round")
    parser.add_argument("--round", type=int, default=15, help="Target round (default: 15)")
    args = parser.parse_args()

    with open(DATA_CACHE) as f:
        print(f"Loading data from {DATA_CACHE}")
        data = [json.loads(line) for line in f]
    print(f"Found {len(data)} player-tournament entries in cache.")

    print(f"\n=== Calculating Total Created Files at Round {args.round} ===")
    model_to_total_files = calculate_total_created_files_at_round(data, target_round=args.round)

    for model, total_files_list in sorted(model_to_total_files.items()):
        print(f"{model}: {len(total_files_list)} tournaments, mean={sum(total_files_list) / len(total_files_list):.1f}")

    print("\n=== Plotting CDF ===")
    plot_cdf_total_created_files(model_to_total_files, target_round=args.round)


if __name__ == "__main__":
    main()
