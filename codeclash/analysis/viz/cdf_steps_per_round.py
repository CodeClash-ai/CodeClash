import json

from matplotlib import pyplot as plt
from tqdm.auto import tqdm

from codeclash.constants import LOCAL_LOG_DIR

OUTPUT_FILE = "cdf_steps_per_round.png"


def main():
    # Create data structure of model -> list of steps per round
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
                num_steps = sum([1 for _ in traj["messages"] if _["role"] == "assistant"])
                model_to_steps[p2m[name]].append(num_steps)

    # Plot CDF
    plt.figure(figsize=(10, 6))
    for model, steps in model_to_steps.items():
        sorted_steps = sorted(steps)
        yvals = [i / len(sorted_steps) for i in range(len(sorted_steps))]
        plt.step(sorted_steps, yvals, label=model, where="post")

    plt.xlabel("Steps per Round")
    plt.ylabel("Cumulative Probability")
    plt.title("CDF of Steps per Round by Model")
    plt.legend()
    plt.grid(True)
    plt.savefig(OUTPUT_FILE)
    print(f"Saved CDF plot to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
