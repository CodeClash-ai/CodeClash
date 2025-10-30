"""
Determine how often files are (not) reused across rounds.

General idea - track when a file is created, then see whether / how often it is modified / deleted in later rounds.

Pseudo-code:
- For each tournament:
    - For each player:
        - For each round:
            - Identify any newly created files
"""

import argparse
import json
import re
from collections import defaultdict
from enum import Enum

import pandas as pd
import unidiff
from matplotlib import pyplot as plt
from tqdm.auto import tqdm

from codeclash.analysis.viz.utils import (
    ASSETS_DIR,
    FONT_BOLD,
    MODEL_TO_COLOR,
    MODEL_TO_DISPLAY_NAME,
)
from codeclash.constants import LOCAL_LOG_DIR

SPECIAL_FILES = [
    ".codeclash_exec",
    "README_agent.md",
]

ASSETS_SUBFOLDER = ASSETS_DIR / "code_org"
ASSETS_SUBFOLDER.mkdir(parents=True, exist_ok=True)
DATA_CACHE = ASSETS_SUBFOLDER / "codebase_organization.jsonl"


class FileOperation(Enum):
    CREATED = "created"
    MODIFIED = "modified"
    DELETED = "deleted"
    RENAMED = "renamed"
    REFERENCED = "referenced"


def get_actions(traj: dict) -> list[str]:
    """Returns all actions from a trajectory"""

    def extract_action(action: str):
        pattern = r"```bash(.*?)```"
        match = re.search(pattern, action, re.DOTALL)
        if match:
            return match.group(1).strip()
        return None

    actions = []
    for msg in traj["messages"]:
        if msg["role"] != "assistant":
            continue
        content = msg["content"]
        if isinstance(content, list):
            content = "\n".join([c["text"] for c in content])
        actions.append(extract_action(content))
    return [a for a in actions if a is not None]


def build_data_structure(refresh_cache: bool = False):
    """
    Create following data structure per tournament:

    "player": {
        "tournament": {
            "a.py": [(round_num, operation, added, removed), (2, created, 10, 0), (5, modified, 5, 3), ...],
            "b.java": [(round_num, operation, added, removed), (1, created, 0, 0), (3, deleted, 0, 15), ...],
            ...
        }
    }
    """
    mode = "w" if refresh_cache or not DATA_CACHE.exists() else "a"
    skip = []
    if mode == "a" and DATA_CACHE.exists():
        with open(DATA_CACHE) as f:
            for line in f:
                data = json.loads(line)
                skip.append((data["player"], data["tournament"]))
        print(f"Skipping {len(skip)} entries already in cache.")

    tournaments = [x.parent for x in LOCAL_LOG_DIR.rglob("metadata.json")]
    with open(DATA_CACHE, mode) as f:
        for game_log_folder in tqdm(tournaments):
            with open(game_log_folder / "metadata.json") as m:
                metadata = json.load(m)
            try:
                p2m = {
                    x["name"]: x["config"]["model"]["model_name"].strip("@").split("/")[-1]
                    for x in metadata["config"]["players"]
                }
            except KeyError:
                continue

            for name in p2m.keys():
                if (p2m[name], game_log_folder.name) in skip:
                    continue

                # Track full history of each file: {filename: [(round, operation), ...]}
                file_history = defaultdict(list)

                change_files = sorted(
                    (game_log_folder / "players" / name).rglob("changes_r*.json"),
                    key=lambda x: int(x.stem.split("_r")[-1]),  # Sort by round number
                )

                for change_file in change_files:
                    # Extract round number from filename (e.g., "changes_r5.json" -> 5)
                    round_num = int(change_file.stem.split("_r")[-1])

                    with open(change_file) as c:
                        change = json.load(c)
                    try:
                        patch = unidiff.PatchSet(change["incremental_diff"])
                    except unidiff.errors.UnidiffParseError as e:
                        print(f"[{change_file}] Error parsing diff: {e}")
                        continue

                    # Track all file operations in this round
                    for patched_file in patch:
                        # Ignore binary files
                        if "Binary files" in str(patched_file):
                            continue

                        filename = patched_file.path

                        # Calculate lines added/removed
                        added = patched_file.added
                        removed = patched_file.removed

                        # Determine operation type based on patch properties
                        if patched_file.is_added_file:
                            file_history[filename].append((round_num, FileOperation.CREATED, added, 0))
                        elif patched_file.is_removed_file:
                            file_history[filename].append((round_num, FileOperation.DELETED, 0, removed))
                        elif patched_file.is_rename:
                            # Handle rename: transfer history from old name to new name
                            old_name = patched_file.source_file
                            new_name = patched_file.target_file

                            # Transfer history
                            if old_name in file_history:
                                file_history[new_name] = file_history[old_name].copy()
                                del file_history[old_name]

                            # Record the rename operation
                            file_history[new_name].append((round_num, FileOperation.RENAMED, added, removed))
                        else:
                            # Regular modification
                            file_history[filename].append((round_num, FileOperation.MODIFIED, added, removed))

                    # Check if any files not referenced in this patch were referenced in the trajectory
                    untouched_files = set(file_history.keys()) - {pf.path for pf in patch}
                    if len(untouched_files) > 0:
                        traj_file = game_log_folder / "players" / name / f"{name}_r{round_num}.traj.json"
                        with open(traj_file) as t:
                            traj = json.load(t)
                        actions = get_actions(traj)
                        for action in actions:
                            for filename in untouched_files:
                                without_path = filename.split("/")[-1]
                                if without_path in action:
                                    # File was referenced but not changed
                                    file_history[filename].append((round_num, FileOperation.REFERENCED, 0, 0))

                # Make file history serializable
                for filename in file_history:
                    file_history[filename] = [
                        (rnd, op.value, added, removed) for rnd, op, added, removed in file_history[filename]
                    ]

                # Store file history for this player and tournament
                f.write(
                    json.dumps({"player": p2m[name], "tournament": game_log_folder.name, "file_history": file_history})
                    + "\n"
                )


def calculate_active_file_ratio(file_history: dict, N: int = 5) -> dict:
    if not file_history:
        return {"total_files": 0, "active_files": 0, "active_file_ratio": None}

    existing_files = {f: h for f, h in file_history.items() if not any(op == "deleted" for _, op, _, _ in h)}

    if not existing_files:
        return {"total_files": 0, "active_files": 0, "active_file_ratio": None}

    max_round = max(max(r for r, _, _, _ in h) for h in existing_files.values())
    active_files = sum(1 for h in existing_files.values() if max(r for r, _, _, _ in h) >= max_round - N + 1)
    total_files = len(existing_files)

    return {"total_files": total_files, "active_files": active_files, "active_file_ratio": active_files / total_files}


def analyze_per_player_arena(data: list, N: int = 5) -> pd.DataFrame:
    arena_data = {}
    for entry in data:
        arena = entry["tournament"].split(".", 2)[1]
        key = (entry["player"], arena)

        if key not in arena_data:
            arena_data[key] = {}

        for filename, history in entry["file_history"].items():
            if filename not in arena_data[key]:
                arena_data[key][filename] = []
            arena_data[key][filename].extend(history)

    results = []
    for (player, arena), file_history in arena_data.items():
        stats = calculate_active_file_ratio(file_history, N=N)
        results.append({"player": player, "arena": arena, **stats})

    return pd.DataFrame(results).sort_values(by=["player", "arena"], ignore_index=True)


def analyze_per_player(data: list, N: int = 5) -> pd.DataFrame:
    df = analyze_per_player_arena(data, N=N)
    df = df[df["total_files"] > 0]
    result = df.groupby("player")["active_file_ratio"].agg(["mean", "std", "count"]).reset_index()
    # Calculate standard error of the mean (SEM)
    result["sem"] = result["std"] / (result["count"] ** 0.5)
    return result


def calculate_root_clutter_ratio(file_history: dict) -> dict:
    existing_files = [f for f, h in file_history.items() if not any(op == "deleted" for _, op, _, _ in h)]

    if not existing_files:
        return {"total_files": 0, "root_files": 0, "root_clutter_ratio": None}

    root_files = sum(1 for f in existing_files if "/" not in f)
    total_files = len(existing_files)

    return {"total_files": total_files, "root_files": root_files, "root_clutter_ratio": root_files / total_files}


def analyze_root_clutter_per_player(data: list) -> pd.DataFrame:
    arena_data = {}
    for entry in data:
        arena = entry["tournament"].split(".", 2)[1]
        key = (entry["player"], arena)

        if key not in arena_data:
            arena_data[key] = {}

        for filename, history in entry["file_history"].items():
            if filename not in arena_data[key]:
                arena_data[key][filename] = []
            arena_data[key][filename].extend(history)

    results = []
    for (player, arena), file_history in arena_data.items():
        stats = calculate_root_clutter_ratio(file_history)
        results.append({"player": player, "arena": arena, **stats})

    df = pd.DataFrame(results)
    df = df[df["total_files"] > 0]
    result = df.groupby("player")["root_clutter_ratio"].agg(["mean", "std", "count"]).reset_index()
    # Calculate standard error of the mean (SEM)
    result["sem"] = result["std"] / (result["count"] ** 0.5)
    return result


def calculate_churn_concentration(file_history: dict, use_magnitude: bool = False) -> dict:
    """Calculate what % of modifications happen on the top 10% most-modified files."""

    # Count modifications per file
    churn_counts = {}
    for filename, history in file_history.items():
        if use_magnitude:
            # Sum lines added + removed for modifications only
            churn = sum(added + removed for _, op, added, removed in history if op == "modified")
        else:
            # Count modification events
            churn = sum(1 for _, op, _, _ in history if op == "modified")

        if churn > 0:
            churn_counts[filename] = churn

    if not churn_counts:
        return {"total_churn": 0, "churn_concentration": None, "files_modified": 0}

    total_churn = sum(churn_counts.values())
    num_files = len(churn_counts)

    # Get top 10% of files by churn
    top_n = max(1, num_files // 10)
    top_files_churn = sum(sorted(churn_counts.values(), reverse=True)[:top_n])

    # Print out top 10% of files by churn for debugging
    # print("Top churn files:", sorted(churn_counts.items(), key=lambda x: x[1], reverse=True)[:top_n])

    return {
        "total_churn": total_churn,
        "files_modified": num_files,
        "churn_concentration": top_files_churn / total_churn,
        "top_10_percent_file_count": top_n,
    }


def analyze_churn_concentration_per_player(data: list, use_magnitude: bool = False) -> pd.DataFrame:
    arena_data = {}
    for entry in data:
        arena = entry["tournament"].split(".", 2)[1]
        key = (entry["player"], arena)

        if key not in arena_data:
            arena_data[key] = {}

        for filename, history in entry["file_history"].items():
            if filename not in arena_data[key]:
                arena_data[key][filename] = []
            arena_data[key][filename].extend(history)

    results = []
    for (player, arena), file_history in arena_data.items():
        stats = calculate_churn_concentration(file_history, use_magnitude=use_magnitude)
        results.append({"player": player, "arena": arena, **stats})

    df = pd.DataFrame(results)
    df = df[df["total_churn"] > 0]
    result = df.groupby("player")["churn_concentration"].agg(["mean", "std", "count"]).reset_index()
    # Calculate standard error of the mean (SEM)
    result["sem"] = result["std"] / (result["count"] ** 0.5)
    return result


def plot_organization_metrics(file_reuse_df: pd.DataFrame, root_clutter_df: pd.DataFrame):
    """Scatter plot with consistent styling across visualizations.

    - X: Root Clutter Ratio (lower is better)
    - Y: File Reuse Ratio (higher is better)
    - One point per model, colored consistently and labeled in legend
    """
    # Merge the two dataframes on player
    merged = file_reuse_df.merge(root_clutter_df, on="player", suffixes=("_reuse", "_clutter"))

    # Figure & axes styling to match other viz
    plt.figure(figsize=(6, 6))

    # Plot points per player/model with consistent color & legend label
    seen_labels = set()
    for _, row in merged.iterrows():
        model_key = row["player"]
        color = MODEL_TO_COLOR.get(model_key, "#333333")
        label = MODEL_TO_DISPLAY_NAME.get(model_key, model_key)
        # Avoid duplicate legend entries
        plot_label = label if label not in seen_labels else None
        if plot_label:
            seen_labels.add(label)

        # Plot error bars first (so they appear behind the scatter points)
        plt.errorbar(
            row["mean_clutter"],
            row["mean_reuse"],
            xerr=row["sem_clutter"],
            yerr=row["sem_reuse"],
            fmt="none",
            ecolor=color,
            elinewidth=1.5,
            capsize=3,
            capthick=1.5,
            alpha=0.6,
            zorder=1,
        )

        # Plot scatter point on top
        plt.scatter(
            row["mean_clutter"],
            row["mean_reuse"],
            s=90,
            alpha=0.9,
            color=color,
            edgecolor="white",
            linewidth=0.8,
            marker="o",
            label=plot_label,
            zorder=2,
        )

    # Axes labels and limits
    plt.xlabel("Root Level Clutter", fontproperties=FONT_BOLD, fontsize=18)
    plt.ylabel("File Reuse Ratio", fontproperties=FONT_BOLD, fontsize=18)

    # Axis ranges (ratios 0..1) and nice ticks
    plt.xlim(0, 1)
    plt.ylim(0, 1)
    plt.xticks([0, 0.25, 0.5, 0.75, 1.0])
    plt.yticks([0, 0.25, 0.5, 0.75, 1.0])

    # Grid & quadrant medians
    plt.grid(True, alpha=0.3)
    # plt.axvline(merged["mean_clutter"].median(), color="gray", linestyle="--", alpha=0.5)
    # plt.axhline(merged["mean_reuse"].median(), color="gray", linestyle="--", alpha=0.5)

    # Legend styling
    # FONT_BOLD.set_size(14)
    # plt.legend(loc="lower center", prop=FONT_BOLD, ncol=2)

    plt.tight_layout()
    OUTPUT_FILE = ASSETS_SUBFOLDER / "scatter_codebase_organization.png"
    plt.savefig(OUTPUT_FILE, dpi=300, bbox_inches="tight")
    print(f"Saved scatter plot to {OUTPUT_FILE}")


def calculate_file_reuse_ratio(file_history: dict) -> dict:
    """Calculate what percentage of created files are later modified/referenced in subsequent rounds.

    For each file created in round X, check if it was ever touched (modified/referenced/renamed) in any round > X.
    Returns: (files reused after creation) / (total files created)
    """
    if not file_history:
        return {"total_files_created": 0, "files_reused": 0, "file_reuse_ratio": None}

    created_files = {}  # filename -> creation_round
    reused_files = set()  # filenames that were reused after creation

    for filename, history in file_history.items():
        if not history:
            continue

        # Find creation round (first CREATED operation)
        creation_round = None
        for round_num, op, _, _ in history:
            if op == "created":
                creation_round = round_num
                break

        # If file was never explicitly created (shouldn't happen but be safe)
        if creation_round is None:
            continue

        created_files[filename] = creation_round

        # Check if file was touched in any later round
        for round_num, op, _, _ in history:
            if round_num > creation_round and op in ["modified", "referenced", "renamed"]:
                reused_files.add(filename)
                break  # Only need to find one reuse instance

    if not created_files:
        return {"total_files_created": 0, "files_reused": 0, "file_reuse_ratio": None}

    return {
        "total_files_created": len(created_files),
        "files_reused": len(reused_files),
        "file_reuse_ratio": len(reused_files) / len(created_files),
    }


def analyze_file_reuse_per_player(data: list) -> pd.DataFrame:
    """Calculate file reuse ratio per player across all arenas."""
    arena_data = {}
    for entry in data:
        arena = entry["tournament"].split(".", 2)[1]
        key = (entry["player"], arena)

        if key not in arena_data:
            arena_data[key] = {}

        for filename, history in entry["file_history"].items():
            if filename not in arena_data[key]:
                arena_data[key][filename] = []
            arena_data[key][filename].extend(history)

    results = []
    for (player, arena), file_history in arena_data.items():
        stats = calculate_file_reuse_ratio(file_history)
        results.append({"player": player, "arena": arena, **stats})

    df = pd.DataFrame(results)
    df = df[df["total_files_created"] > 0]
    result = df.groupby("player")["file_reuse_ratio"].agg(["mean", "std", "count"]).reset_index()
    # Calculate standard error of the mean (SEM)
    result["sem"] = result["std"] / (result["count"] ** 0.5)
    return result


def calculate_filename_redundancy(file_history: dict) -> dict:
    """Calculate ratio of files with shared prefixes (potential duplicates)."""

    existing_files = [f for f, h in file_history.items() if not any(op == "deleted" for _, op, _, _ in h)]

    if len(existing_files) < 2:
        return {"total_files": len(existing_files), "redundant_files": 0, "redundancy_ratio": None}

    # Count files by prefix
    prefixes = {}
    for f in existing_files:
        base = f.split("/")[-1]  # Get filename without path
        # Extract prefix (letters and underscores before numbers/extensions)
        match = re.match(r"^([a-zA-Z_]+)", base)
        if match:
            prefix = match.group(1).lower()
            if prefix not in prefixes:
                prefixes[prefix] = []
            prefixes[prefix].append(f)

    # Count redundant files (groups with 2+ files minus 1 for the "original")
    redundant_files = sum(len(files) - 1 for files in prefixes.values() if len(files) > 1)

    return {
        "total_files": len(existing_files),
        "redundant_files": redundant_files,
        "redundancy_ratio": redundant_files / len(existing_files),
    }


def calculate_redundancy_over_rounds(file_history: dict) -> list:
    """Calculate filename redundancy at each round for a single player-tournament.

    Args:
        file_history: dict mapping filenames to [(round, op, added, removed), ...]

    Returns:
        list of dicts with round and redundancy_ratio
    """
    if not file_history:
        return []

    # Get max round
    max_round = max(max(r for r, _, _, _ in h) for h in file_history.values() if h)

    results = []
    for round_num in range(1, max_round + 1):
        # Build file_history snapshot: only include history up to this round
        file_history_snapshot = {}
        for filename, history in file_history.items():
            relevant_history = [(r, op, a, rm) for r, op, a, rm in history if r <= round_num]
            if relevant_history:
                file_history_snapshot[filename] = relevant_history

        # Calculate redundancy using the snapshot
        stats = calculate_filename_redundancy(file_history_snapshot)

        if stats["redundancy_ratio"] is not None:
            results.append(
                {"round": round_num, "redundancy_ratio": stats["redundancy_ratio"], "total_files": stats["total_files"]}
            )

    return results


def plot_filename_redundancy_over_rounds(redundancy_df: pd.DataFrame):
    """Line plot showing filename redundancy over rounds per model.
    sc
        - X: Round number
        - Y: Filename redundancy ratio (mean across tournaments)
        - One line per model, colored consistently
    """
    # Aggregate by player and round (mean across all tournaments)
    agg_redundancy = (
        redundancy_df.groupby(["player", "round"])
        .agg({"redundancy_ratio": "mean", "total_files": "mean"})
        .reset_index()
    )

    # Figure styling to match other viz
    plt.figure(figsize=(3.5, 6))

    # Plot one line per model with consistent color & legend label
    seen_labels = set()
    for player in sorted(agg_redundancy["player"].unique()):
        player_data = agg_redundancy[agg_redundancy["player"] == player]
        color = MODEL_TO_COLOR.get(player, "#333333")
        label = MODEL_TO_DISPLAY_NAME.get(player, player)

        # Avoid duplicate legend entries
        plot_label = label if label not in seen_labels else None
        if plot_label:
            seen_labels.add(label)

        plt.plot(
            player_data["round"],
            player_data["redundancy_ratio"],
            color=color,
            linewidth=2.5,
            label=plot_label,
            alpha=0.9,
        )

    # Axes labels
    plt.xlabel("Round", fontproperties=FONT_BOLD, fontsize=18)
    plt.ylabel("Filename Redundancy Ratio", fontproperties=FONT_BOLD, fontsize=18)

    # Grid & legend
    plt.grid(True, alpha=0.3)
    FONT_BOLD.set_size(14)
    plt.legend(loc="best", prop=FONT_BOLD)

    plt.tight_layout()
    OUTPUT_FILE = ASSETS_SUBFOLDER / "line_chart_filename_redundancy_over_rounds.png"
    plt.savefig(OUTPUT_FILE, dpi=300, bbox_inches="tight")
    print(f"Saved filename redundancy plot to {OUTPUT_FILE}")


def analyze_filename_redundancy_over_rounds(data: list) -> pd.DataFrame:
    """Calculate filename redundancy over rounds for each player-tournament."""
    redundancy_results = []
    for entry in data:
        player = entry["player"]
        tournament = entry["tournament"]
        file_history = entry["file_history"]

        # Calculate redundancy over rounds for this player-tournament
        rounds_redundancy = calculate_redundancy_over_rounds(file_history)
        for round_data in rounds_redundancy:
            redundancy_results.append(
                {
                    "player": player,
                    "tournament": tournament,
                    "round": round_data["round"],
                    "redundancy_ratio": round_data["redundancy_ratio"],
                    "total_files": round_data["total_files"],
                }
            )

    return pd.DataFrame(redundancy_results)


def main(refresh_cache: bool = False):
    build_data_structure(refresh_cache)

    data = []
    with open(DATA_CACHE) as f:
        data = [json.loads(line) for line in f]
    print(f"Found {len(data)} player-tournament entries in cache.")

    # Analysis 1: Per player-tournament
    print("\n=== Active File Ratio Per Player-Arena ===")
    per_tournament_df = analyze_per_player_arena(data, N=5)
    print(per_tournament_df)
    per_tournament_df.to_csv(ASSETS_SUBFOLDER / "active_file_ratio_per_tournament.csv", index=False)

    # Analysis 2: Per player (aggregated)
    print("\n=== Active File Ratio Per Player ===")
    per_player_df = analyze_per_player(data, N=5)
    print(per_player_df)
    per_player_df.to_csv(ASSETS_SUBFOLDER / "active_file_ratio_per_player.csv", index=False)

    # Analysis 3: Root level file clutter per player
    print("\n=== Root Level File Clutter Per Player ===")
    root_clutter_df = analyze_root_clutter_per_player(data)
    print(root_clutter_df)
    root_clutter_df.to_csv(ASSETS_SUBFOLDER / "root_clutter_ratio_per_player.csv", index=False)

    # Analysis 4: Churn concentration per player
    print("\n=== Churn Concentration Per Player ===")
    churn_concentration_df = analyze_churn_concentration_per_player(data, use_magnitude=True)
    print(churn_concentration_df)
    churn_concentration_df.to_csv(ASSETS_SUBFOLDER / "churn_concentration_per_player.csv", index=False)

    # Analysis 5: File reuse ratio per player
    print("\n=== File Reuse Ratio Per Player ===")
    file_reuse_df = analyze_file_reuse_per_player(data)
    print(file_reuse_df)
    file_reuse_df.to_csv(ASSETS_SUBFOLDER / "file_reuse_ratio_per_player.csv", index=False)

    # Visualization: Organization metrics
    print("\n=== Plotting Organization Metrics ===")
    plot_organization_metrics(file_reuse_df, root_clutter_df)

    # Analysis 6: Filename redundancy over rounds
    print("\n=== Filename Redundancy Over Rounds Per Player-Tournament ===")
    redundancy_df = analyze_filename_redundancy_over_rounds(data)
    print(redundancy_df)
    redundancy_df.to_csv(ASSETS_SUBFOLDER / "filename_redundancy_per_player.csv", index=False)

    # Visualization: Filename redundancy over rounds
    print("\n=== Plotting Filename Redundancy Over Rounds ===")
    plot_filename_redundancy_over_rounds(redundancy_df)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process dead code analysis")
    parser.add_argument("-r", "--refresh-cache", action="store_true", help="Refresh the cache")
    args = parser.parse_args()
    main(**vars(args))
