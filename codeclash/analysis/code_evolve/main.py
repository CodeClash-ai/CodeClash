"""Code evolution and consistency analysis across tournament games."""

import argparse
import difflib
import json
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np
import yaml
from cdifflib import CSequenceMatcher
from tqdm.auto import tqdm
from unidiff import PatchSet

from codeclash.analysis.viz.utils import FONT_BOLD, MARKERS, MODEL_TO_COLOR, MODEL_TO_DISPLAY_NAME
from codeclash.constants import LOCAL_LOG_DIR
from codeclash.games import ARENAS

MODELS_PATH = Path("configs/models.yaml")
TARGET_ROUNDS = [1, 15, 5, 10]


def get_model_arena_logs(model: str | list[str], arena: str | list[str]) -> list[Path]:
    """Get all log folders matching the specified model(s) and arena(s)."""
    arena = arena if isinstance(arena, list) else [arena]
    model = model if isinstance(model, list) else [model]
    return [
        x.parent
        for x in Path(LOCAL_LOG_DIR).rglob("metadata.json")
        if x.parent.name.split(".")[1] in arena and all(f".{m}." in x.parent.name for m in model)
    ]


def get_submission_diff_at_round(log_folder: Path, player_name: str, round_num: int) -> PatchSet:
    """Extract submission-relevant code diff for a player at a specific round."""
    arena = [a for a in ARENAS if a.name == log_folder.name.split(".")[1]][0]

    changes_file = log_folder / "players" / player_name / f"changes_r{round_num}.json"
    if not changes_file.exists():
        raise FileNotFoundError(f"Changes file not found: {changes_file}")

    with open(changes_file) as f:
        changes_data = json.load(f)

    # Filter to submission-relevant files only
    patch = PatchSet(changes_data["full_diff"])
    relevant = []
    for file in patch:
        if file.path == arena.submission or file.path.startswith(arena.submission):
            relevant.append(file)

    return PatchSet("\n".join(str(f) for f in relevant))


def get_submission_diffs_at_round(log_folders: list[Path], player_name: str, round_num: int) -> dict[Path, PatchSet]:
    """Extract submission diffs for a player at a specific round across multiple tournaments."""
    diffs = {}
    for folder in log_folders:
        try:
            diffs[folder] = get_submission_diff_at_round(folder, player_name, round_num)
        except FileNotFoundError as e:
            print(e)
            continue
    return diffs


def find_max_round_for_player(log_folder: Path, player_name: str) -> int:
    """Find the highest round number that exists for a player."""
    player_dir = log_folder / "players" / player_name
    changes_files = list(player_dir.glob("changes_r*.json"))
    rounds = [int(f.stem.split("_r")[1]) for f in changes_files]
    return max(rounds) if rounds else 0


def _compute_code_sim_difflib(diff1: PatchSet, diff2: PatchSet) -> float:
    """Compute similarity score between two diffs using edit distance (0.0 = different, 1.0 = identical)."""
    diff1_str = "\n".join(str(f) for f in diff1)
    diff2_str = "\n".join(str(f) for f in diff2)
    difflib.SequenceMatcher = CSequenceMatcher
    seq_matcher = difflib.SequenceMatcher(None, diff1_str, diff2_str, autojunk=False)
    return seq_matcher.ratio()


def compute_code_sim_jaccard(diff1: PatchSet, diff2: PatchSet) -> float:
    """Jaccard similarity on line-level tokens."""

    def get_lines(patch):
        return {str(f).splitlines() for f in patch}

    lines1 = get_lines(diff1)
    lines2 = get_lines(diff2)

    if not lines1 and not lines2:
        return 1.0
    if not lines1 or not lines2:
        return 0.0

    intersection = len(lines1 & lines2)
    union = len(lines1 | lines2)
    return intersection / union


def compute_code_similarity(diff1: PatchSet, diff2: PatchSet, similarity: str = "difflib") -> float:
    return {
        "difflib": _compute_code_sim_difflib,
        "jaccard": compute_code_sim_jaccard,
    }[similarity](diff1, diff2)


def _compute_similarity_row(args):
    """Helper for parallel similarity computation."""
    i, patch_i, patches, similarity = args
    row = np.zeros(len(patches))
    for j, patch_j in enumerate(patches):
        if i != j:
            row[j] = compute_code_similarity(patch_i, patch_j, similarity)
        else:
            row[j] = 1.0
    return i, row


def compute_round_consistency(
    model: str, opponent: str, arena: str, round_num: int, n_workers: int = 4, similarity: str = "difflib"
) -> tuple[np.ndarray, np.ndarray]:
    """
    Compute pairwise similarity between a model's solutions at a specific round across multiple games.
    Use this for both questions 1a (early rounds) and 1b (final round).
    """
    folders = get_model_arena_logs([model, opponent], arena)
    patches = get_submission_diffs_at_round(folders, model, round_num)
    print(f"Found {len(patches)} patches for {model} vs {opponent} in {arena} at round {round_num}")

    # Compute similarity matrix in parallel
    patch_list = list(patches.values())
    n = len(patch_list)
    similarity_matrix = np.zeros((n, n))

    with ProcessPoolExecutor(max_workers=n_workers) as executor:
        tasks = [(i, patch_list[i], patch_list, similarity) for i in range(n)]
        futures = {executor.submit(_compute_similarity_row, task): task for task in tasks}

        for future in tqdm(as_completed(futures), total=n, desc="Computing similarities"):
            i, row = future.result()
            similarity_matrix[i, :] = row

    # Extract upper triangle for statistics
    upper_triangle = similarity_matrix[np.triu_indices(n, k=1)]

    return similarity_matrix, upper_triangle


def tag_to_str(tag: dict) -> str:
    return f"{tag['model_a']}__vs__{tag['model_b']}__in__{tag['arena']}__r{tag['round']}"


def collect_data(
    data_cache: Path = Path("assets/code_evolve_cache_BattleSnake_difflib.jsonl"),
    arena: str = "BattleSnake",
    similarity: str = "difflib",
):
    """Run code evolution analyses."""
    mode, to_skip = "w", []
    if data_cache.exists():
        mode = "a"
        with open(data_cache) as f:
            for line in f:
                entry = json.loads(line)
                to_skip.append(
                    tag_to_str(
                        {
                            "model_a": entry["model_a"],
                            "model_b": entry["model_b"],
                            "arena": entry["arena"],
                            "round": entry["round"],
                        }
                    )
                )
        print(f"Found cache file, skipping {len(to_skip)} entries.")

    with open(MODELS_PATH) as f:
        models = [x["model_name"].rsplit("/")[-1] for x in yaml.safe_load(f)]

    with open(data_cache, mode) as f:
        for round in TARGET_ROUNDS:
            for i in range(0, len(models)):
                for j in range(0, len(models)):
                    if i == j:
                        continue
                    if (
                        tag_to_str(
                            {
                                "model_a": models[i],
                                "model_b": models[j],
                                "arena": arena,
                                "round": round,
                            }
                        )
                        in to_skip
                    ):
                        continue
                    try:
                        sim_matrix, _ = compute_round_consistency(
                            models[i], models[j], arena, round, similarity=similarity
                        )
                    except Exception as e:
                        print(
                            f"Error computing consistency for {models[i]} vs {models[j]} in {arena} at round {round}: {e}"
                        )
                        continue
                    f.write(
                        json.dumps(
                            {
                                "model_a": models[i],
                                "model_b": models[j],
                                "arena": arena,
                                "round": round,
                                "similarity_matrix": sim_matrix.tolist(),
                            }
                        )
                        + "\n"
                    )
                    f.flush()


# =============================================
# MARK: Visualizations / Statistics below
# =============================================c


def load_cached_results(data_cache: Path) -> list[dict]:
    """Load all cached results from the data file."""
    results = []
    with open(data_cache) as f:
        for line in f:
            results.append(json.loads(line))
    return results


def compute_model_consistency_over_rounds(results: list[dict]) -> dict:
    """
    Aggregate consistency data by model and round.
    For each model at each round, compute mean similarity across all matchups.
    """
    from collections import defaultdict

    # Group by model and round
    model_round_similarities = defaultdict(lambda: defaultdict(list))

    for entry in results:
        sim_matrix = np.array(entry["similarity_matrix"])
        n = sim_matrix.shape[0]
        upper_tri = sim_matrix[np.triu_indices(n, k=1)]
        mean_sim = upper_tri.mean()

        # Similarity matrix reflects model_a's consistency (model_b is just the opponent filter)
        model_round_similarities[entry["model_a"]][entry["round"]].append(mean_sim)

    # Average across all matchups for each model/round
    model_consistency = {}
    for model, round_data in model_round_similarities.items():
        model_consistency[model] = {round_num: np.mean(sims) for round_num, sims in round_data.items()}

    return model_consistency


def compute_opponent_effect_matrix(results: list[dict], target_round: int) -> tuple[list[str], dict]:
    """
    Build matrix showing how each model's consistency varies by opponent.
    Returns (model_list, opponent_matrix) where opponent_matrix[model][opponent] = mean_similarity.
    """
    from collections import defaultdict

    # Group by model and opponent at target round
    model_opponent_similarities = defaultdict(lambda: defaultdict(list))

    for entry in results:
        if entry["round"] != target_round:
            continue

        sim_matrix = np.array(entry["similarity_matrix"])
        n = sim_matrix.shape[0]
        upper_tri = sim_matrix[np.triu_indices(n, k=1)]
        mean_sim = upper_tri.mean()

        # entry has model_a playing against model_b
        model_a = entry["model_a"]
        model_b = entry["model_b"]
        model_opponent_similarities[model_a][model_b].append(mean_sim)

    # Average across repeated games
    opponent_matrix = {}
    for model, opponent_data in model_opponent_similarities.items():
        opponent_matrix[model] = {opponent: np.mean(sims) for opponent, sims in opponent_data.items()}

    return sorted(opponent_matrix.keys()), opponent_matrix


def plot_opponent_effect_heatmap(data_cache: str, target_round: int, output_path: str = None):
    """
    Plot heatmap showing how model consistency varies by opponent.
    Answers questions 2a (round 1) and 2b (round 15).
    """
    if output_path is None:
        output_path = f"assets/heatmap_code_evolution_per_opponent_r{target_round}.png"

    results = load_cached_results(data_cache)
    models, opponent_matrix = compute_opponent_effect_matrix(results, target_round)

    # Get all unique opponents
    all_opponents = set()
    for model_data in opponent_matrix.values():
        all_opponents.update(model_data.keys())
    opponents = sorted(all_opponents)

    # Build matrix: rows=models, cols=opponents
    n_models = len(models)
    n_opponents = len(opponents)
    matrix = np.full((n_models, n_opponents), np.nan)
    for i, model in enumerate(models):
        for j, opponent in enumerate(opponents):
            if opponent in opponent_matrix[model]:
                matrix[i, j] = opponent_matrix[model][opponent]

    # Calculate row averages (model consistency)
    row_means = np.nanmean(matrix, axis=1)
    model_stats = [(models[i], row_means[i]) for i in range(n_models)]
    model_stats_sorted = sorted(model_stats, key=lambda x: x[1], reverse=True)

    # Calculate column averages (opponent effect)
    col_means = np.nanmean(matrix, axis=0)
    opponent_stats = [(opponents[i], col_means[i]) for i in range(n_opponents)]
    opponent_stats_sorted = sorted(opponent_stats, key=lambda x: x[1], reverse=True)

    print(f"\n{'=' * 60}")
    print(f"Model Consistency Statistics (Round {target_round}):")
    print(f"{'=' * 60}")
    print(f"{'Model':<25} {'Avg Similarity'}")
    print(f"{'-' * 60}")
    for model, avg_sim in model_stats_sorted:
        display = MODEL_TO_DISPLAY_NAME.get(model, model)
        print(f"{display:<25} {avg_sim:.3f}")
    print(f"{'=' * 60}")

    print(f"\n{'=' * 60}")
    print(f"Opponent Effect Statistics (Round {target_round}):")
    print(f"{'=' * 60}")
    print(f"{'Opponent':<25} {'Avg Similarity'}")
    print(f"{'-' * 60}")
    for opp, avg_sim in opponent_stats_sorted:
        display = MODEL_TO_DISPLAY_NAME.get(opp, opp)
        print(f"{display:<25} {avg_sim:.3f}")
    print(f"{'=' * 60}\n")

    # Create heatmap with blue-white-red colormap like win_rates
    FONT_BOLD.set_size(14)
    _, ax = plt.subplots(figsize=(6, 6))
    cmap = mcolors.LinearSegmentedColormap.from_list("br", ["#3498db", "#ffffff", "#e74c3c"])
    masked = np.ma.masked_where(np.isnan(matrix), matrix)
    ax.imshow(masked, cmap=cmap, vmin=0, vmax=1, aspect="auto")

    # Add text values in each cell
    for i in range(n_models):
        for j in range(n_opponents):
            if not np.isnan(matrix[i, j]):
                # Choose text color based on background intensity
                color = "white" if abs(matrix[i, j] - 0.5) > 0.25 else "black"
                ax.text(
                    j,
                    i,
                    f"{matrix[i, j]:.2f}",
                    ha="center",
                    va="center",
                    color=color,
                    fontweight="bold",
                    fontproperties=FONT_BOLD,
                )

    # Set ticks and labels
    clean_model_names = [MODEL_TO_DISPLAY_NAME.get(m, m) for m in models]
    clean_opponent_names = [MODEL_TO_DISPLAY_NAME.get(o, o) for o in opponents]

    ax.set_xticks(range(n_opponents))
    ax.set_yticks(range(n_models))
    ax.set_xticklabels(clean_opponent_names, rotation=45, ha="right", fontproperties=FONT_BOLD)
    ax.set_yticklabels(clean_model_names, fontproperties=FONT_BOLD)

    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    print(f"Saved heatmap to {output_path}")


def plot_consistency_over_rounds(data_cache: str, output_path: str = "assets/line_chart_code_evolution.png"):
    """
    Plot line graph: x-axis = round, y-axis = code similarity, one line per model.
    Answers questions 1a (early round consistency) and 1b (evolution over time).
    """
    results = load_cached_results(data_cache)
    model_consistency = compute_model_consistency_over_rounds(results)

    plt.figure(figsize=(6, 6))

    # Plot one line per model
    idx = 0
    for model, round_data in sorted(model_consistency.items()):
        rounds = sorted(round_data.keys())
        similarities = [round_data[r] for r in rounds]
        display = MODEL_TO_DISPLAY_NAME.get(model, model)
        color = MODEL_TO_COLOR.get(model, None)
        plt.plot(
            rounds,
            similarities,
            marker=MARKERS[idx % len(MARKERS)],
            label=display,
            linewidth=1.5,
            markersize=6,
            color=color,
        )
        idx += 1

    plt.xlabel("Round", fontsize=18, fontproperties=FONT_BOLD)
    plt.ylabel("Mean Code Similarity", fontsize=18, fontproperties=FONT_BOLD)
    plt.xticks(TARGET_ROUNDS, fontproperties=FONT_BOLD, fontsize=16)
    plt.yticks(fontproperties=FONT_BOLD, fontsize=16)
    FONT_BOLD.set_size(16)
    plt.legend(bbox_to_anchor=(1, 1), loc="upper right", prop=FONT_BOLD)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    print(f"Saved plot to {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Code Evolution and Consistency Analysis")
    parser.add_argument("-a", "--arena", type=str, default="BattleSnake", help="Arena name to analyze")
    parser.add_argument(
        "-s", "--similarity", type=str, default="difflib", help="Similarity function to use (difflib or jaccard)"
    )
    args = parser.parse_args()

    data_cache = Path(f"assets/code_evolve_cache_{args.arena}_{args.similarity}.jsonl")
    # Run data collection
    collect_data(
        data_cache=data_cache,
        arena=args.arena,
        similarity=args.similarity,
    )

    # Questions 1a/1b: Consistency over rounds
    plot_consistency_over_rounds(data_cache)  # Questions 1a and 1b

    # Questions 2a/2b: Opponent effect
    plot_opponent_effect_heatmap(data_cache, target_round=1)  # Question 2a
    plot_opponent_effect_heatmap(data_cache, target_round=15)  # Question 2b
