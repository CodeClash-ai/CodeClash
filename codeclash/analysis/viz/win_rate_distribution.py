#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.ticker import AutoMinorLocator
from tqdm import tqdm

from codeclash.analysis.viz.utils import ASSETS_DIR, FONT_BOLD, MODEL_TO_DISPLAY_NAME
from codeclash.constants import LOCAL_LOG_DIR, RESULT_TIE
from codeclash.games import BattleCodeGame, DummyGame
from codeclash.utils.log import get_logger

logger = get_logger("win_rate_distribution")


def get_player_win_counts(metadata_path: Path) -> tuple[str | None, dict[str, list[int]], dict[str, list[int]]]:
    """Get the win counts (rounds won) for all players in a tournament.

    Returns a tuple of (game_name, game_to_wins, model_to_wins).
    Only returns data if the tournament has exactly 15 rounds.
    """
    metadata = json.loads(metadata_path.read_text())

    try:
        players = metadata["config"]["players"]
        game_name = metadata["config"]["game"]["name"]
    except KeyError:
        return None, {}, {}

    if len(players) != 2:
        return None, {}, {}

    if game_name in {DummyGame.name, BattleCodeGame.name}:
        return None, {}, {}

    # Map player names to models
    player_to_model = {}
    for player in players:
        player_name = player["name"]
        model = player["config"]["model"]["model_name"].strip("@").split("/")[-1]
        player_to_model[player_name] = model

    player_names = [p["name"] for p in players]

    # Count wins per player and total rounds
    player_wins = {name: 0 for name in player_names}
    total_rounds = 0

    for idx, stats in metadata["round_stats"].items():
        if idx == "0":
            continue

        total_rounds += 1
        winner = stats.get("winner")

        if winner == RESULT_TIE:
            continue
        if winner in player_wins:
            player_wins[winner] += 1

    # Only return if exactly 15 rounds
    if total_rounds != 15:
        return None, {}, {}

    # Organize by game
    game_to_wins = {game_name: list(player_wins.values())}

    # Organize by model
    model_to_wins = {}
    for player_name, wins in player_wins.items():
        model = player_to_model[player_name]
        if model not in model_to_wins:
            model_to_wins[model] = []
        model_to_wins[model].append(wins)

    return game_name, game_to_wins, model_to_wins


def plot_stratified(
    data_by_category: dict[str, list[int]], output_path: Path, *, title: str, by_model: bool = False
) -> None:
    """Plot win counts stratified by category (game or model)."""
    # Determine category order
    if by_model:
        # Sort by full model name (including prefix), then strip prefix for display
        category_names = sorted(data_by_category.keys())
    else:
        category_names = sorted(data_by_category.keys())

    # Create subplots: 3 columns, no "All" plot
    n_plots = len(category_names)
    n_cols = 3
    n_rows = (n_plots + n_cols - 1) // n_cols

    # Use 4x4 for all plots
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(4 * n_cols, 4 * n_rows))
    axes = axes.flatten() if n_plots > 1 else [axes]

    bins = np.arange(-0.5, 16.5, 1)

    # Plot per category
    for idx, category_name in enumerate(category_names):
        ax = axes[idx]
        counts = data_by_category[category_name]

        ax.hist(counts, bins=bins, edgecolor="black", alpha=0.7, density=True)
        ax.set_xlabel("Total number of rounds won (out of 15)", fontproperties=FONT_BOLD, fontsize=12)
        ax.set_ylabel("Density", fontproperties=FONT_BOLD, fontsize=12)

        # Set tick labels to also use bold font
        for label in ax.get_xticklabels() + ax.get_yticklabels():
            label.set_fontproperties(FONT_BOLD)

        if by_model:
            display_name = MODEL_TO_DISPLAY_NAME.get(category_name, category_name)
        else:
            display_name = category_name.replace("Halite", "Poker")
        ax.set_title(display_name, fontproperties=FONT_BOLD, fontsize=14)
        ax.set_xticks(range(0, 16))

        # Add minor ticks on y-axis
        ax.yaxis.set_minor_locator(AutoMinorLocator())

        # Show ticks on all sides, pointing inward
        ax.tick_params(top=True, right=True, which="both", direction="in")

        ax.grid(True, alpha=0.3, axis="y")

        # Add stats text only for by_model plots
        if by_model:
            mean_wc = np.mean(counts)
            median_wc = np.median(counts)
            stats_text = f"Mean: {mean_wc:.2f}\nMedian: {median_wc:.1f}\nN: {len(counts)}"
            ax.text(
                0.5,
                0.93,
                stats_text,
                transform=ax.transAxes,
                verticalalignment="top",
                horizontalalignment="center",
                fontproperties=FONT_BOLD,
                fontsize=10,
                bbox=dict(boxstyle="square", facecolor="white", edgecolor="black", linewidth=1),
            )

    # Hide unused subplots
    for idx in range(n_plots, len(axes)):
        axes[idx].set_visible(False)

    plt.suptitle(title, fontproperties=FONT_BOLD, fontsize=16)
    plt.tight_layout(rect=[0, 0, 1, 0.97])

    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    logger.info(f"Saved plot to {output_path}")

    plt.close()


def get_tournament_wins_by_model(metadata_path: Path) -> dict[str, tuple[bool, int]]:
    """Resolve tournament winner using per_tournament_boolean_drop_draws logic.

    Returns a dict mapping model_name -> (won_tournament, rounds_won).
    Skips tournaments that end in unbreakable ties.
    """
    metadata = json.loads(metadata_path.read_text())

    try:
        players = metadata["config"]["players"]
        game_name = metadata["config"]["game"]["name"]
    except KeyError:
        return {}

    if len(players) != 2:
        return {}

    if game_name in {DummyGame.name, BattleCodeGame.name}:
        return {}

    # Map player names to models
    player_to_model = {}
    for player in players:
        player_name = player["name"]
        model = player["config"]["model"]["model_name"].strip("@").split("/")[-1]
        player_to_model[player_name] = model

    player_names = list(player_to_model.keys())

    # Collect round scores (using tertiary scoring: 0, 0.5, or 1)
    p1_round_scores = []
    p2_round_scores = []

    for idx, stats in metadata["round_stats"].items():
        if idx == "0":
            continue

        winner = stats.get("winner")

        if winner == RESULT_TIE:
            p1_round_scores.append(0.0)
            p2_round_scores.append(0.0)
        elif winner == player_names[0]:
            p1_round_scores.append(1.0)
            p2_round_scores.append(0.0)
        elif winner == player_names[1]:
            p1_round_scores.append(0.0)
            p2_round_scores.append(1.0)
        else:
            continue

    if not p1_round_scores:
        return {}

    p1_rounds_won = int(sum(p1_round_scores))
    p2_rounds_won = int(sum(p2_round_scores))

    # Resolve tournament winner (per_tournament_boolean_drop_draws logic)
    if p1_rounds_won == p2_rounds_won:
        # Check for the last round that was not a tie
        for i in range(len(p1_round_scores) - 1, -1, -1):
            if p1_round_scores[i] > p2_round_scores[i]:
                p1_won_tournament = True
                p2_won_tournament = False
                break
            if p1_round_scores[i] < p2_round_scores[i]:
                p1_won_tournament = False
                p2_won_tournament = True
                break
        else:
            # Unbreakable tie, skip tournament
            return {}
    elif p1_rounds_won > p2_rounds_won:
        p1_won_tournament = True
        p2_won_tournament = False
    else:
        p1_won_tournament = False
        p2_won_tournament = True

    return {
        player_to_model[player_names[0]]: (p1_won_tournament, p1_rounds_won),
        player_to_model[player_names[1]]: (p2_won_tournament, p2_rounds_won),
    }


def plot_overlaid_win_margins(win_margins_by_model: dict[str, list[int]], output_path: Path) -> None:
    """Plot overlaid line histograms of rounds won for winning tournaments only.

    Args:
        win_margins_by_model: Dict mapping model name to list of rounds_won for tournaments they won
    """
    if not win_margins_by_model:
        logger.warning("No win margins to plot")
        return

    # Sort models by display name
    model_names = sorted(win_margins_by_model.keys(), key=lambda m: MODEL_TO_DISPLAY_NAME.get(m, m))

    fig, ax = plt.subplots(figsize=(10, 10))

    # Integer bins for rounds won (0 to 15)
    bins = np.arange(-0.5, 16.5, 1)  # Centers on integers 0-15

    # Plot each model as a line
    for model_name in model_names:
        win_margins = win_margins_by_model[model_name]
        if not win_margins:
            continue

        display_name = MODEL_TO_DISPLAY_NAME.get(model_name, model_name)

        # Calculate statistics
        mean_rounds = np.mean(win_margins)
        median_rounds = np.median(win_margins)

        # Calculate normalized histogram
        hist, bin_edges = np.histogram(win_margins, bins=bins, density=True)
        bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2

        # Plot as line with markers, include stats in legend
        label = f"{display_name} (μ={mean_rounds:.1f}, med={median_rounds:.1f})"
        ax.plot(bin_centers, hist, marker="o", linewidth=2, markersize=4, label=label, alpha=0.8)

    ax.set_xlabel("Rounds Won (out of 15, in tournaments won)", fontproperties=FONT_BOLD, fontsize=14)
    ax.set_ylabel("Normalized Frequency", fontproperties=FONT_BOLD, fontsize=14)
    ax.set_title(
        "Distribution of Victory Margins by Model (Winning Tournaments Only)", fontproperties=FONT_BOLD, fontsize=16
    )
    ax.set_xticks(range(0, 16))
    ax.set_xlim(-0.5, 15.5)
    ax.grid(True, alpha=0.3, axis="y")
    legend = ax.legend(prop=FONT_BOLD, fontsize=12, loc="best")
    legend.set_frame_on(False)

    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    logger.info(f"Saved overlaid win margins plot to {output_path}")
    plt.close()


def main(log_dir: Path) -> None:
    """Calculate win counts and plot histograms stratified by game and by model."""
    logger.info(f"Processing tournaments from {log_dir}")

    win_counts_by_game = {}
    win_counts_by_model = {}
    win_margins_by_model = {}

    for metadata_path in tqdm(list(log_dir.rglob("metadata.json"))):
        try:
            game_name, game_wins, model_wins = get_player_win_counts(metadata_path)
            if game_name:
                # Collect by game
                for game, counts in game_wins.items():
                    if game not in win_counts_by_game:
                        win_counts_by_game[game] = []
                    win_counts_by_game[game].extend(counts)

                # Collect by model
                for model, counts in model_wins.items():
                    if model not in win_counts_by_model:
                        win_counts_by_model[model] = []
                    win_counts_by_model[model].extend(counts)

            # Collect tournament wins for overlaid plot (only winning tournaments)
            tournament_results = get_tournament_wins_by_model(metadata_path)
            for model, (won_tournament, rounds_won_fraction) in tournament_results.items():
                if won_tournament:  # Only include tournaments this model won
                    if model not in win_margins_by_model:
                        win_margins_by_model[model] = []
                    win_margins_by_model[model].append(rounds_won_fraction)
        except Exception as e:
            logger.error(f"Error processing {metadata_path}: {e}", exc_info=True)
            continue

    if not win_counts_by_game:
        logger.warning("No win counts collected")
        return

    all_win_counts = [w for counts in win_counts_by_game.values() for w in counts]
    logger.info(
        f"Collected {len(all_win_counts)} win counts across {len(win_counts_by_game)} games and {len(win_counts_by_model)} models"
    )

    # Plot by game
    output_by_game = ASSETS_DIR / "win_rate_distribution_by_game.pdf"
    plot_stratified(
        win_counts_by_game,
        output_by_game,
        title="Distribution of Player Win Counts by Game (15 Round Tournaments Only)",
        by_model=False,
    )

    # Plot by model
    output_by_model = ASSETS_DIR / "win_rate_distribution_by_model.pdf"
    plot_stratified(
        win_counts_by_model,
        output_by_model,
        title="Distribution of Player Win Counts by Model (15 Round Tournaments Only)",
        by_model=True,
    )

    # Plot overlaid win margins
    if win_margins_by_model:
        total_wins = sum(len(v) for v in win_margins_by_model.values())
        logger.info(f"Collected {total_wins} winning tournaments across {len(win_margins_by_model)} models")
        output_overlaid = ASSETS_DIR / "win_rates_won_games_by_model_overlaid.pdf"
        plot_overlaid_win_margins(win_margins_by_model, output_overlaid)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Plot distribution of player win counts (only tournaments with 15 rounds)"
    )
    parser.add_argument("-d", "--log_dir", type=Path, default=LOCAL_LOG_DIR, help="Path to log directory")
    args = parser.parse_args()

    main(args.log_dir)
