#!/usr/bin/env python3
import json

from matplotlib import pyplot as plt
from tqdm.auto import tqdm

from codeclash.analysis.viz.utils import ASSETS_DIR, FONT_BOLD, MODEL_TO_COLOR, MODEL_TO_DISPLAY_NAME
from codeclash.constants import LOCAL_LOG_DIR

ROUNDS = 15
OUTPUT_FILE = ASSETS_DIR / "line_chart_steps_per_round.pdf"
DATA_CACHE = ASSETS_DIR / "line_chart_steps_per_round.json"


def main():
    model_to_round_steps = {}

    if not DATA_CACHE.exists():
        tournaments = [x.parent for x in LOCAL_LOG_DIR.rglob("metadata.json")]
        for game_log_folder in tqdm(tournaments, desc="Scanning tournaments"):
            try:
                with open(game_log_folder / "metadata.json") as f:
                    metadata = json.load(f)
            except Exception:
                continue

            try:
                p2m = {
                    x["name"]: x["config"]["model"]["model_name"].strip("@").split("/")[-1]
                    for x in metadata["config"]["players"]
                }
            except Exception:
                # malformed metadata
                continue

            # ensure models exist
            for model in set(p2m.values()):
                model_to_round_steps.setdefault(model, [[] for _ in range(ROUNDS)])

            for player_name, model in p2m.items():
                traj_files = (game_log_folder / "players" / player_name).rglob("*.traj.json")
                for traj_file in traj_files:
                    m = traj_file.name.rsplit("_r", 1)
                    if len(m) != 2:
                        continue
                    try:
                        round_part = m[1]
                        round_idx = int(round_part.split(".")[0])
                    except Exception:
                        continue
                    if round_idx < 1 or round_idx > ROUNDS:
                        continue

                    try:
                        with open(traj_file) as f:
                            traj = json.load(f)
                    except Exception:
                        continue

                    num_steps = sum(1 for _ in traj.get("messages", []) if _["role"] == "assistant")
                    model_to_round_steps[model][round_idx - 1].append(num_steps)

        with open(DATA_CACHE, "w") as f:
            json.dump(model_to_round_steps, f, indent=2)

    with open(DATA_CACHE) as f:
        model_to_round_steps = json.load(f)

    # Compute averages per round and plot
    model_to_avg = {}
    for model, rounds_lists in model_to_round_steps.items():
        # pad/truncate
        if len(rounds_lists) < ROUNDS:
            rounds_lists = rounds_lists + [[] for _ in range(ROUNDS - len(rounds_lists))]
        avgs = []
        for lst in rounds_lists[:ROUNDS]:
            if lst:
                nums = [int(x) for x in lst]
                sorted_nums = sorted(nums)
                cutoff_index = max(1, int(len(sorted_nums) * 0.99))
                filtered = sorted_nums[:cutoff_index]
                avgs.append(sum(filtered) / len(filtered) if filtered else 0.0)
            else:
                avgs.append(0.0)
        model_to_avg[model] = avgs

    # Print summary
    print("Average steps per round (first 15 rounds):")
    for model, avgs in model_to_avg.items():
        display = MODEL_TO_DISPLAY_NAME.get(model, model)
        print(f" - {display} ({model}): " + ", ".join([f"{v:.1f}" for v in avgs]))

    # Plot
    plt.figure(figsize=(8, 8))
    x = list(range(1, ROUNDS + 1))
    ymax = 0
    for model, avgs in model_to_avg.items():
        display = MODEL_TO_DISPLAY_NAME.get(model, model)
        color = MODEL_TO_COLOR.get(model, None)
        plt.plot(x, avgs, marker="o", label=display, linewidth=1.5, markersize=6, color=color)
        ymax = max(ymax, max(avgs) if avgs else 0)

    plt.xlabel("Round", fontsize=18, fontproperties=FONT_BOLD)
    plt.xticks(x, fontproperties=FONT_BOLD, fontsize=18)
    plt.yticks(fontproperties=FONT_BOLD, fontsize=18)
    plt.grid(True, alpha=0.3)
    plt.ylim(5, max(10, ymax + 5))
    plt.tight_layout()
    plt.savefig(OUTPUT_FILE, dpi=300, bbox_inches="tight")
    print(f"Saved line chart to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
