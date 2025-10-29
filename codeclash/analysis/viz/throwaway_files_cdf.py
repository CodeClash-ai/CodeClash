#!/usr/bin/env python3
"""Plot CDF of total throwaway files per tournament for each model."""

import argparse
import json

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.font_manager import FontProperties
from matplotlib.ticker import AutoMinorLocator

from codeclash.analysis.viz.scatter_codebase_organization import (
    ASSETS_SUBFOLDER,
    DATA_CACHE,
)
from codeclash.analysis.viz.throwaway_files_bar_chart import calculate_throwaway_files
from codeclash.analysis.viz.utils import FONT_BOLD, MODEL_TO_COLOR, MODEL_TO_DISPLAY_NAME


def analyze_total_throwaway_per_player(data: list, threshold_round: int = 15) -> pd.DataFrame:
    results = []
    for entry in data:
        player = entry["player"]
        tournament = entry["tournament"]
        file_history = entry["file_history"]

        root_count, non_root_count = calculate_throwaway_files(file_history, threshold_round=threshold_round)
        results.append(
            {
                "player": player,
                "tournament": tournament,
                "total_throwaway": root_count + non_root_count,
            }
        )

    return pd.DataFrame(results)


def plot_throwaway_cdf(df: pd.DataFrame) -> None:
    plt.figure(figsize=(7, 6))

    # Plot empirical CDF for each model
    for player, group in df.groupby("player"):
        values = np.sort(group["total_throwaway"].to_numpy())
        if values.size == 0:
            continue
        y = np.arange(1, values.size + 1) / values.size
        color = MODEL_TO_COLOR.get(player, "#333333")
        label = MODEL_TO_DISPLAY_NAME.get(player, player)
        plt.step(values, y, where="post", label=label, color=color, linewidth=2, alpha=0.9)

    plt.xlabel("Total throwaway files per tournament", fontproperties=FONT_BOLD, fontsize=18)
    plt.ylabel("Cumulative fraction", fontproperties=FONT_BOLD, fontsize=18)
    plt.xticks(fontproperties=FONT_BOLD, fontsize=14)
    plt.yticks(fontproperties=FONT_BOLD, fontsize=14)
    plt.gca().xaxis.set_minor_locator(AutoMinorLocator())
    plt.xlim(0, 200)
    plt.grid(True, alpha=0.3, axis="both")

    legend_font = FontProperties(fname=FONT_BOLD.get_file(), size=12)
    plt.legend(prop=legend_font, loc="lower right", frameon=True)

    plt.tight_layout()
    output_file = ASSETS_SUBFOLDER / "cdf_throwaway_files_per_model.pdf"
    plt.savefig(output_file, bbox_inches="tight")
    print(f"Saved throwaway files CDF to {output_file}")


def main(refresh_cache: bool = False, threshold_round: int = 15) -> None:
    data = []
    with open(DATA_CACHE) as f:
        print("loading data from", DATA_CACHE)
        data = [json.loads(line) for line in f]
    print(f"Found {len(data)} player-tournament entries in cache.")

    df = analyze_total_throwaway_per_player(data, threshold_round=threshold_round)
    print("\n=== Throwaway totals per player (raw, no filtering) ===")
    print(df.head())

    plot_throwaway_cdf(df)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Plot CDF of throwaway files per tournament for each model")
    parser.add_argument("-r", "--refresh-cache", action="store_true", help="Refresh the cache")
    parser.add_argument(
        "-t",
        "--threshold-round",
        type=int,
        default=15,
        help="Round threshold for early files",
    )
    args = parser.parse_args()
    main(**vars(args))
