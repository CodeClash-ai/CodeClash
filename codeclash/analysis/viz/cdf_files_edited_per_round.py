#!/usr/bin/env python3
import json

from matplotlib import pyplot as plt
from tqdm.auto import tqdm
from unidiff import PatchSet

from codeclash.analysis.viz.utils import ASSETS_DIR, FONT_BOLD, FONT_REG, MODEL_TO_COLOR, MODEL_TO_DISPLAY_NAME
from codeclash.constants import LOCAL_LOG_DIR

OUTPUT_FILE = ASSETS_DIR / "cdf_files_edited_per_round.pdf"
DATA_CACHE = ASSETS_DIR / "cdf_files_edited_per_round.json"


def main():
    model_to_num_files = {}

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
                    if model not in model_to_num_files:
                        model_to_num_files[model] = []
            except KeyError:
                continue

            for name in p2m.keys():
                changes_files = (game_log_folder / "players" / name).rglob("changes_r*.json")
                for changes_file in changes_files:
                    with open(changes_file) as f:
                        changes = json.load(f)
                    try:
                        num_files = len(PatchSet(changes["incremental_diff"]))
                    except Exception as e:
                        print(f"Issue parsing diff in {changes_file}, skipping: {e}")
                        continue
                    model_to_num_files[p2m[name]].append(num_files)

        with open(DATA_CACHE, "w") as f:
            json.dump(model_to_num_files, f, indent=2)

    with open(DATA_CACHE) as f:
        model_to_num_files = json.load(f)

    # Plot CDF
    plt.figure(figsize=(6, 6))
    for model, files_edited in model_to_num_files.items():
        sorted_files_edited = sorted(files_edited)
        yvals = [i / len(sorted_files_edited) for i in range(len(sorted_files_edited))]
        plt.step(
            sorted_files_edited, yvals, label=MODEL_TO_DISPLAY_NAME[model], where="post", color=MODEL_TO_COLOR[model]
        )

    LIM = 20
    plt.xlim(0, LIM)  # Limit x-axis to 40 for better visibility
    plt.xticks(range(0, LIM + 1, 5), fontsize=18, fontproperties=FONT_REG)
    plt.yticks([i / 10 for i in range(11)], [f"{i * 10}%" for i in range(11)], fontsize=18, fontproperties=FONT_REG)
    plt.xlabel("Files Edited per Round", fontproperties=FONT_BOLD, fontsize=18)
    # plt.ylabel("Cumulative Probability", fontproperties=FONT_BOLD, fontsize=18)
    # plt.title("CDF of Files Edited per Round by Model")
    FONT_BOLD.set_size(18)
    plt.legend(prop=FONT_BOLD)
    plt.grid(True)
    plt.savefig(OUTPUT_FILE, dpi=300, bbox_inches="tight")
    print(f"Saved CDF plot to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
