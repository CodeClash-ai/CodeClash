import json

from matplotlib import pyplot as plt
from tqdm.auto import tqdm

from codeclash.constants import LOCAL_LOG_DIR

OUTPUT_FILE = "cdf_files_edited_per_round.png"


def main():
    model_to_num_files = {}

    tournaments = [x.parent for x in LOCAL_LOG_DIR.rglob("game.log")]
    for game_log_folder in tqdm(tournaments):
        with open(game_log_folder / "metadata.json") as f:
            metadata = json.load(f)
        try:
            p2m = {x["name"]: x["config"]["model"]["model_name"].strip("@") for x in metadata["config"]["players"]}
            for model in p2m.values():
                if model not in model_to_num_files:
                    model_to_num_files[model] = []
        except KeyError:
            continue

        for name in p2m.keys():
            changes_files = (game_log_folder / "players" / name).rglob("changes_r*.json")
            for changes_file in changes_files:
                with open(changes_file) as f:
                    changes = json.load(f)
                num_files = len(changes["modified_files"])
                model_to_num_files[p2m[name]].append(num_files)

    # Plot CDF
    plt.figure(figsize=(10, 6))
    for model, files_edited in model_to_num_files.items():
        sorted_files_edited = sorted(files_edited)
        yvals = [i / len(sorted_files_edited) for i in range(len(sorted_files_edited))]
        plt.step(sorted_files_edited, yvals, label=model, where="post")

    plt.xlabel("Files Edited per Round")
    plt.ylabel("Cumulative Probability")
    plt.title("CDF of Files Edited per Round by Model")
    plt.legend()
    plt.grid(True)
    plt.savefig(OUTPUT_FILE)
    print(f"Saved CDF plot to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
