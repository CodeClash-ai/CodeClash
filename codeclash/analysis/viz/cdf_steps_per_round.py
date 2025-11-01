#!/usr/bin/env python3
import json

from matplotlib import pyplot as plt
from tqdm.auto import tqdm

from codeclash.analysis.viz.utils import ASSETS_DIR, FONT_BOLD, MODEL_TO_COLOR, MODEL_TO_DISPLAY_NAME
from codeclash.constants import LOCAL_LOG_DIR

OUTPUT_FILE = ASSETS_DIR / "cdf_steps_per_round.pdf"
DATA_CACHE = ASSETS_DIR / "cdf_steps_per_round.json"


def main():
    model_to_steps = {}

    if not DATA_CACHE.exists():
        tournaments = [x.parent for x in LOCAL_LOG_DIR.rglob("metadata.json")]
        for game_log_folder in tqdm(tournaments):
            with open(game_log_folder / "metadata.json") as f:
                metadata = json.load(f)
            try:
                p2m = {
                    x["name"]: x["config"]["model"]["model_name"].strip("@").split("/")[-1]
                    for x in metadata["config"]["players"]
                }
                for model in p2m.values():
                    if model not in model_to_steps:
                        model_to_steps[model] = []
            except KeyError:
                continue

            for name in p2m.keys():
                traj_files = (game_log_folder / "players" / name).rglob("*.traj.json")
                for traj_file in traj_files:
                    with open(traj_file) as f:
                        traj = json.load(f)
                    num_steps = sum([1 for _ in traj["messages"] if _["role"] == "assistant"])
                    model_to_steps[p2m[name]].append(num_steps)

        with open(DATA_CACHE, "w") as f:
            json.dump(model_to_steps, f, indent=2)

    with open(DATA_CACHE) as f:
        model_to_steps = json.load(f)

    for model, steps in model_to_steps.items():
        step_limit_exceeded = sum(1 for s in steps if s == 30) / len(steps) * 100
        print(
            f"- {model}: {len(steps)} rounds; avg {sum(steps) / len(steps):.2f} steps/round; 30-step limit exceeded: {step_limit_exceeded:.2f}%"
        )

    # Plot CDF
    plt.figure(figsize=(6, 6))
    for model, steps in model_to_steps.items():
        sorted_steps = sorted(steps)
        yvals = [i / len(sorted_steps) for i in range(len(sorted_steps))]
        plt.step(sorted_steps, yvals, label=MODEL_TO_DISPLAY_NAME[model], where="post", color=MODEL_TO_COLOR[model])

    plt.xticks(range(0, 31, 5), fontsize=18, fontproperties=FONT_BOLD)
    plt.yticks([i / 10 for i in range(11)], [f"{i * 10}%" for i in range(11)], fontsize=18, fontproperties=FONT_BOLD)
    plt.xlabel("Steps per Round", fontproperties=FONT_BOLD, fontsize=18)
    # plt.ylabel("Cumulative Probability")
    # plt.title("CDF of Steps per Round by Model")
    FONT_BOLD.set_size(18)
    plt.legend(prop=FONT_BOLD)
    plt.grid(True)
    plt.savefig(OUTPUT_FILE, dpi=300, bbox_inches="tight")
    print(f"Saved CDF plot to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
