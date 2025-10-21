#!/usr/bin/env python3
"""
Model Resiliency Analysis: Round-to-Round Recovery Rate by Deficit Size

This script analyzes how well different AI models recover in the immediate next round
after losing by various margins. It measures direct bounce-back ability.

Key Metrics:
- Deficit Size: Calculated per-round as (winner_score - loser_score) / (winner_score + loser_score) * 100
  This represents the losing margin as a percentage of total round outcomes.
- Recovery Success: Whether a model that lost round N wins round N+1
- Success Rate: Percentage of successful immediate recoveries for each deficit range

Visualization:
- Line chart showing deficit size (x-axis) vs next-round win rate (y-axis)
- Separate line for each model to compare resilience patterns

Insights:
- Identifies models with strong bounce-back ability vs those that struggle after losses
- Shows deficit sizes from which models can typically recover vs those that cause continued struggle
- Reveals model-specific patterns in immediate resilience and recovery
"""

import argparse
import glob
import json
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
from tqdm import tqdm

from codeclash.analysis.viz.utils import ASSETS_DIR, FONT_BOLD, MODEL_TO_COLOR, MODEL_TO_DISPLAY_NAME

DEFICIT_RANGES = [
    (0, 10),  # 0-10% deficit
    (10, 20),  # 10-20% deficit
    (20, 30),  # 20-30% deficit
    (30, 50),  # 30-50% deficit
    (50, 100),  # 50%+ deficit
]

OUTPUT_FILE = ASSETS_DIR / "line_chart_model_resiliency.png"


def load_tournament_metadata(metadata_path):
    """Load tournament metadata from JSON file."""
    try:
        with open(metadata_path) as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"Warning: Could not load {metadata_path}: {e}")
        return None


def identify_deficit_and_recovery_situations(rounds_data, players):
    """
    Identify situations where a player lost a round and track if they won the next round.

    Deficit is calculated per-round as: (winner_score - loser_score) / (winner_score + loser_score) * 100
    This represents the losing margin as a percentage of total round outcomes.

    Args:
        rounds_data: Dictionary mapping round numbers to round data
        players: List of player names (should be exactly 2 for PvP)

    Returns:
        List of tuples: (round_num, losing_player, deficit_percentage, won_next_round)
    """
    recovery_situations = []
    sorted_round_nums = sorted(int(k) for k in rounds_data.keys())

    # Process each round and check the next round for recovery
    for i, round_num in enumerate(sorted_round_nums):
        round_data = rounds_data[str(round_num)]

        # Get scores for both players in this round
        if len(players) != 2:
            continue  # Skip if not exactly 2 players

        player1, player2 = players
        score1 = round_data["player_stats"].get(player1, {}).get("score", 0)
        score2 = round_data["player_stats"].get(player2, {}).get("score", 0)

        total_score = score1 + score2

        if total_score == 0:
            continue  # Skip rounds with no scoring

        # Identify winner and loser of this round
        if score1 > score2:
            winner_score = score1
            loser_score = score2
            losing_player = player2
            # winning_player = player1
        elif score2 > score1:
            winner_score = score2
            loser_score = score1
            losing_player = player1
            # winning_player = player2
        else:
            continue  # Skip tied rounds

        # Calculate deficit as losing margin percentage
        deficit_percentage = ((winner_score - loser_score) / total_score) * 100

        # Check if there's a next round
        if i + 1 < len(sorted_round_nums):
            next_round_num = sorted_round_nums[i + 1]
            next_round_data = rounds_data[str(next_round_num)]

            # Check who won the next round
            next_score1 = next_round_data["player_stats"].get(player1, {}).get("score", 0)
            next_score2 = next_round_data["player_stats"].get(player2, {}).get("score", 0)
            next_total = next_score1 + next_score2

            # Did the loser of this round win the next round?
            won_next_round = False
            if next_total > 0:  # Only if next round had scoring
                if losing_player == player1 and next_score1 > next_score2:
                    won_next_round = True
                elif losing_player == player2 and next_score2 > next_score1:
                    won_next_round = True

            recovery_situations.append((round_num, losing_player, deficit_percentage, won_next_round))

    return recovery_situations


def analyze_tournament_directory(log_dir):
    """
    Analyze all tournaments in a directory for round-to-round recovery patterns.

    Args:
        log_dir: Path to directory containing tournament logs

    Returns:
        Aggregated recovery success rate data (next-round win rate after losses)
    """
    metadata_files = glob.glob(str(log_dir / "**/metadata.json"), recursive=True)

    # Aggregate data across all tournaments
    all_recovery_data = defaultdict(lambda: defaultdict(lambda: {"attempts": 0, "successes": 0}))
    processed_tournaments = 0

    print(f"Found {len(metadata_files)} metadata files")

    for metadata_path in tqdm(metadata_files, desc="Processing tournaments"):
        metadata = load_tournament_metadata(metadata_path)
        if not metadata or "round_stats" not in metadata:
            continue

        try:
            rounds_data = metadata["round_stats"]
            players = list(metadata["config"]["players"])
            player_names = [p["name"] for p in players]

            # Create player-to-model mapping (consistent with other analysis scripts)
            p2m = {
                x["name"]: x["config"]["model"]["model_name"].strip("@").split("/")[-1]
                for x in metadata["config"]["players"]
            }

            # Skip if not exactly 2 players (PvP tournament)
            if len(player_names) != 2:
                continue

            # Identify deficit and recovery situations (round-to-round)
            recovery_situations = identify_deficit_and_recovery_situations(rounds_data, player_names)

            if not recovery_situations:
                continue

            # Process recovery situations for this tournament
            for _round_num, losing_player, deficit_percentage, won_next_round in recovery_situations:
                # Map player name to model name
                losing_model = p2m.get(losing_player, losing_player)

                for min_deficit, max_deficit in DEFICIT_RANGES:
                    if min_deficit <= deficit_percentage < max_deficit:
                        # Record attempt (lost this round)
                        all_recovery_data[losing_model][(min_deficit, max_deficit)]["attempts"] += 1

                        # Record success if they won the next round
                        if won_next_round:
                            all_recovery_data[losing_model][(min_deficit, max_deficit)]["successes"] += 1
                        break

            processed_tournaments += 1

        except Exception as e:
            print(f"Error processing {metadata_path}: {e}")
            continue

    print(f"Successfully processed {processed_tournaments} tournaments")

    # Calculate aggregated success rates
    success_rates = defaultdict(dict)

    for model, deficit_data in all_recovery_data.items():
        for deficit_range, stats in deficit_data.items():
            if stats["attempts"] > 0:
                success_rate = stats["successes"] / stats["attempts"]
                success_rates[model][deficit_range] = {
                    "rate": success_rate,
                    "attempts": stats["attempts"],
                    "successes": stats["successes"],
                }

    return success_rates


def create_comeback_visualization(success_rates, output_path):
    """
    Create line chart visualization of round-to-round recovery rates.

    Args:
        success_rates: Dictionary of recovery rates by model and deficit range
        output_path: Path to save the visualization
    """
    # Set up the plot with clean styling
    plt.style.use("default")
    _, ax = plt.subplots(figsize=(6, 6))

    # Define colors for different models
    markers = ["o", "s", "^", "D", "v", "P", "h"]

    # Create simple x-axis positions (evenly spaced)
    x_positions = list(range(len(DEFICIT_RANGES)))
    x_labels = []

    for min_def, max_def in DEFICIT_RANGES:
        x_labels.append(f"{min_def}-{max_def}")

    # Plot line for each model
    model_names = sorted(success_rates.keys())

    for i, model in enumerate(model_names):
        model_data = success_rates[model]

        # Collect y-values (success rates) for each deficit range
        y_values = []
        valid_x_positions = []

        for j, deficit_range in enumerate(DEFICIT_RANGES):
            if deficit_range in model_data:
                stats = model_data[deficit_range]
                y_values.append(stats["rate"] * 100)  # Convert to percentage
                valid_x_positions.append(x_positions[j])

        if not y_values:  # Skip models with no data
            continue

        # Plot the line
        marker = markers[i % len(markers)]

        ax.plot(
            valid_x_positions,
            y_values,
            marker=marker,
            linewidth=2,
            markersize=8,
            color=MODEL_TO_COLOR[model],
            label=MODEL_TO_DISPLAY_NAME[model],
            alpha=0.9,
        )

    # Customize the plot
    ax.set_xlabel("Loss Margin (%)", fontsize=18, fontproperties=FONT_BOLD)
    ax.set_ylabel("Next Round Win Rate (%)", fontsize=18, fontproperties=FONT_BOLD)
    # ax.set_title("Model Recovery Rate by Loss Margin", fontsize=20, fontproperties=FONT_BOLD, pad=20)

    # Set axis limits and ticks
    ax.set_ylim(0, 100)
    ax.set_xlim(-0.5, len(DEFICIT_RANGES) - 0.5)
    ax.set_xticks(x_positions)
    ax.set_xticklabels(x_labels, fontproperties=FONT_BOLD, fontsize=14)
    ax.set_yticklabels(range(0, 101, 20), fontproperties=FONT_BOLD, fontsize=14)

    # Add grid for better readability
    ax.grid(True, alpha=0.3, linestyle="--")

    # Add legend
    FONT_BOLD.set_size(14)
    ax.legend(loc="upper right", frameon=True, fancybox=True, shadow=True, prop=FONT_BOLD, ncol=2)

    # Adjust layout
    plt.tight_layout()

    # Save the plot
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    print(f"Recovery rate visualization saved to: {output_path}")

    # Display summary statistics
    print("\n" + "=" * 60)
    print("ROUND-TO-ROUND RECOVERY ANALYSIS SUMMARY")
    print("=" * 60)

    for model in model_names:
        if model not in success_rates:
            continue

        print(f"\n{model}:")
        model_data = success_rates[model]

        # Calculate overall recovery rate across all loss margins
        total_attempts = sum(stats["attempts"] for stats in model_data.values())
        total_successes = sum(stats["successes"] for stats in model_data.values())
        overall_rate = total_successes / total_attempts if total_attempts > 0 else 0

        print(f"  Overall next-round win rate after losses: {overall_rate:.1%} ({total_successes}/{total_attempts})")

        # Show breakdown by loss margin range
        for deficit_range in DEFICIT_RANGES:
            if deficit_range in model_data:
                stats = model_data[deficit_range]
                min_def, max_def = deficit_range
                range_label = f"{min_def}%+" if max_def == float("inf") else f"{min_def}-{max_def}%"
                print(f"  Loss margin {range_label}: {stats['rate']:.1%} ({stats['successes']}/{stats['attempts']})")


def main():
    """Main function to run round-to-round recovery analysis."""
    parser = argparse.ArgumentParser(description="Analyze next-round win rates after losses by loss margin")
    parser.add_argument("log_dir", help="Path to directory containing tournament logs", type=Path)
    parser.add_argument("--output", "-o", default=OUTPUT_FILE, help="Output path for the visualization")

    args = parser.parse_args()

    # Validate input directory
    if not args.log_dir.is_dir():
        print(f"Error: Directory '{args.log_dir}' does not exist")
        return

    print(f"Analyzing round-to-round recovery patterns in: {args.log_dir}")

    # Analyze tournaments for recovery patterns
    success_rates = analyze_tournament_directory(args.log_dir)

    if not success_rates:
        print("No recovery data found. Ensure the directory contains PvP tournament metadata files.")
        return

    # Create visualization
    create_comeback_visualization(success_rates, args.output)


if __name__ == "__main__":
    main()
