#!/usr/bin/env python3
"""Plot the cumulative total number of created files vs round."""

import argparse
import json

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.font_manager import FontProperties

from codeclash.analysis.viz.scatter_codebase_organization import (
    ASSETS_SUBFOLDER,
    DATA_CACHE,
)
from codeclash.analysis.viz.utils import FONT_BOLD, MODEL_TO_COLOR, MODEL_TO_DISPLAY_NAME


def calculate_file_counts_by_extension_at_round(data: list, target_round: int = 15) -> pd.DataFrame:
    """Calculate total file counts by extension at a specific round."""
    results = []

    for entry in data:
        player = entry["player"]
        tournament = entry["tournament"]
        file_history = entry["file_history"]

        # Count files by extension that were created at or before target_round
        extension_counts = {}
        for filename, history in file_history.items():
            # Find creation round
            creation_round = None
            for round_num, op, _, _ in history:
                if op == "created":
                    creation_round = round_num
                    break

            if creation_round is not None and creation_round <= target_round:
                # Extract extension
                if "." in filename:
                    ext = filename.rsplit(".", 1)[1]
                else:
                    ext = "no_extension"

                extension_counts[ext] = extension_counts.get(ext, 0) + 1

        # Store result
        result_row = {
            "player": player,
            "tournament": tournament,
        }
        result_row.update(extension_counts)
        results.append(result_row)

    df = pd.DataFrame(results).fillna(0)

    # Aggregate by player (mean across tournaments)
    extension_cols = [col for col in df.columns if col not in ["player", "tournament"]]

    agg_dict = {col: "mean" for col in extension_cols}
    player_agg = df.groupby("player").agg(agg_dict).reset_index()

    # Rename columns to count_<ext>
    rename_dict = {col: f"count_{col}" for col in extension_cols}

    return player_agg.rename(columns=rename_dict)


def calculate_cumulative_created_files_per_round(data: list, max_round: int = 15) -> pd.DataFrame:
    """Calculate cumulative total number of created files per player per round."""
    results = []

    for entry in data:
        player = entry["player"]
        tournament = entry["tournament"]
        file_history = entry["file_history"]

        # Get all creation rounds
        creation_rounds = []
        for _, history in file_history.items():
            for round_num, op, _, _ in history:
                if op == "created":
                    creation_rounds.append(round_num)

        # Calculate cumulative counts per round (up to max_round)
        for round_num in range(max_round + 1):
            cumulative_count = sum(1 for r in creation_rounds if r <= round_num)
            results.append(
                {"player": player, "tournament": tournament, "round": round_num, "total_files": cumulative_count}
            )

    return pd.DataFrame(results)


def filter_outlier_tournaments_by_total_files_99p(created_files_df: pd.DataFrame) -> pd.DataFrame:
    """Filter out player-tournament trajectories above the player's 99th percentile.

    Uses the maximum cumulative total per player-tournament to compute the cutoff,
    mirroring the 99% filtering logic from the bar chart.
    """
    max_totals = (
        created_files_df.groupby(["player", "tournament"], as_index=False)["total_files"]
        .max()
        .rename(columns={"total_files": "max_total_files"})
    )
    q99_per_player = max_totals.groupby("player")["max_total_files"].transform(lambda s: s.quantile(0.99))
    valid_pairs = max_totals[max_totals["max_total_files"] <= q99_per_player][["player", "tournament"]]
    return created_files_df.merge(valid_pairs, on=["player", "tournament"], how="inner")


def plot_total_created_files_over_rounds(created_files_df: pd.DataFrame):
    """Line plot showing cumulative total created files over rounds per model.

    - X: Round number
    - Y: Total number of files created (cumulative, mean across tournaments)
    - One line per model, colored consistently
    """
    # Aggregate by player and round (mean across all tournaments)
    print("------")
    print(created_files_df.groupby(["player"]).agg({"total_files": "max"}).reset_index())
    print("------")
    agg_created = (
        created_files_df
        # .query("total_files < 10_000")  # remove outliers
        .groupby(["player", "round"])
        .agg({"total_files": "mean"})
        .reset_index()
    )

    # Figure styling to match other viz
    plt.figure(figsize=(6, 6))

    # Plot one line per model with consistent color & legend label
    seen_labels = set()
    for player in sorted(agg_created["player"].unique()):
        player_data = agg_created[agg_created["player"] == player]
        color = MODEL_TO_COLOR.get(player, "#333333")
        label = MODEL_TO_DISPLAY_NAME.get(player, player)

        # Avoid duplicate legend entries
        plot_label = label if label not in seen_labels else None
        if plot_label:
            seen_labels.add(label)

        plt.plot(
            player_data["round"],
            player_data["total_files"],
            color=color,
            linewidth=2.5,
            label=plot_label,
            alpha=0.9,
        )

    # Axes labels
    plt.xlabel("Round", fontproperties=FONT_BOLD, fontsize=18)
    plt.ylabel("Total created files", fontproperties=FONT_BOLD, fontsize=18)
    plt.xticks(fontproperties=FONT_BOLD, fontsize=14)
    plt.yticks(fontproperties=FONT_BOLD, fontsize=14)

    # Grid & legend
    plt.grid(True, alpha=0.3)
    legend_font = FontProperties(fname=FONT_BOLD.get_file(), size=14)
    plt.legend(loc="best", prop=legend_font)

    plt.tight_layout()
    OUTPUT_FILE = ASSETS_SUBFOLDER / "line_chart_total_created_files_vs_round.pdf"
    plt.savefig(OUTPUT_FILE, bbox_inches="tight")
    print(f"Saved total created files plot to {OUTPUT_FILE}")


def main():
    data = []
    with open(DATA_CACHE) as f:
        print("Loading data from", DATA_CACHE)
        data = [json.loads(line) for line in f]
    print(f"Found {len(data)} player-tournament entries in cache.")

    print("\n=== Calculating File Counts by Extension at Round 15 ===")
    extension_counts_df = calculate_file_counts_by_extension_at_round(data, target_round=15)
    print(extension_counts_df)
    output_csv = ASSETS_SUBFOLDER / "file_counts_by_extension_round15.csv"
    extension_counts_df.to_csv(output_csv, index=False)
    print(f"Saved file counts by extension to {output_csv}")

    print("\n=== Calculating Cumulative Created Files Per Round ===")
    created_files_df = calculate_cumulative_created_files_per_round(data)
    print(created_files_df.head(20))
    # Apply 99% per-player filtering (mirrors bar chart logic)
    created_files_df = filter_outlier_tournaments_by_total_files_99p(created_files_df)

    print("\n=== Plotting Total Created Files Over Rounds ===")
    plot_total_created_files_over_rounds(created_files_df)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Plot cumulative total created files vs round")
    args = parser.parse_args()
    main()
