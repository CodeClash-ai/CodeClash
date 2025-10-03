#!/usr/bin/env python3
import json
import re

from matplotlib import pyplot as plt
from tqdm.auto import tqdm

from codeclash.constants import LOCAL_LOG_DIR

OUTPUT_FILE = "cdf_thought_length_per_round.png"


def main():
    model_to_steps = {}

    tournaments = [x.parent for x in LOCAL_LOG_DIR.rglob("game.log")]
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

    # Plot CDF
    plt.figure(figsize=(10, 6))
    for model, thought_length in model_to_steps.items():
        sorted_steps = sorted(thought_length)
        yvals = [i / len(sorted_steps) for i in range(len(sorted_steps))]
        plt.step(sorted_steps, yvals, label=model, where="post")

    plt.xlim(0, 500)
    plt.xlabel("Thought Length (in Words) per Round")
    plt.ylabel("Cumulative Probability")
    plt.title("CDF of Thought Length (in Words) per Round by Model")
    plt.legend()
    plt.grid(True)
    plt.savefig(OUTPUT_FILE)
    print(f"Saved CDF plot to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
