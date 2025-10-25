import json
from collections import defaultdict
from pathlib import Path

import trueskill as ts
from tqdm.auto import tqdm

from codeclash.analysis.viz.utils import MODEL_TO_DISPLAY_NAME
from codeclash.constants import LOCAL_LOG_DIR

# TrueSkill environment setup
env = ts.TrueSkill(
    mu=25.0,
    sigma=25.0 / 3.0,  # ~8.33
    beta=25.0 / 6.0,  # ~4.17 (performance variance)
    tau=0.7,  # skill drift per round (↑ for faster adaptation)
    draw_probability=0.0,
)
ts.setup(env)
ratings = defaultdict(env.Rating)

# Find all game log folders with 3+ players
game_log_folders = [x.parent for x in Path(LOCAL_LOG_DIR).rglob("metadata.json")]
three_plus_players = []
for game_log_folder in tqdm(game_log_folders):
    arena = game_log_folder.name.split(".")[1]
    num_players = int(game_log_folder.name.split(".")[4].strip("p"))
    if num_players >= 3:
        three_plus_players.append(game_log_folder)

print(f"Found {len(three_plus_players)} tournaments with 3+ players.")


def scores_to_ranks(scores_dict):
    """Higher score => better rank (0 is best). Ties share the same rank."""
    # Sort by (-score, name) for deterministic ordering
    ordered = sorted(scores_dict.items(), key=lambda kv: (-kv[1], kv[0]))
    ranks = {}
    prev_score, prev_rank = None, None
    for idx, (name, score) in enumerate(ordered):
        if score == prev_score:
            ranks[name] = prev_rank
        else:
            ranks[name] = idx
            prev_rank = idx
            prev_score = score
    return ordered, ranks  # ordered is list[(name, score)] in finishing order


def update_ratings_for_round(scores_dict):
    ordered, ranks = scores_to_ranks(scores_dict)

    # Convert to the Rating objects, preserving team order
    team_ratings = [[ratings[name]] for name, _ in ordered]

    # ranks vector matches the order of `teams`
    ranks_vec = [ranks[name] for name, _ in ordered]

    # Update using TrueSkill (one multi-player game)
    new_team_ratings = ts.rate(team_ratings, ranks=ranks_vec)

    # Write back
    for (name, _), new_rating in zip(ordered, new_team_ratings):
        ratings[name] = new_rating[0]


def conservative_score(r):
    # Leaderboard-safe score (lower-bound skill)
    return r.mu - 3 * r.sigma


for game_log_folder in tqdm(three_plus_players):
    with open(game_log_folder / "metadata.json") as f:
        metadata = json.load(f)
    p2m = {
        x["name"]: x["config"]["model"]["model_name"].strip("@").split("/")[-1] for x in metadata["config"]["players"]
    }
    for round_num in range(len(metadata["round_stats"])):
        if round_num == 0:
            continue
        scores = metadata["round_stats"][str(round_num)]["scores"]
        update_ratings_for_round(scores)

leaderboard = sorted(ratings.items(), key=lambda kv: conservative_score(kv[1]), reverse=True)

for name, r in leaderboard:
    print(f"{name:30s} mu={r.mu:6.2f}  sigma={r.sigma:5.2f}  conservative={conservative_score(r):6.2f}")

# Print out a latex style table
# print("\nLatex Table:")
# print("\\begin{tabular}{lccc}")
# print("\\textbf{Model} & $\\mu$ & $\\sigma$ & \\textbf{Conservative} \\\\ \\hline")
# for name, r in leaderboard:
#     display_name = MODEL_TO_DISPLAY_NAME.get(name, name)
#     print(f"{display_name:30s} & {r.mu:6.2f} & {r.sigma:5.2f} & {conservative_score(r):6.2f} \\\\")
# print("\\end{tabular}")

print("\nLatex Table:")
print("\\begin{tabular}{l|c}")
print("\\textbf{Model} & $\\mu$ \\\\ \\midrule")
for name, r in leaderboard:
    display_name = MODEL_TO_DISPLAY_NAME.get(name, name)
    print(f"{display_name:30s} & {r.mu:6.2f} $\\pm$ {r.sigma:5.2f} \\\\")
print("\\end{tabular}")
