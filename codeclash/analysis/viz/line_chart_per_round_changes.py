#!/usr/bin/env python3
"""Plot average lines changed per round for each model.

Produces a cached JSON with the structure the user requested:
{
  "model1": [[3,4,...], [5,6,...], ...]  # 15 lists for rounds 1..15
  ...
}

And writes a PNG with one line per model where each point is the average
lines changed for that round.
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
from codeclash.constants import LOCAL_LOG_DIR

ROUNDS = 15
DATA_CACHE = ASSETS_DIR / "line_chart_per_round_changes.json"
OUTPUT_PNG = ASSETS_DIR / "line_chart_per_round_changes.png"


def _lines_changed_from_patch_text(patch_text: str) -> int:
    """Count added + removed lines in a unified diff string using unidiff.PatchSet.

    Returns 0 if the patch cannot be parsed.
    """
    try:
        ps = PatchSet(patch_text)
    except Exception:
        return 0

    cnt = 0
    for pf in ps:
        for hunk in pf:
            for line in hunk:
                if getattr(line, "is_added", False) or getattr(line, "is_removed", False):
                    cnt += 1
    return cnt


def build_data(log_dir: Path):
    """Walk logs and build model -> list[list[int]] for rounds 1..ROUNDS.

    Returns a dict where each model maps to a list of ROUNDS lists, where each
    inner list contains ints = number of lines changed in that game/round by
    that model.
    """
    model_to_round_lines = {}

    tournaments = [x.parent for x in log_dir.rglob("metadata.json")]
    for game_log_folder in tqdm(tournaments, desc="Scanning tournaments"):
        try:
            with open(game_log_folder / "metadata.json") as f:
                metadata = json.load(f)
        except Exception:
            continue

        try:
            p2m = {x["name"]: x["config"]["model"]["model_name"].strip("@") for x in metadata["config"]["players"]}
        except Exception:
            # malformed metadata
            continue

        # ensure models exist in dict
        for model in set(p2m.values()):
            model_to_round_lines.setdefault(model, [[] for _ in range(ROUNDS)])

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

                num_lines = _lines_changed_from_patch_text(patch_text)
                model_to_round_lines.setdefault(model, [[] for _ in range(ROUNDS)])[round_idx - 1].append(num_lines)

    return model_to_round_lines


def plot_averages(model_to_round_lines, out_png: Path):
    """Plot average lines changed per round for each model and save PNG."""
    # compute averages per round
    model_to_avg = {}
    for model, rounds_lists in model_to_round_lines.items():
        # pad/truncate to ROUNDS
        if len(rounds_lists) < ROUNDS:
            rounds_lists = rounds_lists + [[] for _ in range(ROUNDS - len(rounds_lists))]

        avgs = []
        for lst in rounds_lists[:ROUNDS]:
            if lst:
                nums = [int(x) for x in lst]
                # Remove top 5% outliers
                sorted_nums = sorted(nums)
                cutoff_index = int(len(sorted_nums) * 0.99)
                filtered_nums = sorted_nums[:cutoff_index]
                avgs.append(mean(filtered_nums) if filtered_nums else 0.0)
            else:
                avgs.append(0.0)
        model_to_avg[model] = avgs

    # Print a short summary
    print("Average lines changed per round (first 15 rounds):")
    for model, avgs in model_to_avg.items():
        print(f" - {model}: " + ", ".join([f"{v:.1f}" for v in avgs]))

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
    plt.ylabel("Average Lines Changed", fontsize=18, fontproperties=FONT_BOLD)
    plt.xticks(x, fontproperties=FONT_BOLD, fontsize=18)
    plt.yticks(fontproperties=FONT_BOLD, fontsize=18)
    FONT_BOLD.set_size(18)
    # plt.legend(bbox_to_anchor=(1, 1), loc="upper left", prop=FONT_BOLD)
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

    plot_averages(model_to_round_lines, OUTPUT_PNG)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Plot average lines changed per round by model")
    parser.add_argument("-d", "--log_dir", type=Path, default=LOCAL_LOG_DIR, help="Path to game logs")
    args = parser.parse_args()
    main(args.log_dir)
