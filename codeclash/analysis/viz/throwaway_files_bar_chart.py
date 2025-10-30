#!/usr/bin/env python3
"""Calculate and plot the average number of throwaway files per model.

A throwaway file is defined as any file that is created in round < 15 and not used again.
"""

import argparse
import json

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.font_manager import FontProperties
from matplotlib.patches import Patch
from matplotlib.ticker import AutoMinorLocator

from codeclash.analysis.viz.scatter_codebase_organization import (
    ASSETS_SUBFOLDER,
    DATA_CACHE,
)
from codeclash.analysis.viz.utils import FONT_BOLD, MODEL_TO_COLOR, MODEL_TO_DISPLAY_NAME


def get_text_color_for_background(hex_color: str) -> str:
    """Return 'white' for dark backgrounds, 'black' for light backgrounds."""
    hex_color = hex_color.lstrip("#")
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    # Calculate relative luminance
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    return "white" if luminance < 0.5 else "black"


def calculate_throwaway_files(file_history: dict, threshold_round: int = 15) -> tuple[int, int]:
    """Calculate the number of throwaway files at root and elsewhere.

    A throwaway file is one that is created in round i < threshold_round and never used in any round > i.

    Args:
        file_history: dict mapping filenames to [(round, op, added, removed), ...]
        threshold_round: Round threshold (files created in this round or later are excluded)

    Returns:
        tuple of (root_count, non_root_count)
    """
    root_count = 0
    non_root_count = 0

    for filename, history in file_history.items():
        if not history:
            continue

        # Find creation round
        creation_round = None
        for round_num, op, _, _ in history:
            if op == "created":
                creation_round = round_num
                break
        else:
            print(f"File {filename} was never created")
            continue

        # Skip files not created before threshold
        if creation_round >= threshold_round:
            continue

        # Check if file was ever touched after creation round
        # Look for any operation (modified, referenced, renamed, deleted) in rounds > creation_round
        used_after_creation = False
        for round_num, _, _, _ in history:
            if round_num > creation_round:
                used_after_creation = True
                break

        if not used_after_creation:
            # Check if file is at root level (no "/" in path)
            if "/" not in filename:
                root_count += 1
            else:
                non_root_count += 1

    return root_count, non_root_count


def analyze_throwaway_files_per_player(data: list, threshold_round: int = 15) -> pd.DataFrame:
    """Calculate throwaway files per player, averaged across tournaments."""
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
                "root_throwaway": root_count,
                "non_root_throwaway": non_root_count,
                "total_throwaway": root_count + non_root_count,
            }
        )
        print(f"{player} {tournament}: {root_count} root, {non_root_count} non-root throwaway files")

    df = pd.DataFrame(results)
    # Remove outliers above the 99th percentile of total_throwaway per player
    q99_per_player = df.groupby("player")["total_throwaway"].transform(lambda s: s.quantile(0.99))
    df = df[df["total_throwaway"] <= q99_per_player]

    # Aggregate means only
    return df.groupby("player", as_index=False).agg(
        root_mean=("root_throwaway", "mean"),
        non_root_mean=("non_root_throwaway", "mean"),
        total_mean=("total_throwaway", "mean"),
    )


def plot_throwaway_files_bar_chart(throwaway_df: pd.DataFrame):
    """Stacked horizontal bar chart showing throwaway files at root vs elsewhere per model.

    - Y: Model name (alphabetically ordered)
    - X: Average number of throwaway files (stacked: root + elsewhere)

    Args:
        throwaway_df: DataFrame with statistics per player
    """
    plt.figure(figsize=(6, 6))

    # Get sorted models alphabetically (reversed)
    sorted_df = throwaway_df.sort_values("player", ascending=False)

    # Prepare data
    models = []
    root_values = []
    non_root_values = []
    colors = []

    root_col = "root_mean"
    non_root_col = "non_root_mean"

    for _, row in sorted_df.iterrows():
        model_key = row["player"]
        display_name = MODEL_TO_DISPLAY_NAME.get(model_key, model_key)
        color = MODEL_TO_COLOR.get(model_key, "#333333")

        models.append(display_name)
        root_values.append(row[root_col])
        non_root_values.append(row[non_root_col])
        colors.append(color)

    # Create stacked horizontal bar chart
    y_pos = np.arange(len(models))

    # First bar: root throwaway files
    plt.barh(y_pos, root_values, color=colors, alpha=0.8, edgecolor=colors, linewidth=0)

    # Second bar: non-root throwaway files (stacked on top of first)
    plt.barh(y_pos, non_root_values, left=root_values, color=colors, alpha=0.5, edgecolor=colors, linewidth=0)

    # Add value labels inside bars and totals at the end
    for i, (root_val, non_root_val, color) in enumerate(zip(root_values, non_root_values, colors)):
        total = root_val + non_root_val
        # Determine text color based on background (root section has alpha=0.8)
        root_text_color = get_text_color_for_background(color)
        # Non-root section has alpha=0.5 (lighter), so use black text
        non_root_text_color = "black"

        # Label for root section
        if root_val > 2:
            plt.text(
                root_val / 2,
                i,
                f"{root_val:.1f}",
                ha="center",
                va="center",
                fontproperties=FONT_BOLD,
                fontsize=14,
                color=root_text_color,
            )
        # Label for non-root section (lighter background with alpha=0.5)
        if non_root_val > 2:
            plt.text(
                root_val + non_root_val / 2,
                i,
                f"{non_root_val:.1f}",
                ha="center",
                va="center",
                fontproperties=FONT_BOLD,
                fontsize=14,
                color=non_root_text_color,
            )
        # Total at the end of bar
        plt.text(
            total + 0.3, i, f"{total:.1f}", ha="left", va="center", fontproperties=FONT_BOLD, fontsize=14, color="black"
        )

    # Set xlim to give 10% extra space for the numbers
    max_total = max(r + nr for r, nr in zip(root_values, non_root_values))
    plt.xlim(0, max_total * 1.15)

    # Styling
    plt.xlabel("Throwaway Files per Tournament", fontproperties=FONT_BOLD, fontsize=18)
    plt.yticks(y_pos, models, fontproperties=FONT_BOLD, fontsize=14)
    plt.xticks(fontproperties=FONT_BOLD, fontsize=14)
    plt.gca().xaxis.set_minor_locator(AutoMinorLocator())
    plt.grid(True, alpha=0.3, axis="x")

    # Custom legend with grey colors
    legend_elements = [Patch(facecolor="#555555", label="At repo root"), Patch(facecolor="#AAAAAA", label="Elsewhere")]
    legend_font = FontProperties(fname=FONT_BOLD.get_file(), size=14)
    plt.legend(handles=legend_elements, prop=legend_font, loc="lower right")

    plt.tight_layout()
    OUTPUT_FILE = ASSETS_SUBFOLDER / "bar_chart_throwaway_files_mean.pdf"
    plt.savefig(OUTPUT_FILE, bbox_inches="tight")
    print(f"Saved throwaway files bar chart (Mean) to {OUTPUT_FILE}")


def main(refresh_cache: bool = False, threshold_round: int = 15):
    # build_data_structure(refresh_cache)

    data = []
    with open(DATA_CACHE) as f:
        print("loading data from", DATA_CACHE)
        data = [json.loads(line) for line in f]
    print(f"Found {len(data)} player-tournament entries in cache.")
    # print(data)

    print(f"\n=== Throwaway Files Per Player (threshold: round {threshold_round}) ===")
    throwaway_df = analyze_throwaway_files_per_player(data, threshold_round=threshold_round)
    print(throwaway_df)
    throwaway_df.to_csv(ASSETS_SUBFOLDER / "throwaway_files_per_player.csv", index=False)

    print("\n=== Plotting Throwaway Files Bar Charts ===")
    plot_throwaway_files_bar_chart(throwaway_df)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Calculate and plot throwaway files per model")
    parser.add_argument("-r", "--refresh-cache", action="store_true", help="Refresh the cache")
    parser.add_argument("-t", "--threshold-round", type=int, default=15, help="Round threshold for early files")
    args = parser.parse_args()
    main(**vars(args))
