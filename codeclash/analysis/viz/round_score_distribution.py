#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from tqdm import tqdm

from codeclash.analysis.viz.utils import MODEL_TO_DISPLAY_NAME
from codeclash.constants import LOCAL_LOG_DIR
from codeclash.games import BattleCodeGame, DummyGame
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

    if game_name in {DummyGame.name, BattleCodeGame.name}:
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
    all_scores = [s for scores in data_by_category.values() for s in scores]

    # Determine category order
    if by_model:
        category_names = sorted(data_by_category.keys(), key=lambda m: MODEL_TO_DISPLAY_NAME.get(m, m))
    else:
        category_names = sorted(data_by_category.keys())

    # Create subplots: 1 for all + 1 per category
    n_plots = 1 + len(category_names)
    n_cols = 2
    n_rows = (n_plots + n_cols - 1) // n_cols

    fig, axes = plt.subplots(n_rows, n_cols, figsize=(14, 5 * n_rows))
    axes = axes.flatten() if n_plots > 1 else [axes]

    bins = np.linspace(0, 1, 51)

    # Plot all combined
    ax = axes[0]
    ax.hist(all_scores, bins=bins, edgecolor="black", alpha=0.7)
    ax.set_xlabel("Normalized Score", fontsize=10, fontweight="bold")
    ax.set_ylabel("Frequency", fontsize=10, fontweight="bold")
    ax.set_title("All Models" if by_model else "All Games", fontsize=12, fontweight="bold")
    ax.set_xlim(0, 1)
    ax.grid(True, alpha=0.3, axis="y")

    mean_score = np.mean(all_scores)
    median_score = np.median(all_scores)
    stats_text = f"Mean: {mean_score:.3f}\nMedian: {median_score:.3f}\nN: {len(all_scores)}"
    ax.text(
        0.98,
        0.98,
        stats_text,
        transform=ax.transAxes,
        verticalalignment="top",
        horizontalalignment="right",
        fontsize=9,
        bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.8),
    )

    # Plot per category
    for idx, category_name in enumerate(category_names, start=1):
        ax = axes[idx]
        scores = data_by_category[category_name]

        ax.hist(scores, bins=bins, edgecolor="black", alpha=0.7)
        ax.set_xlabel("Normalized Score", fontsize=10, fontweight="bold")
        ax.set_ylabel("Frequency", fontsize=10, fontweight="bold")
        display_name = MODEL_TO_DISPLAY_NAME.get(category_name, category_name) if by_model else category_name
        ax.set_title(display_name, fontsize=12, fontweight="bold")
        ax.set_xlim(0, 1)
        ax.grid(True, alpha=0.3, axis="y")

        mean_score = np.mean(scores)
        median_score = np.median(scores)
        stats_text = f"Mean: {mean_score:.3f}\nMedian: {median_score:.3f}\nN: {len(scores)}"
        ax.text(
            0.98,
            0.98,
            stats_text,
            transform=ax.transAxes,
            verticalalignment="top",
            horizontalalignment="right",
            fontsize=9,
            bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.8),
        )

    # Hide unused subplots
    for idx in range(n_plots, len(axes)):
        axes[idx].set_visible(False)

    plt.suptitle(title, fontsize=14, fontweight="bold")
    plt.tight_layout(rect=[0, 0, 1, 0.97])

    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    logger.info(f"Saved plot to {output_path}")

    plt.close()


def main(log_dir: Path, output_by_game: Path, output_by_model: Path) -> None:
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
    plot_stratified(
        scores_by_game,
        output_by_game,
        title="Distribution of Normalized Player Scores by Game (Valid Rounds Only)",
        by_model=False,
    )

    # Plot by model
    plot_stratified(
        scores_by_model,
        output_by_model,
        title="Distribution of Normalized Player Scores by Model (Valid Rounds Only)",
        by_model=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Plot distribution of normalized player scores (valid rounds only)")
    parser.add_argument("-d", "--log_dir", type=Path, default=LOCAL_LOG_DIR, help="Path to log directory")
    parser.add_argument(
        "--output_by_game",
        type=Path,
        default=Path("round_score_distribution_by_game.pdf"),
        help="Output path for by-game plot",
    )
    parser.add_argument(
        "--output_by_model",
        type=Path,
        default=Path("round_score_distribution_by_model.pdf"),
        help="Output path for by-model plot",
    )
    args = parser.parse_args()

    main(args.log_dir, args.output_by_game, args.output_by_model)
