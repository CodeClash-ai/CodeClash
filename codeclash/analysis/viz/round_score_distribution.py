#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.ticker import AutoMinorLocator
from tqdm import tqdm

from codeclash.analysis.viz.utils import ASSETS_DIR, FONT_BOLD, MODEL_TO_DISPLAY_NAME
from codeclash.arenas import BattleCode2025Arena, DummyGame
from codeclash.constants import LOCAL_LOG_DIR
from codeclash.utils.log import get_logger

logger = get_logger("round_score_distribution")


def get_normalized_scores(metadata_path: Path) -> tuple[str | None, dict[str, list[float]], dict[str, list[float]]]:
    """Get normalized scores for all rounds where all players had valid submissions.

    Returns a tuple of (game_name, game_to_scores, model_to_scores).
    """
    metadata = json.loads(metadata_path.read_text())

    try:
        players = metadata["config"]["players"]
        game_name = metadata["config"]["game"]["name"]
    except KeyError:
        return None, {}, {}

    if len(players) != 2:
        return None, {}, {}

    if game_name in {DummyGame.name, BattleCode2025Arena.name}:
        return None, {}, {}

    # Map player names to models
    player_to_model = {}
    for player in players:
        player_name = player["name"]
        model = player["config"]["model"]["model_name"].strip("@").split("/")[-1]
        player_to_model[player_name] = model

    player_names = list(player_to_model.keys())

    # Collect scores
    all_normalized_scores = []
    model_scores = {model: [] for model in player_to_model.values()}

    for idx, stats in metadata["round_stats"].items():
        if idx == "0":
            continue

        # Check if all players have valid submissions
        player_stats = stats.get("player_stats", {})
        if not all(ps.get("valid_submit", False) for ps in player_stats.values()):
            continue

        # Get scores
        scores = stats.get("scores", {})
        player_scores = {player: scores.get(player) for player in player_names}

        if not all(s is not None for s in player_scores.values()):
            continue

        total_score = sum(player_scores.values())

        if total_score == 0:
            continue

        # Normalize and add to lists
        for player, score in player_scores.items():
            normalized_score = score / total_score
            all_normalized_scores.append(normalized_score)
            model = player_to_model[player]
            model_scores[model].append(normalized_score)

    # Organize by game
    game_to_scores = {game_name: all_normalized_scores} if all_normalized_scores else {}

    # Filter out empty model scores
    model_to_scores = {model: scores for model, scores in model_scores.items() if scores}

    return game_name, game_to_scores, model_to_scores


def plot_stratified(
    data_by_category: dict[str, list[float]], output_path: Path, *, title: str, by_model: bool = False
) -> None:
    """Plot normalized scores stratified by category (game or model)."""
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

    bins = np.linspace(0, 1, 51)

    # Plot per category
    for idx, category_name in enumerate(category_names):
        ax = axes[idx]
        scores = data_by_category[category_name]

        ax.hist(scores, bins=bins, edgecolor="black", alpha=0.7, density=True)
        ax.set_xlabel("Normalized Score", fontproperties=FONT_BOLD, fontsize=12)
        ax.set_ylabel("Density", fontproperties=FONT_BOLD, fontsize=12)

        # Set tick labels to also use bold font
        for label in ax.get_xticklabels() + ax.get_yticklabels():
            label.set_fontproperties(FONT_BOLD)

        if by_model:
            display_name = MODEL_TO_DISPLAY_NAME.get(category_name, category_name)
        else:
            display_name = category_name.replace("Halite", "Poker")
        ax.set_title(display_name, fontproperties=FONT_BOLD, fontsize=14)
        ax.set_xlim(0, 1)

        # Add minor ticks on both axes
        ax.xaxis.set_minor_locator(AutoMinorLocator())
        ax.yaxis.set_minor_locator(AutoMinorLocator())

        # Show ticks on all sides
        ax.tick_params(top=True, right=True, which="both")

        # Add gridlines for both x and y
        ax.grid(True, alpha=0.3, axis="both", which="major")

        # Add dashed black line at 50%
        ax.axvline(0.5, color="black", linestyle="--", linewidth=1.5, alpha=0.7)

        # Add stats text only for by_model plots
        if by_model:
            mean_score = np.mean(scores)
            median_score = np.median(scores)
            stats_text = f"Mean: {mean_score:.3f}    Median: {median_score:.3f}"
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


def main(log_dir: Path) -> None:
    """Calculate normalized scores and plot histograms stratified by game and by model."""
    logger.info(f"Processing tournaments from {log_dir}")

    scores_by_game = {}
    scores_by_model = {}

    for metadata_path in tqdm(list(log_dir.rglob("metadata.json"))):
        try:
            game_name, game_scores, model_scores = get_normalized_scores(metadata_path)
            if game_name:
                # Collect by game
                for game, scores in game_scores.items():
                    if game not in scores_by_game:
                        scores_by_game[game] = []
                    scores_by_game[game].extend(scores)

                # Collect by model
                for model, scores in model_scores.items():
                    if model not in scores_by_model:
                        scores_by_model[model] = []
                    scores_by_model[model].extend(scores)
        except Exception as e:
            logger.error(f"Error processing {metadata_path}: {e}", exc_info=True)
            continue

    if not scores_by_game:
        logger.warning("No scores collected")
        return

    all_scores = [s for scores in scores_by_game.values() for s in scores]
    logger.info(
        f"Collected {len(all_scores)} normalized scores across {len(scores_by_game)} games and {len(scores_by_model)} models"
    )

    # Plot by game
    output_by_game = ASSETS_DIR / "round_score_distribution_by_game.pdf"
    plot_stratified(
        scores_by_game,
        output_by_game,
        title="Distribution of Normalized Player Scores by Game (Valid Rounds Only)",
        by_model=False,
    )

    # Plot by model
    output_by_model = ASSETS_DIR / "round_score_distribution_by_model.pdf"
    plot_stratified(
        scores_by_model,
        output_by_model,
        title="Distribution of Normalized Player Scores by Model (Valid Rounds Only)",
        by_model=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Plot distribution of normalized player scores (valid rounds only)")
    parser.add_argument("-d", "--log_dir", type=Path, default=LOCAL_LOG_DIR, help="Path to log directory")
    args = parser.parse_args()

    main(args.log_dir)
