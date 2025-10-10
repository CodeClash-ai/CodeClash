#!/usr/bin/env python3
import json
import re

from matplotlib import pyplot as plt
from tqdm.auto import tqdm

from codeclash.analysis.viz.utils import ASSETS_DIR, FONT_BOLD, FONT_REG, MODEL_TO_COLOR, MODEL_TO_DISPLAY_NAME
from codeclash.constants import LOCAL_LOG_DIR

OUTPUT_FILE = ASSETS_DIR / "cdf_thought_length_per_round.png"
DATA_CACHE = ASSETS_DIR / "cdf_thought_length_per_round.json"


def main():
    model_to_steps = {}

    if not DATA_CACHE.exists():
        tournaments = [x.parent for x in LOCAL_LOG_DIR.rglob("metadata.json")]
        for game_log_folder in tqdm(tournaments):
            with open(game_log_folder / "metadata.json") as f:
                metadata = json.load(f)
            try:
                p2m = {x["name"]: x["config"]["model"]["model_name"].strip("@") for x in metadata["config"]["players"]}
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
                    for message in traj["messages"]:
                        if message["role"] != "assistant":
                            continue
                        content = message.get("content", "")

                        # Extract THOUGHT section
                        thought_match = re.search(r"THOUGHT:(.+?)```bash", content, re.DOTALL | re.IGNORECASE)
                        if not thought_match:
                            continue

                        thought = thought_match.group(1).strip()
                        thought_length = len(thought.split())
                        model_to_steps[p2m[name]].append(thought_length)

        with open(DATA_CACHE, "w") as f:
            json.dump(model_to_steps, f, indent=2)

    with open(DATA_CACHE) as f:
        model_to_steps = json.load(f)

    # Plot CDF
    plt.figure(figsize=(8, 8))
    for model, thought_length in model_to_steps.items():
        sorted_steps = sorted(thought_length)
        yvals = [i / len(sorted_steps) for i in range(len(sorted_steps))]
        plt.step(sorted_steps, yvals, label=MODEL_TO_DISPLAY_NAME[model], where="post", color=MODEL_TO_COLOR[model])

    LIM = 200
    plt.xlim(0, LIM)
    plt.xticks(range(0, LIM + 1, 20), fontsize=18, fontproperties=FONT_REG)
    plt.yticks([i / 10 for i in range(11)], [f"{i * 10}%" for i in range(11)], fontsize=18, fontproperties=FONT_REG)
    plt.xlabel("Thought length (in words) per action", fontproperties=FONT_BOLD, fontsize=18)
    # plt.ylabel("Cumulative Probability")
    # plt.title("CDF of Thought Length (in Words) per Round by Model")
    FONT_BOLD.set_size(14)
    plt.legend(prop=FONT_BOLD)
    plt.grid(True)
    plt.savefig(OUTPUT_FILE, dpi=300, bbox_inches="tight")
    print(f"Saved CDF plot to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
