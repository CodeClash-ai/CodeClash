#!/usr/bin/env python3
"""
Winner's Share Analysis: Compare winner dominance between 2-player and N-player tournaments.

Shows that multi-player tournaments are more competitive with winners capturing a smaller
percentage of total points.
"""

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from codeclash.analysis.viz.utils import ASSETS_DIR, FONT_BOLD
from codeclash.constants import LOCAL_LOG_DIR


def calculate_winner_share(metadata_path: Path, num_players: int) -> list[float]:
    """Calculate winner's share of total points for each round in a tournament."""
    with open(metadata_path) as f:
        metadata = json.load(f)

    winner_shares = []

    for round_id, stats in metadata.get("round_stats", {}).items():
        if round_id == "0":
            continue

        scores = stats.get("scores", {})
        # Filter out "Tie" key if present
        scores = {k: v for k, v in scores.items() if k != "Tie"}

        if len(scores) != num_players:
            continue

        score_values = list(scores.values())
        total_score = sum(score_values)
        max_score = max(score_values)

        if total_score > 0:
            winner_share = max_score / total_score * 100
            winner_shares.append(winner_share)

    return winner_shares


def analyze_winner_share(log_dir: Path, game_pattern: str = "CoreWar.r15.s1000"):
    """Compare winner's share between 2-player and multi-player tournaments."""

    # Collect 2-player data
    print("Analyzing 2-player tournaments...")
    winner_shares_2p = []
    for metadata_path in log_dir.rglob(f"*{game_pattern}.p2.*/metadata.json"):
        winner_shares_2p.extend(calculate_winner_share(metadata_path, num_players=2))

    # Collect 6-player data
    print("Analyzing 6-player tournaments...")
    winner_shares_6p = []
    for metadata_path in log_dir.rglob(f"*{game_pattern}.p6.*/metadata.json"):
        winner_shares_6p.extend(calculate_winner_share(metadata_path, num_players=6))

    # Print statistics
    print("\n" + "=" * 70)
    print("WINNER'S SHARE COMPARISON")
    print("=" * 70)

    print("\n2-Player Tournaments:")
    print(f"  Mean: {np.mean(winner_shares_2p):.1f}%")
    print(f"  Median: {np.median(winner_shares_2p):.1f}%")
    print(f"  Range: {np.min(winner_shares_2p):.1f}% - {np.max(winner_shares_2p):.1f}%")
    print(f"  Samples: {len(winner_shares_2p)}")

    print("\n6-Player Tournaments:")
    print(f"  Mean: {np.mean(winner_shares_6p):.1f}%")
    print(f"  Median: {np.median(winner_shares_6p):.1f}%")
    print(f"  Range: {np.min(winner_shares_6p):.1f}% - {np.max(winner_shares_6p):.1f}%")
    print(f"  Samples: {len(winner_shares_6p)}")

    print("\n" + "=" * 70)
    print("KEY INSIGHT")
    print("=" * 70)
    ratio = np.mean(winner_shares_2p) / np.mean(winner_shares_6p)
    print(f"""
In 6-player tournaments, the winner captures only {np.mean(winner_shares_6p):.1f}% of total points
on average, compared to {np.mean(winner_shares_2p):.1f}% in 2-player tournaments.

This means 6-player games are MUCH less dominated by a single winner - victories
are more competitive and less clear-cut ({ratio:.2f}x less dominant).

👉 Bottom line: Multi-player tournaments show MORE COMPETITIVE BALANCE and LESS
   WINNER DOMINANCE than 2-player head-to-head matches.
""")

    # Create visualization
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    # Plot 1: Histogram comparison
    ax1 = axes[0]
    ax1.hist(winner_shares_6p, bins=20, alpha=0.7, label="6-Player", color="steelblue", edgecolor="black")
    ax1.hist(winner_shares_2p, bins=20, alpha=0.7, label="2-Player", color="coral", edgecolor="black")
    ax1.axvline(
        np.mean(winner_shares_6p),
        color="steelblue",
        linestyle="--",
        linewidth=2,
        label=f"6P Mean: {np.mean(winner_shares_6p):.1f}%",
    )
    ax1.axvline(
        np.mean(winner_shares_2p),
        color="coral",
        linestyle="--",
        linewidth=2,
        label=f"2P Mean: {np.mean(winner_shares_2p):.1f}%",
    )
    ax1.set_xlabel("Winner's Share of Total Points (%)", fontsize=18, fontproperties=FONT_BOLD)
    ax1.set_ylabel("Frequency", fontsize=18, fontproperties=FONT_BOLD)
    ax1.tick_params(axis="both", labelsize=14)
    ax1.legend(prop=FONT_BOLD, fontsize=12)
    ax1.grid(alpha=0.3)

    # Plot 2: Box plot comparison
    ax2 = axes[1]
    bp = ax2.boxplot(
        [winner_shares_6p, winner_shares_2p], tick_labels=["6-Player", "2-Player"], patch_artist=True, widths=0.6
    )
    bp["boxes"][0].set_facecolor("steelblue")
    bp["boxes"][1].set_facecolor("coral")
    ax2.set_ylabel("Winner's Share of Total Points (%)", fontsize=18, fontproperties=FONT_BOLD)
    ax2.tick_params(axis="both", labelsize=14)
    ax2.grid(axis="y", alpha=0.3)

    # Add mean markers
    for i, data in enumerate([winner_shares_6p, winner_shares_2p], 1):
        ax2.plot(i, np.mean(data), "D", color="darkred", markersize=8, label="Mean" if i == 1 else "")
    ax2.legend(prop=FONT_BOLD, fontsize=12)

    # Set tick labels with custom font
    for label in ax2.get_xticklabels():
        label.set_fontproperties(FONT_BOLD)

    plt.tight_layout()
    output_file = ASSETS_DIR / "winner_share_comparison.png"
    plt.savefig(output_file, dpi=300, bbox_inches="tight")
    print(f"\nVisualization saved to: {output_file}")
    plt.close()

    return {"2p": winner_shares_2p, "6p": winner_shares_6p}


def main():
    analyze_winner_share(LOCAL_LOG_DIR)


if __name__ == "__main__":
    main()
