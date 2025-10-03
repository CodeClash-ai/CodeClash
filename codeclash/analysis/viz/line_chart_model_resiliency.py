#!/usr/bin/env python3
"""
Model Resiliency Analysis: Comeback Success Rate by Deficit Size

This script analyzes how well different AI models recover from score deficits during
tournaments. It tracks models that are trailing in cumulative score at various points
and calculates their success rate at making comebacks.

Key Metrics:
- Deficit Size: How far behind a model is in cumulative score
- Comeback Success: Whether the trailing model ultimately wins the tournament
- Success Rate: Percentage of successful comebacks for each deficit range

Visualization:
- Line chart showing deficit size (x-axis) vs comeback success rate (y-axis)
- Separate line for each model to compare resilience patterns
- Error bars to show confidence intervals where sample sizes permit

Insights:
- Identifies models with strong comeback ability vs those that struggle when behind
- Shows the "point of no return" - deficit sizes from which comebacks become rare
- Reveals model-specific patterns in tournament resilience and recovery
"""

import argparse
import glob
import json
from collections import defaultdict

import matplotlib.pyplot as plt
from tqdm import tqdm


def load_tournament_metadata(metadata_path):
    """Load tournament metadata from JSON file."""
    try:
        with open(metadata_path) as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"Warning: Could not load {metadata_path}: {e}")
        return None


def calculate_cumulative_scores(rounds_data, players):
    """
    Calculate cumulative scores for each player after each round.

    Args:
        rounds_data: Dictionary mapping round numbers to round data
        players: List of player names

    Returns:
        Dictionary mapping round number to player cumulative scores
    """
    cumulative_scores = {}

    # Initialize cumulative scores
    running_totals = {player: 0 for player in players}

    # Process each round in order
    for round_num in sorted(int(k) for k in rounds_data.keys()):
        round_data = rounds_data[str(round_num)]

        # Add this round's scores to running totals
        for player in players:
            if player in round_data["player_stats"]:
                running_totals[player] += round_data["player_stats"][player]["score"]

        # Store cumulative scores after this round
        cumulative_scores[round_num] = running_totals.copy()

    return cumulative_scores


def identify_deficit_situations(cumulative_scores, players):
    """
    Identify situations where a player is trailing and by how much.

    Args:
        cumulative_scores: Dictionary of cumulative scores by round
        players: List of player names

    Returns:
        List of tuples: (round_num, trailing_player, deficit_size)
    """
    deficit_situations = []

    for round_num, scores in cumulative_scores.items():
        if len(scores) < 2:  # Need at least 2 players for comparison
            continue

        # Sort players by score (highest first)
        sorted_players = sorted(players, key=lambda p: scores.get(p, 0), reverse=True)

        if len(sorted_players) >= 2:
            leader = sorted_players[0]
            leader_score = scores.get(leader, 0)

            # Check each trailing player
            for trailing_player in sorted_players[1:]:
                trailing_score = scores.get(trailing_player, 0)
                deficit = leader_score - trailing_score

                if deficit > 0:  # Only record if there's actually a deficit
                    deficit_situations.append((round_num, trailing_player, deficit))

    return deficit_situations


def determine_tournament_winner(rounds_data, players):
    """
    Determine who won the tournament based on final cumulative scores.

    Args:
        rounds_data: Dictionary of round data
        players: List of player names

    Returns:
        String name of winning player
    """
    # Get final cumulative scores
    final_scores = {player: 0 for player in players}

    for round_data in rounds_data.values():
        for player in players:
            if player in round_data["player_stats"]:
                final_scores[player] += round_data["player_stats"][player]["score"]

    # Return player with highest final score
    return max(final_scores.keys(), key=lambda p: final_scores[p])


def calculate_comeback_success_rates(deficit_situations, rounds_data, players):
    """
    Calculate comeback success rates for different deficit ranges.

    Args:
        deficit_situations: List of (round_num, player, deficit) tuples
        rounds_data: Dictionary of round data for determining winners
        players: List of player names

    Returns:
        Dictionary mapping deficit ranges to success rates by model
    """
    # Define deficit ranges (buckets)
    deficit_ranges = [
        (0, 50),  # Small deficit
        (50, 100),  # Medium deficit
        (100, 200),  # Large deficit
        (200, 400),  # Very large deficit
        (400, 800),  # Huge deficit
        (800, float("inf")),  # Massive deficit
    ]

    # Track attempts and successes for each model and deficit range
    comeback_data = defaultdict(lambda: defaultdict(lambda: {"attempts": 0, "successes": 0}))

    # Group deficit situations by tournament
    tournament_deficits = defaultdict(list)
    for round_num, player, deficit in deficit_situations:
        # We need to track which tournament this came from
        # For now, assume all deficit situations are from the same tournament
        tournament_deficits["current"].append((round_num, player, deficit))

    # Process each tournament's deficit situations
    for _tournament_key, deficits in tournament_deficits.items():
        if not deficits:
            continue

        # Determine tournament winner
        winner = determine_tournament_winner(rounds_data, players)

        # Process each deficit situation in this tournament
        for _round_num, trailing_player, deficit in deficits:
            # Find which deficit range this belongs to
            for min_deficit, max_deficit in deficit_ranges:
                if min_deficit <= deficit < max_deficit:
                    # Record attempt
                    comeback_data[trailing_player][(min_deficit, max_deficit)]["attempts"] += 1

                    # Record success if this player ultimately won
                    if trailing_player == winner:
                        comeback_data[trailing_player][(min_deficit, max_deficit)]["successes"] += 1
                    break

    # Calculate success rates
    success_rates = defaultdict(dict)
    for player, deficit_data in comeback_data.items():
        for deficit_range, stats in deficit_data.items():
            if stats["attempts"] > 0:
                success_rate = stats["successes"] / stats["attempts"]
                success_rates[player][deficit_range] = {
                    "rate": success_rate,
                    "attempts": stats["attempts"],
                    "successes": stats["successes"],
                }

    return success_rates, deficit_ranges


def analyze_tournament_directory(log_dir):
    """
    Analyze all tournaments in a directory for comeback patterns.

    Args:
        log_dir: Path to directory containing tournament logs

    Returns:
        Aggregated comeback success rate data
    """
    metadata_files = glob.glob(str(log_dir / "**/metadata.json"), recursive=True)

    # Aggregate data across all tournaments
    all_comeback_data = defaultdict(lambda: defaultdict(lambda: {"attempts": 0, "successes": 0}))
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
            p2m = {x["name"]: x["config"]["model"]["model_name"].strip("@") for x in metadata["config"]["players"]}

            # Skip if not exactly 2 players (PvP tournament)
            if len(player_names) != 2:
                continue

            # Calculate cumulative scores
            cumulative_scores = calculate_cumulative_scores(rounds_data, player_names)

            # Identify deficit situations
            deficit_situations = identify_deficit_situations(cumulative_scores, player_names)

            if not deficit_situations:
                continue

            # Determine tournament winner
            winner = determine_tournament_winner(rounds_data, player_names)  # Define deficit ranges
            deficit_ranges = [(0, 50), (50, 100), (100, 200), (200, 400), (400, 800), (800, float("inf"))]

            # Process deficit situations for this tournament
            for _round_num, trailing_player, deficit in deficit_situations:
                # Map player name to model name
                trailing_model = p2m.get(trailing_player, trailing_player)

                for min_deficit, max_deficit in deficit_ranges:
                    if min_deficit <= deficit < max_deficit:
                        # Record attempt
                        all_comeback_data[trailing_model][(min_deficit, max_deficit)]["attempts"] += 1

                        # Record success if this player's model ultimately won
                        if trailing_player == winner:
                            all_comeback_data[trailing_model][(min_deficit, max_deficit)]["successes"] += 1
                        break

            processed_tournaments += 1

        except Exception as e:
            print(f"Error processing {metadata_path}: {e}")
            continue

    print(f"Successfully processed {processed_tournaments} tournaments")

    # Calculate aggregated success rates
    deficit_ranges = [(0, 50), (50, 100), (100, 200), (200, 400), (400, 800), (800, float("inf"))]
    success_rates = defaultdict(dict)

    for model, deficit_data in all_comeback_data.items():
        for deficit_range, stats in deficit_data.items():
            if stats["attempts"] > 0:
                success_rate = stats["successes"] / stats["attempts"]
                success_rates[model][deficit_range] = {
                    "rate": success_rate,
                    "attempts": stats["attempts"],
                    "successes": stats["successes"],
                }

    return success_rates, deficit_ranges


def create_comeback_visualization(success_rates, deficit_ranges, output_path):
    """
    Create line chart visualization of comeback success rates.

    Args:
        success_rates: Dictionary of success rates by model and deficit range
        deficit_ranges: List of deficit range tuples
        output_path: Path to save the visualization
    """
    # Set up the plot with clean styling
    plt.style.use("default")
    fig, ax = plt.subplots(figsize=(12, 8))

    # Define colors for different models
    colors = ["#2E86C1", "#E74C3C", "#28B463", "#F39C12", "#8E44AD", "#17A2B8", "#DC7633"]
    markers = ["o", "s", "^", "D", "v", "P", "h"]

    # Create simple x-axis positions (evenly spaced)
    x_positions = list(range(len(deficit_ranges)))
    x_labels = []

    for min_def, max_def in deficit_ranges:
        if max_def == float("inf"):
            x_labels.append(f"{min_def}+")
        else:
            x_labels.append(f"{min_def}-{max_def}")

    # Plot line for each model
    model_names = sorted(success_rates.keys())

    for i, model in enumerate(model_names):
        model_data = success_rates[model]

        # Collect y-values (success rates) for each deficit range
        y_values = []
        valid_x_positions = []

        for j, deficit_range in enumerate(deficit_ranges):
            if deficit_range in model_data:
                stats = model_data[deficit_range]
                y_values.append(stats["rate"] * 100)  # Convert to percentage
                valid_x_positions.append(x_positions[j])

        if not y_values:  # Skip models with no data
            continue

        # Plot the line
        color = colors[i % len(colors)]
        marker = markers[i % len(markers)]

        # Clean model name for legend (remove provider prefix)
        clean_model_name = model.split("/")[-1] if "/" in model else model

        ax.plot(
            valid_x_positions,
            y_values,
            marker=marker,
            linewidth=3,
            markersize=8,
            color=color,
            label=clean_model_name,
            alpha=0.9,
        )

    # Customize the plot
    ax.set_xlabel("Deficit Size Range", fontsize=14, fontweight="bold")
    ax.set_ylabel("Comeback Success Rate (%)", fontsize=14, fontweight="bold")
    ax.set_title("Model Comeback Success Rate by Deficit Size", fontsize=16, fontweight="bold", pad=20)

    # Set axis limits and ticks
    ax.set_ylim(0, 100)
    ax.set_xlim(-0.5, len(deficit_ranges) - 0.5)
    ax.set_xticks(x_positions)
    ax.set_xticklabels(x_labels)

    # Add grid for better readability
    ax.grid(True, alpha=0.3, linestyle="--")

    # Add legend
    ax.legend(loc="upper right", frameon=True, fancybox=True, shadow=True)

    # Adjust layout
    plt.tight_layout()

    # Save the plot
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    print(f"Comeback success rate visualization saved to: {output_path}")

    # Display summary statistics
    print("\n" + "=" * 60)
    print("COMEBACK ANALYSIS SUMMARY")
    print("=" * 60)

    for model in model_names:
        if model not in success_rates:
            continue

        print(f"\n{model}:")
        model_data = success_rates[model]

        # Calculate overall comeback rate across all deficits
        total_attempts = sum(stats["attempts"] for stats in model_data.values())
        total_successes = sum(stats["successes"] for stats in model_data.values())
        overall_rate = total_successes / total_attempts if total_attempts > 0 else 0

        print(f"  Overall comeback rate: {overall_rate:.1%} ({total_successes}/{total_attempts})")

        # Show breakdown by deficit range
        for deficit_range in deficit_ranges:
            if deficit_range in model_data:
                stats = model_data[deficit_range]
                min_def, max_def = deficit_range
                range_label = f"{min_def}+" if max_def == float("inf") else f"{min_def}-{max_def}"
                print(f"  {range_label}: {stats['rate']:.1%} ({stats['successes']}/{stats['attempts']})")


def main():
    """Main function to run comeback analysis."""
    parser = argparse.ArgumentParser(description="Analyze comeback success rates by deficit size")
    parser.add_argument("log_dir", help="Path to directory containing tournament logs")
    parser.add_argument(
        "--output", "-o", default="comeback_success_rates.png", help="Output path for the visualization"
    )

    args = parser.parse_args()

    # Validate input directory
    if not args.log_dir.is_dir():
        print(f"Error: Directory '{args.log_dir}' does not exist")
        return

    print(f"Analyzing comeback patterns in: {args.log_dir}")

    # Analyze tournaments for comeback patterns
    success_rates, deficit_ranges = analyze_tournament_directory(args.log_dir)

    if not success_rates:
        print("No comeback data found. Ensure the directory contains PvP tournament metadata files.")
        return

    # Create visualization
    create_comeback_visualization(success_rates, deficit_ranges, args.output)


if __name__ == "__main__":
    main()
