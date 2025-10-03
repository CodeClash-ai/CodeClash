import argparse
import json
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from tqdm import tqdm

from codeclash.constants import LOCAL_LOG_DIR


def main(log_dir: Path):
    win_streaks = defaultdict(list)

    for metadata_file in tqdm(list(log_dir.rglob("metadata.json")), desc="Processing tournaments"):
        try:
            metadata = json.load(open(metadata_file))
            p2m = {x["name"]: x["config"]["model"]["model_name"].strip("@") for x in metadata["config"]["players"]}

            if len(p2m) != 2:
                continue

            # Skip tournaments where both players use the same model
            models_in_tournament = list(p2m.values())
            if len(set(models_in_tournament)) < 2:
                continue

            round_stats = metadata.get("round_stats", {})

            # Track consecutive wins for each model
            current_streaks = defaultdict(int)
            models = list(p2m.values())

            # Process rounds in order (skip round 0)
            for round_id in sorted(round_stats.keys(), key=int):
                if round_id == "0":
                    continue

                round_data = round_stats[round_id]
                winner = round_data.get("winner")

                if winner in p2m:
                    winner_model = p2m[winner]

                    # Update streaks
                    for model in models:
                        if model == winner_model:
                            current_streaks[model] += 1
                        else:
                            if current_streaks[model] > 0:
                                win_streaks[model].append(current_streaks[model])
                                current_streaks[model] = 0

            # Record any remaining streaks at tournament end
            for model in models:
                if current_streaks[model] > 0:
                    win_streaks[model].append(current_streaks[model])

        except:
            continue

    # Create box plot visualization
    models = sorted(win_streaks.keys())
    clean_names = [m.split("/")[-1] for m in models]

    # Prepare data for box plot - filter out models with no streaks
    box_data = []
    valid_models = []
    valid_clean_names = []

    for i, model in enumerate(models):
        streaks = win_streaks[model]
        if streaks:  # Only include models that have streaks
            box_data.append(streaks)
            valid_models.append(model)
            valid_clean_names.append(clean_names[i])

    if not box_data:
        print("No streak data found!")
        return

    plt.figure(figsize=(12, 8))

    # Create box plot
    bp = plt.boxplot(box_data, tick_labels=valid_clean_names, patch_artist=True, showmeans=False)

    # Customize box plot appearance
    for patch in bp["boxes"]:
        patch.set_facecolor("#3498db")
        patch.set_alpha(0.7)

    for whisker in bp["whiskers"]:
        whisker.set_color("#2c3e50")
        whisker.set_linewidth(2)

    for cap in bp["caps"]:
        cap.set_color("#2c3e50")
        cap.set_linewidth(2)

    # Hide the default median lines
    for median in bp["medians"]:
        median.set_visible(False)

    # Add mean and median markers
    means = [np.mean(streaks) for streaks in box_data]
    medians = [np.median(streaks) for streaks in box_data]

    plt.scatter(range(1, len(means) + 1), means, color="#f39c12", s=50, zorder=3, marker="D", label="Mean")
    plt.scatter(range(1, len(medians) + 1), medians, color="#e74c3c", s=50, zorder=3, marker="s", label="Median")

    plt.xlabel("Model")
    plt.ylabel("Win Streak Length")
    plt.title("Win Streak Length Distribution by Model", fontweight="bold")
    plt.xticks(rotation=45, ha="right")
    plt.grid(True, alpha=0.3, axis="y")

    # Create custom legend
    from matplotlib.lines import Line2D

    legend_elements = [
        Line2D([0], [0], marker="s", color="w", markerfacecolor="#e74c3c", markersize=8, label="Median"),
        Line2D([0], [0], marker="D", color="w", markerfacecolor="#f39c12", markersize=8, label="Mean"),
    ]
    plt.legend(handles=legend_elements)
    plt.tight_layout()
    plt.savefig("box_plots_win_streaks.png", dpi=300, bbox_inches="tight")
    print("Win streak box plots saved to box_plots_win_streaks.png")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyze model win streak distributions with box plots")
    parser.add_argument("-d", "--log_dir", type=Path, default=LOCAL_LOG_DIR, help="Path to logs")
    args = parser.parse_args()
    main(args.log_dir)
