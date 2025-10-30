#!/usr/bin/env python3
"""Plot comeback and falldown probabilities after win/loss streaks."""

import argparse
import json
import logging
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.font_manager import FontProperties
from matplotlib.ticker import AutoMinorLocator, NullLocator
from tqdm import tqdm

from codeclash import REPO_DIR
from codeclash.analysis.viz.utils import ASSETS_DIR, FONT_BOLD, MARKERS, MODEL_TO_COLOR, MODEL_TO_DISPLAY_NAME

logger = logging.getLogger(__name__)


def load_tournament_data(log_dir: Path) -> pd.DataFrame:
    """Load tournament data and extract round winners."""
    data = []
    for metadata_file in tqdm(list(log_dir.rglob("metadata.json")), desc="Processing tournaments"):
        try:
            metadata = json.load(open(metadata_file))
            p2m = {
                x["name"]: x["config"]["model"]["model_name"].strip("@").partition("/")[2]
                or x["config"]["model"]["model_name"].strip("@")
                for x in metadata["config"]["players"]
            }

            if len(p2m) != 2:
                continue

            models_in_tournament = list(p2m.values())
            if len(set(models_in_tournament)) < 2:
                continue

            round_stats = metadata.get("round_stats", {})
            round_ids = [r for r in round_stats.keys() if r != "0"]
            if len(round_ids) != 15:
                continue

            player_names = list(p2m.keys())
            model_a = p2m[player_names[0]]
            model_b = p2m[player_names[1]]

            tournament_data = {
                "model_a": model_a,
                "model_b": model_b,
                "tournament_path": str(metadata_file.parent),
            }

            for round_id in sorted(round_stats.keys(), key=int):
                if round_id == "0":
                    continue

                round_data = round_stats[round_id]
                winner = round_data.get("winner")

                if winner in p2m:
                    winner_model = p2m[winner]
                    tournament_data[f"round_{round_id}_winner"] = winner_model
                else:
                    tournament_data[f"round_{round_id}_winner"] = None

            data.append(tournament_data)
        except Exception:
            logger.warning("Failed to process tournament metadata file %s", metadata_file, exc_info=True)
            continue

    return pd.DataFrame(data)


def calculate_streak_probabilities(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Calculate comeback and falldown probabilities after i consecutive losses/wins."""
    model_comeback_stats = defaultdict(lambda: defaultdict(lambda: {"opportunities": 0, "successes": 0}))
    model_falldown_stats = defaultdict(lambda: defaultdict(lambda: {"opportunities": 0, "successes": 0}))
    model_overall_stats = defaultdict(lambda: {"total_rounds": 0, "wins": 0})

    for _, row in df.iterrows():
        model_a = row["model_a"]
        model_b = row["model_b"]

        for round_num in range(1, 16):
            winner_current = row[f"round_{round_num}_winner"]

            # Track overall win rates
            model_overall_stats[model_a]["total_rounds"] += 1
            model_overall_stats[model_b]["total_rounds"] += 1
            if winner_current == model_a:
                model_overall_stats[model_a]["wins"] += 1
            elif winner_current == model_b:
                model_overall_stats[model_b]["wins"] += 1

        for round_num in range(2, 16):
            winner_current = row[f"round_{round_num}_winner"]

            # Check for model_a
            consecutive_losses_a = 0
            for lookback in range(1, round_num):
                check_round = round_num - lookback
                if row[f"round_{check_round}_winner"] == model_b:
                    consecutive_losses_a += 1
                else:
                    break

            if consecutive_losses_a > 0:
                for i in range(1, consecutive_losses_a + 1):
                    model_comeback_stats[model_a][i]["opportunities"] += 1
                    if winner_current == model_a:
                        model_comeback_stats[model_a][i]["successes"] += 1

            consecutive_wins_a = 0
            for lookback in range(1, round_num):
                check_round = round_num - lookback
                if row[f"round_{check_round}_winner"] == model_a:
                    consecutive_wins_a += 1
                else:
                    break

            if consecutive_wins_a > 0:
                for i in range(1, consecutive_wins_a + 1):
                    model_falldown_stats[model_a][i]["opportunities"] += 1
                    if winner_current == model_b:
                        model_falldown_stats[model_a][i]["successes"] += 1

            # Check for model_b
            consecutive_losses_b = 0
            for lookback in range(1, round_num):
                check_round = round_num - lookback
                if row[f"round_{check_round}_winner"] == model_a:
                    consecutive_losses_b += 1
                else:
                    break

            if consecutive_losses_b > 0:
                for i in range(1, consecutive_losses_b + 1):
                    model_comeback_stats[model_b][i]["opportunities"] += 1
                    if winner_current == model_b:
                        model_comeback_stats[model_b][i]["successes"] += 1

            consecutive_wins_b = 0
            for lookback in range(1, round_num):
                check_round = round_num - lookback
                if row[f"round_{check_round}_winner"] == model_b:
                    consecutive_wins_b += 1
                else:
                    break

            if consecutive_wins_b > 0:
                for i in range(1, consecutive_wins_b + 1):
                    model_falldown_stats[model_b][i]["opportunities"] += 1
                    if winner_current == model_a:
                        model_falldown_stats[model_b][i]["successes"] += 1

    # Create dataframes
    comeback_prob_data = []
    for model in model_comeback_stats:
        row_data = {"model": model}
        for i in range(1, 15):
            if model_comeback_stats[model][i]["opportunities"] > 0:
                prob = model_comeback_stats[model][i]["successes"] / model_comeback_stats[model][i]["opportunities"]
                row_data[f"comeback_prob_after_{i}_losses"] = prob
            else:
                row_data[f"comeback_prob_after_{i}_losses"] = None
        comeback_prob_data.append(row_data)

    comeback_prob_df = pd.DataFrame(comeback_prob_data).set_index("model")

    falldown_prob_data = []
    for model in model_falldown_stats:
        row_data = {"model": model}
        for i in range(1, 15):
            if model_falldown_stats[model][i]["opportunities"] > 0:
                prob = model_falldown_stats[model][i]["successes"] / model_falldown_stats[model][i]["opportunities"]
                row_data[f"falldown_prob_after_{i}_wins"] = prob
            else:
                row_data[f"falldown_prob_after_{i}_wins"] = None
        falldown_prob_data.append(row_data)

    falldown_prob_df = pd.DataFrame(falldown_prob_data).set_index("model")

    # Create overall win rate dataframe
    overall_win_rate_data = []
    for model in model_overall_stats:
        if model_overall_stats[model]["total_rounds"] > 0:
            win_rate = model_overall_stats[model]["wins"] / model_overall_stats[model]["total_rounds"]
            overall_win_rate_data.append({"model": model, "win_rate": win_rate})

    overall_win_rate_df = pd.DataFrame(overall_win_rate_data).set_index("model")

    return comeback_prob_df, falldown_prob_df, overall_win_rate_df


def plot_comeback_probabilities(
    comeback_prob_df: pd.DataFrame, overall_win_rate_df: pd.DataFrame, output_file: Path
) -> None:
    """Plot probability of winning after i consecutive losses."""
    fig, ax = plt.subplots(figsize=(6, 6))
    label_font = FontProperties(fname=FONT_BOLD.get_file(), size=18)
    title_font = FontProperties(fname=FONT_BOLD.get_file(), size=18)
    legend_font = FontProperties(fname=FONT_BOLD.get_file(), size=14)

    sorted_models = sorted(comeback_prob_df.index)

    for idx, model in enumerate(sorted_models):
        x_values = []
        y_values = []

        for i in range(1, 15):
            col = f"comeback_prob_after_{i}_losses"
            if pd.notna(comeback_prob_df.loc[model, col]):
                x_values.append(i)
                y_values.append(comeback_prob_df.loc[model, col])

        if x_values:
            display_name = MODEL_TO_DISPLAY_NAME.get(model, model)

            # Add overall win rate to legend
            if model in overall_win_rate_df.index:
                win_rate_pct = overall_win_rate_df.loc[model, "win_rate"] * 100
                display_name = f"{display_name} ({win_rate_pct:.0f}%)"

            color = MODEL_TO_COLOR.get(model, None)
            marker = MARKERS[idx % len(MARKERS)]
            ax.plot(
                x_values,
                y_values,
                label=display_name,
                alpha=0.7,
                color=color,
                linewidth=2.5,
                marker=marker,
                markersize=7,
            )

    ax.set_xlabel("Number of Consecutive Rounds Lost", fontproperties=label_font)
    ax.set_ylabel("Probability of winning next round", fontproperties=label_font)
    ax.set_title("Comeback probability after loss streak", fontproperties=title_font)
    ax.legend(loc="upper right", prop=legend_font)
    ax.grid(True, alpha=0.3)
    ax.yaxis.set_minor_locator(AutoMinorLocator())
    ax.xaxis.set_minor_locator(NullLocator())

    # Set x-axis to show integer ticks
    ax.set_xticks(range(1, 15))
    ax.set_xlim(0.5, max(ax.get_xlim()[1], 14.5))
    for label in ax.get_xticklabels() + ax.get_yticklabels():
        label.set_fontproperties(FontProperties(fname=FONT_BOLD.get_file(), size=14))
    plt.tight_layout()
    plt.savefig(output_file, bbox_inches="tight")
    print(f"Saved comeback probability plot to {output_file}")


def plot_falldown_probabilities(
    falldown_prob_df: pd.DataFrame, overall_win_rate_df: pd.DataFrame, output_file: Path
) -> None:
    """Plot probability of losing after i consecutive wins."""
    fig, ax = plt.subplots(figsize=(6, 6))
    label_font = FontProperties(fname=FONT_BOLD.get_file(), size=18)
    title_font = FontProperties(fname=FONT_BOLD.get_file(), size=18)
    legend_font = FontProperties(fname=FONT_BOLD.get_file(), size=14)

    sorted_models = sorted(falldown_prob_df.index)

    for idx, model in enumerate(sorted_models):
        x_values = []
        y_values = []

        for i in range(1, 15):
            col = f"falldown_prob_after_{i}_wins"
            if pd.notna(falldown_prob_df.loc[model, col]):
                x_values.append(i)
                y_values.append(falldown_prob_df.loc[model, col])

        if x_values:
            display_name = MODEL_TO_DISPLAY_NAME.get(model, model)

            # Add overall loss rate to legend
            if model in overall_win_rate_df.index:
                loss_rate_pct = (1 - overall_win_rate_df.loc[model, "win_rate"]) * 100
                display_name = f"{display_name} ({loss_rate_pct:.0f}%)"

            color = MODEL_TO_COLOR.get(model, None)
            marker = MARKERS[idx % len(MARKERS)]
            ax.plot(
                x_values,
                y_values,
                label=display_name,
                alpha=0.7,
                color=color,
                linewidth=2.5,
                marker=marker,
                markersize=7,
            )

    ax.set_xlabel("Number of Consecutive Rounds Won", fontproperties=label_font)
    ax.set_ylabel("Probability of losing next round", fontproperties=label_font)
    ax.set_title("Falldown probability after win streak", fontproperties=title_font)
    ax.legend(loc="upper right", prop=legend_font)
    ax.grid(True, alpha=0.3)
    ax.yaxis.set_minor_locator(AutoMinorLocator())
    ax.xaxis.set_minor_locator(NullLocator())

    # Set x-axis to show integer ticks
    ax.set_xticks(range(1, 15))
    ax.set_xlim(0.5, max(ax.get_xlim()[1], 14.5))
    for label in ax.get_xticklabels() + ax.get_yticklabels():
        label.set_fontproperties(FontProperties(fname=FONT_BOLD.get_file(), size=14))
    plt.tight_layout()
    plt.savefig(output_file, bbox_inches="tight")
    print(f"Saved falldown probability plot to {output_file}")


def main(log_dir: Path | None = None) -> None:
    """Main function to generate comeback and falldown plots."""
    if log_dir is None:
        log_dir = REPO_DIR / "logs"

    print(f"Loading tournament data from {log_dir}")
    df = load_tournament_data(log_dir)
    print(f"Loaded {len(df)} tournaments")

    comeback_prob_df, falldown_prob_df, overall_win_rate_df = calculate_streak_probabilities(df)

    plot_comeback_probabilities(comeback_prob_df, overall_win_rate_df, ASSETS_DIR / "comeback_probabilities.pdf")
    plot_falldown_probabilities(falldown_prob_df, overall_win_rate_df, ASSETS_DIR / "falldown_probabilities.pdf")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Plot comeback and falldown probabilities after win/loss streaks")
    parser.add_argument("--log-dir", type=Path, help="Path to logs directory")
    args = parser.parse_args()
    main(log_dir=args.log_dir)
