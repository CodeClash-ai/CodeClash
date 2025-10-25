#!/usr/bin/env python3
"""
Win Change Rate Analysis: Measure how often the winner changes between consecutive rounds.

Shows that multi-player tournaments are more volatile with more frequent lead changes
compared to 2-player tournaments.
"""

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from codeclash.analysis.viz.utils import ASSETS_DIR, FONT_BOLD
from codeclash.constants import LOCAL_LOG_DIR


def calculate_lead_changes(metadata_path: Path) -> dict:
    """Calculate how often the winner changes between consecutive rounds."""
    with open(metadata_path) as f:
        metadata = json.load(f)

    # Extract winners in order
    winners = []
    for round_id in sorted([int(k) for k in metadata.get("round_stats", {}).keys() if k != "0"]):
        stats = metadata["round_stats"][str(round_id)]
        winner = stats.get("winner")
        if winner:
            winners.append(winner)

    if len(winners) < 2:
        return None

    # Count changes
    changes = sum(1 for i in range(1, len(winners)) if winners[i] != winners[i - 1])
    total_transitions = len(winners) - 1
    change_rate = (changes / total_transitions * 100) if total_transitions > 0 else 0

    return {"total_rounds": len(winners), "lead_changes": changes, "change_rate": change_rate}


def analyze_win_change_rate(log_dir: Path, game_pattern: str = "CoreWar.r15.s1000"):
    """Compare lead change rates between 2-player and multi-player tournaments."""

    # Collect 2-player data
    print("Analyzing 2-player tournaments...")
    lead_changes_2p = []
    for metadata_path in log_dir.rglob(f"*{game_pattern}.p2.*/metadata.json"):
        result = calculate_lead_changes(metadata_path)
        if result:
            lead_changes_2p.append(result)

    # Collect 6-player data
    print("Analyzing 6-player tournaments...")
    lead_changes_6p = []
    for metadata_path in log_dir.rglob(f"*{game_pattern}.p6.*/metadata.json"):
        result = calculate_lead_changes(metadata_path)
        if result:
            lead_changes_6p.append(result)

    # Extract change rates
    change_rates_2p = [x["change_rate"] for x in lead_changes_2p]
    change_rates_6p = [x["change_rate"] for x in lead_changes_6p]

    lead_count_2p = [x["lead_changes"] for x in lead_changes_2p]
    lead_count_6p = [x["lead_changes"] for x in lead_changes_6p]

    # Print statistics
    print("\n" + "=" * 70)
    print("LEAD CHANGES COMPARISON")
    print("=" * 70)

    print("\n2-Player Tournaments:")
    print(f"  Tournaments analyzed: {len(lead_changes_2p)}")
    print(f"  Average lead changes: {np.mean(lead_count_2p):.1f} per tournament")
    print(f"  Average change rate: {np.mean(change_rates_2p):.1f}%")
    print(f"  Median: {np.median(lead_count_2p):.0f} changes")
    print(f"  Range: {np.min(lead_count_2p):.0f} - {np.max(lead_count_2p):.0f}")

    print("\n6-Player Tournaments:")
    print(f"  Tournaments analyzed: {len(lead_changes_6p)}")
    print(f"  Average lead changes: {np.mean(lead_count_6p):.1f} per tournament")
    print(f"  Average change rate: {np.mean(change_rates_6p):.1f}%")
    print(f"  Median: {np.median(lead_count_6p):.0f} changes")
    print(f"  Range: {np.min(lead_count_6p):.0f} - {np.max(lead_count_6p):.0f}")

    print("\n" + "=" * 70)
    print("KEY INSIGHT")
    print("=" * 70)
    ratio = np.mean(change_rates_6p) / np.mean(change_rates_2p)
    print(f"""
Lead change rate:
  • 6-Player: {np.mean(change_rates_6p):.1f}% of round transitions
  • 2-Player: {np.mean(change_rates_2p):.1f}% of round transitions

💡 Insight: 6-player tournaments are {ratio:.2f}x MORE VOLATILE!
   The lead changes {ratio:.2f}x as often in 6-player vs 2-player tournaments.

👉 Bottom line: Multi-player tournaments are much more dynamic and competitive,
   with no single player maintaining dominance throughout the tournament.
""")

    # Create visualization
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    # Plot 1: Distribution of lead changes
    ax1 = axes[0]
    ax1.hist(lead_count_6p, bins=15, alpha=0.7, label="6-Player", color="steelblue", edgecolor="black")
    ax1.hist(lead_count_2p, bins=15, alpha=0.7, label="2-Player", color="coral", edgecolor="black")
    ax1.axvline(
        np.mean(lead_count_6p),
        color="steelblue",
        linestyle="--",
        linewidth=2,
        label=f"6P Mean: {np.mean(lead_count_6p):.1f}",
    )
    ax1.axvline(
        np.mean(lead_count_2p),
        color="coral",
        linestyle="--",
        linewidth=2,
        label=f"2P Mean: {np.mean(lead_count_2p):.1f}",
    )
    ax1.set_xlabel("Number of Lead Changes per Tournament", fontsize=18, fontproperties=FONT_BOLD)
    ax1.set_ylabel("Frequency", fontsize=18, fontproperties=FONT_BOLD)
    ax1.tick_params(axis="both", labelsize=14)
    ax1.legend(prop=FONT_BOLD, fontsize=12)
    ax1.grid(alpha=0.3)

    # Plot 2: Change rates comparison
    ax2 = axes[1]
    bp = ax2.boxplot(
        [change_rates_6p, change_rates_2p], tick_labels=["6-Player", "2-Player"], patch_artist=True, widths=0.6
    )
    bp["boxes"][0].set_facecolor("steelblue")
    bp["boxes"][1].set_facecolor("coral")
    ax2.set_ylabel("Lead Change Rate (%)", fontsize=18, fontproperties=FONT_BOLD)
    ax2.tick_params(axis="both", labelsize=14)
    ax2.grid(axis="y", alpha=0.3)

    # Add mean markers
    for i, data in enumerate([change_rates_6p, change_rates_2p], 1):
        ax2.plot(i, np.mean(data), "D", color="darkred", markersize=8, label="Mean" if i == 1 else "")
    ax2.legend(prop=FONT_BOLD, fontsize=12)

    # Set tick labels with custom font
    for label in ax2.get_xticklabels():
        label.set_fontproperties(FONT_BOLD)

    plt.tight_layout()
    output_file = ASSETS_DIR / "win_change_rate_comparison.png"
    plt.savefig(output_file, dpi=300, bbox_inches="tight")
    print(f"\nVisualization saved to: {output_file}")
    plt.close()

    return {"2p": lead_changes_2p, "6p": lead_changes_6p}


def main():
    analyze_win_change_rate(LOCAL_LOG_DIR)


if __name__ == "__main__":
    main()
