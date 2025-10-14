#!/usr/bin/env python3
import argparse
import json
from dataclasses import dataclass
from pathlib import Path

from matplotlib import pyplot as plt
from tqdm import tqdm

from codeclash.analysis.viz.utils import ASSETS_DIR, FONT_BOLD, MODEL_TO_COLOR, MODEL_TO_DISPLAY_NAME
from codeclash.constants import LOCAL_LOG_DIR, RESULT_TIE


@dataclass
class ModelRoundWinProfile:
    model: str
    arena: str
    wins: int
    total_games: int
    round_idx: int

    @property
    def win_rate(self) -> float:
        return self.wins / self.total_games if self.total_games > 0 else 0.0


def main(log_dir: Path):
    print(f"Calculating win rates by round from logs in {log_dir} ...")

    player_round_profiles = {}

    for game_log_folder in tqdm([x.parent for x in log_dir.rglob("metadata.json")]):
        arena = game_log_folder.name.split(".")[1]
        metadata = json.load(open(game_log_folder / "metadata.json"))

        try:
            p2m = {x["name"]: x["config"]["model"]["model_name"].strip("@") for x in metadata["config"]["players"]}
        except KeyError:
            print(f"Skipping {game_log_folder} (malformed metadata.json)")
            continue

        if len(p2m) != 2:
            # Only process if there are exactly 2 players:
            continue

        for idx, stats in metadata["round_stats"].items():
            if idx == "0":
                # Skip initial round
                continue

            # Initialize profiles for each model in this round
            for model in p2m.values():
                key = f"{arena}.{model}.{idx}"
                if key not in player_round_profiles:
                    player_round_profiles[key] = ModelRoundWinProfile(
                        model=model, arena=arena, wins=0, total_games=0, round_idx=int(idx)
                    )

            # Count the game for each participating model
            for model in p2m.values():
                key = f"{arena}.{model}.{idx}"
                player_round_profiles[key].total_games += 1

            # Check if there's a winner for this round
            winner = stats.get("winner")
            if winner and winner != RESULT_TIE and winner in p2m:
                winning_model = p2m[winner]
                key = f"{arena}.{winning_model}.{idx}"
                if key in player_round_profiles:
                    player_round_profiles[key].wins += 1

    # Organize data by model and round for plotting
    lines = {
        pid: [[] for _ in range(15)]
        for pid in {x.rsplit(".", 1)[0].split(".", 1)[-1] for x in player_round_profiles.keys()}
    }

    for pid, profile in player_round_profiles.items():
        k = pid.rsplit(".", 1)[0].split(".", 1)[-1]
        if 1 <= profile.round_idx <= 15:
            lines[k][profile.round_idx - 1].append(profile)

    print("=" * 50)
    print("Player win rate progression per round:")

    def aggregate_win_rates_across_games(profiles):
        """Aggregate win rates across multiple games using micro-averaging"""
        total_wins = sum([p.wins for p in profiles])
        total_games = sum([p.total_games for p in profiles])
        return total_wins / total_games if total_games > 0 else 0.0

    # Calculate aggregated win rates for each player and round
    for pid, win_profiles in lines.items():
        lines[pid] = [aggregate_win_rates_across_games(r) for r in win_profiles]
        print(f" - {pid}: " + ", ".join([f"{wr:.2%}" for wr in lines[pid]]))

    # Create line chart of win rate progression per player
    plt.figure(figsize=(6, 6))
    for pid, win_rates in lines.items():
        plt.plot(
            range(1, 16),
            win_rates,
            marker="o",
            label=MODEL_TO_DISPLAY_NAME[pid],
            linewidth=1,
            markersize=6,
            color=MODEL_TO_COLOR[pid],
        )

    # plt.title("Win Rate Progression per Round", fontsize=16, fontweight="bold")
    plt.xlabel("Round", fontsize=20, fontproperties=FONT_BOLD)
    plt.ylabel("Win Rate", fontsize=20, fontproperties=FONT_BOLD)
    plt.xticks(range(1, 16), fontproperties=FONT_BOLD, fontsize=14)
    plt.yticks(
        [i / 10 for i in range(0, 11)],
        [f"{i * 10}%" for i in range(0, 11)],
        fontproperties=FONT_BOLD,
        fontsize=14,
    )
    plt.ylim(0.1, 1)
    FONT_BOLD.set_size(14)
    plt.legend(
        bbox_to_anchor=(1, 1),
        loc="upper right",
        ncol=2,
        prop=FONT_BOLD,
        handletextpad=0.3,
        borderpad=0.3,
        handlelength=0.5,
    )
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(ASSETS_DIR / "line_chart_per_round_win_rate.png", dpi=300, bbox_inches="tight")
    print("Win rate progression chart saved to line_chart_per_round_win_rate.png")

    # Print summary statistics
    print("\n" + "=" * 50)
    print("Summary statistics:")
    for pid, win_rates in lines.items():
        avg_win_rate = (
            sum(win_rates) / len([wr for wr in win_rates if wr > 0]) if any(wr > 0 for wr in win_rates) else 0
        )
        max_win_rate = max(win_rates) if win_rates else 0
        min_win_rate = min([wr for wr in win_rates if wr > 0]) if any(wr > 0 for wr in win_rates) else 0
        print(f" - {pid}: Avg: {avg_win_rate:.2%}, Max: {max_win_rate:.2%}, Min: {min_win_rate:.2%}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Calculate win rates per round")
    parser.add_argument("-d", "--log_dir", type=Path, help="Path to game logs (Default: logs/)", default=LOCAL_LOG_DIR)
    args = parser.parse_args()
    main(args.log_dir)
