"""Plot average lines changed (for README_agent.md, submission file/folder, others) per round for each model.

Produces a cached JSON with the structure:
{
    "model1": {
        "README_agent.md": [[3,4,...], [5,6,...], ...],  # 15 lists for rounds 1..15
        "submission": [[3,4,...], [5,6,...], ...],
        "others": [[3,4,...], [5,6,...], ...]
    },
    "model2": { ... },
    ...
}

And creates a PNG with two lines per model:
- one line for average lines changed in README_agent.md per round
- one line for average lines changed in submission file/folder per round
"""

import argparse
import json
import re
from pathlib import Path
from statistics import mean

from matplotlib import pyplot as plt
from tqdm.auto import tqdm
from unidiff import PatchSet

from codeclash.analysis.viz.utils import ASSETS_DIR, FONT_BOLD, MODEL_TO_COLOR, MODEL_TO_DISPLAY_NAME
from codeclash.arenas import ARENAS
from codeclash.constants import LOCAL_LOG_DIR

ROUNDS = 15
DATA_CACHE = ASSETS_DIR / "line_chart_per_round_specific.json"
OUTPUT_PNG_README = ASSETS_DIR / "line_chart_per_round_changes_readme.pdf"
OUTPUT_PNG_SUBMISSION = ASSETS_DIR / "line_chart_per_round_changes_submission.pdf"

MAP_GAME_TO_SUBMISSION_FILE = {a.name: a.submission for a in ARENAS}


def _lines_changed_from_patch_text(patch_text: str, arena: str) -> dict[str, int]:
    """Count added + removed lines in a unified diff string using unidiff.PatchSet.

    Returns {} if the patch cannot be parsed.
    """
    rv = {"README_agent.md": 0, "submission": 0, "others": 0}
    try:
        ps = PatchSet(patch_text)
    except Exception:
        return rv

    submission = MAP_GAME_TO_SUBMISSION_FILE[arena]

    for pf in ps:
        cnt = 0
        for hunk in pf:
            for line in hunk:
                if getattr(line, "is_added", False) or getattr(line, "is_removed", False):
                    cnt += 1
        filename = pf.path
        if filename == "README_agent.md":
            rv["README_agent.md"] += cnt
        elif submission in filename:
            rv["submission"] += cnt
        else:
            rv["others"] += cnt

    return rv


def build_data(log_dir: Path):
    """Walk logs and build model -> list[list[int]] for rounds 1..ROUNDS.

    Returns a dict where each model maps to a list of ROUNDS lists, where each
    inner list contains ints = number of lines changed in that game/round by
    that model.
    """
    model_to_files = {}

    tournaments = [x.parent for x in log_dir.rglob("metadata.json")]
    for game_log_folder in tqdm(tournaments, desc="Scanning tournaments"):
        arena = game_log_folder.stem.split(".", 2)[1]  # e.g. "RobotRumble", "BattleSnake"
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

        # ensure models exist in dict
        for model in set(p2m.values()):
            model_to_files.setdefault(
                model,
                {
                    "README_agent.md": [[] for _ in range(ROUNDS)],
                    "submission": [[] for _ in range(ROUNDS)],
                    "others": [[] for _ in range(ROUNDS)],
                },
            )

        # collect changes files per player
        for player_name, model in p2m.items():
            changes_files = (game_log_folder / "players" / player_name).rglob("changes_r*.json")
            for changes_file in changes_files:
                m = re.search(r"changes_r(\d+)\.json", changes_file.name)
                if not m:
                    continue
                round_idx = int(m.group(1))
                if round_idx < 1 or round_idx > ROUNDS:
                    continue

                try:
                    with open(changes_file) as f:
                        changes = json.load(f)
                except Exception:
                    continue

                patch_text = changes.get("incremental_diff")
                if not patch_text:
                    # no diff recorded for this round
                    continue

                file_to_num_lines = _lines_changed_from_patch_text(patch_text, arena)
                for file_type, num_lines in file_to_num_lines.items():
                    model_to_files[model][file_type][round_idx - 1].append(num_lines)

    return model_to_files


def plot_averages(model_to_files, out_png: Path, file_types=None):
    """Plot average lines changed per round for each model and save PNG.

    file_types: iterable of file-type keys to include (e.g. ["README_agent.md"] or ["submission"]).
    """
    if file_types is None:
        file_types = ["README_agent.md", "submission"]

    # compute averages per round for requested file-types
    model_to_avg = {}
    for model, file_dict in model_to_files.items():
        model_to_avg[model] = {}
        for ft in file_types:
            rounds_lists = file_dict.get(ft, [[] for _ in range(ROUNDS)])
            # pad/truncate to ROUNDS
            if len(rounds_lists) < ROUNDS:
                rounds_lists = rounds_lists + [[] for _ in range(ROUNDS - len(rounds_lists))]

            avgs = []
            for lst in rounds_lists[:ROUNDS]:
                if lst:
                    nums = [int(x) for x in lst]
                    # Remove top 1% outliers (keep 99% of the data). Ensure at least one element remains.
                    sorted_nums = sorted(nums)
                    cutoff_index = max(1, int(len(sorted_nums) * 0.95))
                    filtered_nums = sorted_nums[:cutoff_index]
                    avgs.append(mean(filtered_nums) if filtered_nums else 0.0)
                else:
                    avgs.append(0.0)
            model_to_avg[model][ft] = avgs

    # Print a short summary per requested file type
    print("Average lines changed per round (first 15 rounds):")
    for model, ft_map in model_to_avg.items():
        display = MODEL_TO_DISPLAY_NAME.get(model, model)
        parts = []
        for ft in file_types:
            avgs = ft_map.get(ft, [0.0] * ROUNDS)
            parts.append(
                ("README" if ft == "README_agent.md" else "Submission") + ": " + ", ".join([f"{v:.1f}" for v in avgs])
            )
        print(f" - {display} ({model}): " + " | ".join(parts))

    # Plot
    plt.figure(figsize=(8, 8))
    x = list(range(1, ROUNDS + 1))
    ymax = 0
    # different line styles for file types so users can distinguish them
    for model, ft_map in model_to_avg.items():
        display = MODEL_TO_DISPLAY_NAME.get(model, model)
        color = MODEL_TO_COLOR.get(model, None)
        for ft, avgs in ft_map.items():
            # label for legend: if plotting only one file-type, label by model; if multiple, include file-type
            if len(file_types) == 1:
                label = display
            else:
                label = f"{display} — {'README' if ft == 'README_agent.md' else 'Submission'}"
            plt.plot(x, avgs, marker="o", label=label, linewidth=1.5, markersize=6, color=color)
            ymax = max(ymax, max(avgs) if avgs else 0)

    plt.xlabel("Round", fontsize=18, fontproperties=FONT_BOLD)
    if out_png == OUTPUT_PNG_README:
        plt.ylabel("Average Lines Changed", fontsize=18, fontproperties=FONT_BOLD)
    # ylabel removed; explained in figure caption
    plt.xticks(x, fontproperties=FONT_BOLD, fontsize=18)
    # make y-tick labels use the same bold font
    plt.yticks(fontproperties=FONT_BOLD, fontsize=18)
    FONT_BOLD.set_size(12)
    # plt.legend(prop=FONT_BOLD, loc="upper right")
    plt.grid(True, alpha=0.3)
    plt.ylim(0, max(10, ymax + 5))
    plt.tight_layout()
    plt.savefig(out_png, dpi=300, bbox_inches="tight")
    print(f"Saved line chart to {out_png}")


def main(log_dir: Path):
    if DATA_CACHE.exists():
        try:
            with open(DATA_CACHE) as f:
                model_to_round_lines = json.load(f)
        except Exception:
            model_to_round_lines = build_data(log_dir)
            with open(DATA_CACHE, "w") as f:
                json.dump(model_to_round_lines, f, indent=2)
    else:
        model_to_round_lines = build_data(log_dir)
        with open(DATA_CACHE, "w") as f:
            json.dump(model_to_round_lines, f, indent=2)

    # Separate charts: one for README changes, one for submission changes
    plot_averages(model_to_round_lines, OUTPUT_PNG_README, file_types=["README_agent.md"])
    plot_averages(model_to_round_lines, OUTPUT_PNG_SUBMISSION, file_types=["submission"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Plot average lines changed per round by model")
    parser.add_argument("-d", "--log_dir", type=Path, default=LOCAL_LOG_DIR, help="Path to game logs")
    args = parser.parse_args()
    main(args.log_dir)
