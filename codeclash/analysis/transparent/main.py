import json
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from codeclash.analysis.viz.utils import ASSETS_DIR, FONT_BOLD, MODEL_TO_COLOR, MODEL_TO_DISPLAY_NAME
from codeclash.constants import LOCAL_LOG_DIR


def compute_win_rates(folder_list):
    wins = defaultdict(int)
    total = defaultdict(int)

    for folder in folder_list:
        metadata = json.load(open(folder / "metadata.json"))

        # Count wins per round
        for round_key, round_data in metadata["round_stats"].items():
            if round_key == "overall":
                continue
            winner = round_data.get("winner")
            for player in round_data.get("scores", {}).keys():
                total[player] += 1
                if player == winner:
                    wins[player] += 1

    return {player: wins[player] / total[player] if total[player] > 0 else 0 for player in total.keys()}


def analyze_opponent_code_access(folder_list):
    """Check trajectory logs for commands accessing /opponent_codebases/"""
    access_counts = defaultdict(lambda: {"accessed": 0, "total_rounds": 0})

    for folder in folder_list:
        players_dir = folder / "players"
        if not players_dir.exists():
            continue

        for player_dir in players_dir.iterdir():
            if not player_dir.is_dir():
                continue
            player_name = player_dir.name

            # Check all trajectory files
            for traj_file in player_dir.glob("*.traj.json"):
                traj = json.load(open(traj_file))

                accessed_opponent = False
                # Look through messages for commands accessing opponent code
                for msg in traj.get("messages", []):
                    if msg.get("role") == "assistant":
                        content = msg.get("content", "")
                        if "/opponent_codebases/" in content or "opponent_codebases" in content:
                            accessed_opponent = True
                            break

                access_counts[player_name]["total_rounds"] += 1
                if accessed_opponent:
                    access_counts[player_name]["accessed"] += 1

    # Compute rates
    rates = {}
    for player, counts in access_counts.items():
        rate = counts["accessed"] / counts["total_rounds"] if counts["total_rounds"] > 0 else 0
        rates[player] = {"rate": rate, "accessed": counts["accessed"], "total": counts["total_rounds"]}

    return rates


def compute_exploitation_advantage():
    """Calculate win rate change from normal to transparent for each model"""
    advantages = {}

    for model in transparent_wr.keys():
        normal_rate = normal_wr.get(model, 0)
        transparent_rate = transparent_wr.get(model, 0)

        # Absolute and relative change
        absolute_change = transparent_rate - normal_rate
        relative_change = (transparent_rate - normal_rate) / normal_rate if normal_rate > 0 else 0

        advantages[model] = {
            "normal": normal_rate,
            "transparent": transparent_rate,
            "absolute_change": absolute_change,
            "relative_change": relative_change,
        }

    return advantages


def analyze_temporal_opponent_access(folder_list):
    """Track opponent code access by round number (early vs late tournament)"""
    access_by_round = defaultdict(lambda: {"accessed": 0, "total": 0})
    access_by_model_round = defaultdict(lambda: defaultdict(lambda: {"accessed": 0, "total": 0}))

    for folder in folder_list:
        players_dir = folder / "players"
        if not players_dir.exists():
            continue

        for player_dir in players_dir.iterdir():
            if not player_dir.is_dir():
                continue
            player_name = player_dir.name

            for traj_file in player_dir.glob("*_r*.traj.json"):
                # Extract round number from filename
                round_num = int(traj_file.stem.split("_r")[-1].split(".")[0])

                traj = json.load(open(traj_file))
                accessed_opponent = False

                for msg in traj.get("messages", []):
                    if msg.get("role") == "assistant":
                        content = msg.get("content", "")
                        if "/opponent_codebases/" in content or "opponent_codebases" in content:
                            accessed_opponent = True
                            break

                access_by_round[round_num]["total"] += 1
                access_by_model_round[player_name][round_num]["total"] += 1

                if accessed_opponent:
                    access_by_round[round_num]["accessed"] += 1
                    access_by_model_round[player_name][round_num]["accessed"] += 1

    return access_by_round, access_by_model_round


if __name__ == "__main__":
    # `normal` is all 1v1 Halite games from main results
    normal = sorted(
        [
            x.parent
            for x in Path(LOCAL_LOG_DIR).rglob("metadata.json")
            if "Halite" in x.parent.name
            and ".p2." in x.parent.name
            and "transparent" not in x.parent.name
            and (
                ("claude-sonnet-4-5" in x.parent.name and "gemini-2.5-pro" in x.parent.name)
                or ("claude-sonnet-4-5" in x.parent.name and ".gpt-5." in x.parent.name)
                or ("gemini-2.5-pro" in x.parent.name and ".gpt-5." in x.parent.name)
            )
        ]
    )
    folders = sorted(
        [x.parent for x in Path(LOCAL_LOG_DIR).rglob("metadata.json") if x.parent.name.endswith(".transparent")]
    )
    len(folders), len(normal)

    # 1. Win Rates in Transparent vs. Normal Settings
    transparent_wr = compute_win_rates(folders)
    normal_wr = compute_win_rates(normal)

    print("TRANSPARENT Win Rates:")
    for model, wr in sorted(transparent_wr.items(), key=lambda x: x[1], reverse=True):
        print(f"  {model}: {wr:.3f}")

    print("\nNORMAL Win Rates:")
    for model, wr in sorted(normal_wr.items(), key=lambda x: x[1], reverse=True):
        print(f"  {model}: {wr:.3f}")

    # 2. Opponent Code Access Analysis
    opponent_analysis = analyze_opponent_code_access(folders)

    print("Opponent Code Access Rates (Transparent Setting):")
    for model, stats in sorted(opponent_analysis.items(), key=lambda x: x[1]["rate"], reverse=True):
        print(f"  {model}: {stats['rate']:.1%} ({stats['accessed']}/{stats['total']} rounds)")

    # 3. Exploitation Advantage Calculation
    exploitation = compute_exploitation_advantage()

    print("Exploitation Advantage (Win Rate Changes):")
    for model, stats in sorted(exploitation.items(), key=lambda x: x[1]["absolute_change"], reverse=True):
        print(f"  {model}:")
        print(f"    Normal: {stats['normal']:.3f} → Transparent: {stats['transparent']:.3f}")
        print(f"    Change: {stats['absolute_change']:+.3f} ({stats['relative_change']:+.1%})")

    # 4. Temporal Evolution: Do Models look at opponent code more over time
    overall_temporal, model_temporal = analyze_temporal_opponent_access(folders)

    # Show early (rounds 1-5), mid (rounds 6-10), vs late (rounds 11-15) for each model
    print("\nOpponent Code Access: Early (R1-5) vs Mid (R6-10) vs Late (R11-15) Rounds\n")

    temporal_data = {}
    for model in sorted(model_temporal.keys()):
        early_acc = sum(model_temporal[model][r]["accessed"] for r in range(1, 6))
        early_tot = sum(model_temporal[model][r]["total"] for r in range(1, 6))
        mid_acc = sum(model_temporal[model][r]["accessed"] for r in range(6, 11))
        mid_tot = sum(model_temporal[model][r]["total"] for r in range(6, 11))
        late_acc = sum(model_temporal[model][r]["accessed"] for r in range(11, 16))
        late_tot = sum(model_temporal[model][r]["total"] for r in range(11, 16))

        early_rate = early_acc / early_tot if early_tot > 0 else 0
        mid_rate = mid_acc / mid_tot if mid_tot > 0 else 0
        late_rate = late_acc / late_tot if late_tot > 0 else 0

        temporal_data[model] = {"Early (R1-5)": early_rate, "Mid (R6-10)": mid_rate, "Late (R11-15)": late_rate}

        print(f"  {model}:")
        print(f"    Early: {early_rate:.1%} ({early_acc}/{early_tot})")
        print(f"    Mid:   {mid_rate:.1%} ({mid_acc}/{mid_tot})")
        print(f"    Late:  {late_rate:.1%} ({late_acc}/{late_tot})")

    # Create bar chart visualization
    fig, ax = plt.subplots(figsize=(6, 6))

    periods = ["Early\n(R1-5)", "Mid\n(R6-10)", "Late\n(R11-15)"]
    x = np.arange(len(periods))
    width = 0.2

    models = sorted(temporal_data.keys())

    for i, model in enumerate(models):
        display_name = MODEL_TO_DISPLAY_NAME.get(model, model)
        color = MODEL_TO_COLOR.get(model, None)
        rates = [temporal_data[model][period] * 100 for period in ["Early (R1-5)", "Mid (R6-10)", "Late (R11-15)"]]
        ax.bar(x + i * width, rates, width, label=display_name, color=color)

    # ax.set_xlabel('Rounds', fontsize=18, fontproperties=FONT_BOLD)
    ax.set_ylabel("Opponent Code Access Rate (%)", fontsize=18, fontproperties=FONT_BOLD)
    ax.set_xticks(x + width)
    ax.set_xticklabels(periods, fontproperties=FONT_BOLD, fontsize=18)
    ax.tick_params(axis="y", labelsize=18)
    for label in ax.get_yticklabels():
        label.set_fontproperties(FONT_BOLD)
    FONT_BOLD.set_size(16)
    ax.legend(prop=FONT_BOLD, fontsize=14)
    ax.grid(axis="y", alpha=0.3)

    plt.tight_layout()
    plt.savefig(ASSETS_DIR / "bar_chart_temporal_opponent_access.png", dpi=300, bbox_inches="tight")
    print(f"\nSaved visualization to {ASSETS_DIR / 'bar_chart_temporal_opponent_access.png'}")
