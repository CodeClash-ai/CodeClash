import argparse
import json
from collections import defaultdict
from pathlib import Path

import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np
from tqdm.auto import tqdm

from codeclash.analysis.viz.utils import ASSETS_DIR, FONT_BOLD, MODEL_TO_DISPLAY_NAME
from codeclash.constants import LOCAL_LOG_DIR

DATA_CACHE = ASSETS_DIR / "heatmap_returncode.json"


def main(logs: Path):
    model_to_arena_to_return_codes = {}
    if not DATA_CACHE.exists():
        tournaments = [x.parent for x in logs.rglob("metadata.json")]
        for game_log_folder in tqdm(tournaments):
            arena = game_log_folder.name.split(".", 2)[1]
            with open(game_log_folder / "metadata.json") as f:
                metadata = json.load(f)
            try:
                p2m = {
                    x["name"]: x["config"]["model"]["model_name"].strip("@").split("/")[-1]
                    for x in metadata["config"]["players"]
                }
                for model in p2m.values():
                    if model not in model_to_arena_to_return_codes:
                        model_to_arena_to_return_codes[model] = {}
                    if arena not in model_to_arena_to_return_codes[model]:
                        model_to_arena_to_return_codes[model][arena] = {"actions": 0, "malformed": 0}
            except KeyError:
                continue

            for name in p2m.keys():
                traj_files = (game_log_folder / "players" / name).rglob("*.traj.json")
                for traj_file in traj_files:
                    with open(traj_file) as f:
                        traj = json.load(f)
                    msgs = traj["messages"][2:]  # Skip system prompt and first user message
                    observations = [msg for msg in msgs if msg["role"] == "user"]
                    actions = len(observations)
                    malformed = 0
                    for obs in observations:
                        if isinstance(obs["content"], str):
                            malformed += "<returncode>0</returncode>" not in obs["content"]
                        elif isinstance(obs["content"], list):
                            malformed += "<returncode>0</returncode>" not in obs["content"][0]["text"]
                        else:
                            print(f"Unknown content type: {type(obs['content'])}")
                    model_to_arena_to_return_codes[p2m[name]][arena]["actions"] += actions
                    model_to_arena_to_return_codes[p2m[name]][arena]["malformed"] += malformed

        with open(DATA_CACHE, "w") as f:
            json.dump(model_to_arena_to_return_codes, f, indent=2)

    with open(DATA_CACHE) as f:
        model_to_arena_to_return_codes = json.load(f)

    model_to_return_code = defaultdict(tuple)
    for model, arena_to_return_codes in model_to_arena_to_return_codes.items():
        a, m = 0, 0
        for arena, data in arena_to_return_codes.items():
            malform_rate = data["malformed"] / data["actions"] * 100
            a += data["actions"]
            m += data["malformed"]
            print(
                f"- {model} in {arena}: {data['actions']} actions; {data['malformed']} malformed ({malform_rate:.2f}%)"
            )
        model_to_return_code[model] = (m, a, m / a * 100)
    print("=" * 20)
    for model, (_m, _a, rate) in model_to_return_code.items():
        print(f"{MODEL_TO_DISPLAY_NAME[model]}: {rate:.2f}% average malform rate")
    print("=" * 20)

    # Calculate average malform rate per arena
    arena_to_stats = defaultdict(lambda: {"total_actions": 0, "total_malformed": 0})
    for _model, arena_to_return_codes in model_to_arena_to_return_codes.items():
        for arena, data in arena_to_return_codes.items():
            arena_to_stats[arena]["total_actions"] += data["actions"]
            arena_to_stats[arena]["total_malformed"] += data["malformed"]

    print("Arena-wise malform rates:")
    for arena in sorted(arena_to_stats.keys()):
        stats = arena_to_stats[arena]
        if stats["total_actions"] > 0:
            rate = stats["total_malformed"] / stats["total_actions"] * 100
            print(f"{arena}: {rate:.2f}% malform rate ({stats['total_malformed']}/{stats['total_actions']})")
    print("=" * 20)

    overall_rate = sum(m / a * 100 for m, a, _ in model_to_return_code.values()) / len(model_to_return_code)
    print(f"Overall: {overall_rate:.2f}% average malform rate")

    # Create heatmap data
    models = list(model_to_arena_to_return_codes.keys())
    arenas = set()
    for arena_data in model_to_arena_to_return_codes.values():
        arenas.update(arena_data.keys())
    arenas = sorted(list(arenas))

    # Create matrix for heatmap
    heatmap_data = np.zeros((len(models), len(arenas)))
    for i, model in enumerate(models):
        for j, arena in enumerate(arenas):
            if arena in model_to_arena_to_return_codes[model]:
                data = model_to_arena_to_return_codes[model][arena]
                if data["actions"] > 0:
                    heatmap_data[i, j] = data["malformed"] / data["actions"] * 100

    # Create heatmap
    plt.figure(figsize=(6, 6))
    cmap = mcolors.LinearSegmentedColormap.from_list("br", ["#ffffff", "#e74c3c"])
    plt.imshow(heatmap_data, cmap=cmap, aspect="auto")

    # Set labels
    plt.xticks(range(len(arenas)), arenas, rotation=45, ha="right", fontproperties=FONT_BOLD, fontsize=14)
    plt.yticks(
        range(len(models)), [MODEL_TO_DISPLAY_NAME.get(m, m) for m in models], fontproperties=FONT_BOLD, fontsize=14
    )

    # Add colorbar
    # cbar = plt.colorbar(im)
    # cbar.set_label('Malformed Rate (%)', fontproperties=FONT_BOLD, fontsize=14)

    # Add text annotations (percentage, styled like win streak heatmap)
    for i in range(len(models)):
        for j in range(len(arenas)):
            percentage = heatmap_data[i, j]
            if percentage > 0:
                color = "white" if percentage > 40 else "black"
                plt.text(
                    j,
                    i,
                    f"{percentage:.1f}%",
                    ha="center",
                    va="center",
                    color=color,
                    fontweight="bold",
                    fontsize=12,
                    fontproperties=FONT_BOLD,
                )

    # plt.title('Malformed Return Code Rate by Model and Arena', fontproperties=FONT_BOLD, fontsize=18)
    # plt.xlabel('Arena', fontproperties=FONT_BOLD, fontsize=18)
    # plt.ylabel('Model', fontproperties=FONT_BOLD, fontsize=18)
    plt.tight_layout()
    plt.savefig(ASSETS_DIR / "heatmap_returncode.png", dpi=300, bbox_inches="tight")
    plt.show()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-l", "--logs", type=Path, default=LOCAL_LOG_DIR)
    args = parser.parse_args()
    main(**vars(args))
