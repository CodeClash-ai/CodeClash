#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from codeclash.analysis.viz.utils import FONT_BOLD, FONT_REG


TIER_ORDER = ["default", "low", "medium", "high"]
ARENA_ORDER = ["BattleSnake", "CoreWar", "Halite", "HuskyBench", "RoboCode", "RobotRumble"]
ARENA_LABELS = {
    "BattleSnake": "BattleSnake",
    "CoreWar": "CoreWar",
    "Halite": "Halite",
    "HuskyBench": "HuskyBench",
    "RoboCode": "RoboCode",
    "RobotRumble": "RobotRumble",
}


def iter_live_metadata(run_root: Path):
    for metadata_path in sorted(run_root.rglob("metadata.json")):
        if "quarantine" in metadata_path.parts:
            continue
        yield metadata_path


def parse_tier(model_name: str) -> str:
    for tier in TIER_ORDER:
        if model_name.endswith(f"-{tier}"):
            return tier
    raise ValueError(f"Could not parse tier from {model_name}")


def load_stats(run_root: Path):
    by_tier = {tier: {"gpt-5.4": 0, "gpt-5.3-codex": 0, "ties": 0, "total": 0} for tier in TIER_ORDER}
    by_arena_tier = {
        arena: {tier: {"gpt-5.4": 0, "gpt-5.3-codex": 0, "ties": 0, "total": 0} for tier in TIER_ORDER}
        for arena in ARENA_ORDER
    }

    for metadata_path in iter_live_metadata(run_root):
        data = json.loads(metadata_path.read_text())
        game_name = data.get("config", {}).get("game", {}).get("name") or data.get("game", {}).get("name")
        if game_name not in ARENA_ORDER:
            continue

        players = [p.get("name") for p in data.get("config", {}).get("players", []) if isinstance(p, dict)]
        if len(players) != 2:
            continue

        tier = parse_tier(players[0])
        rounds = data.get("round_stats", {})
        if isinstance(rounds, dict):
            rounds = list(rounds.values())

        for round_stat in rounds:
            winner = round_stat.get("winner")
            bucket = by_tier[tier]
            arena_bucket = by_arena_tier[game_name][tier]
            if winner == "Tie":
                bucket["ties"] += 1
                arena_bucket["ties"] += 1
            elif winner and winner.startswith("gpt-5.4"):
                bucket["gpt-5.4"] += 1
                arena_bucket["gpt-5.4"] += 1
            elif winner and winner.startswith("gpt-5.3-codex"):
                bucket["gpt-5.3-codex"] += 1
                arena_bucket["gpt-5.3-codex"] += 1
            else:
                continue
            bucket["total"] += 1
            arena_bucket["total"] += 1

    return by_tier, by_arena_tier


def plot_overall(by_tier, output_path: Path) -> None:
    tiers = TIER_ORDER
    gpt54_rates = []
    codex_rates = []

    for tier in tiers:
        total = by_tier[tier]["total"] or 1
        gpt54_rates.append(100 * by_tier[tier]["gpt-5.4"] / total)
        codex_rates.append(100 * by_tier[tier]["gpt-5.3-codex"] / total)

    y = np.arange(len(tiers))
    fig, ax = plt.subplots(figsize=(9, 4.8))

    ax.barh(y - 0.18, gpt54_rates, height=0.34, color="#0B8F55", label="GPT-5.4")
    ax.barh(y + 0.18, codex_rates, height=0.34, color="#C75B12", label="GPT-5.3-Codex")

    for idx, tier in enumerate(tiers):
        total = by_tier[tier]["total"]
        ax.text(gpt54_rates[idx] + 1.2, y[idx] - 0.18, f"{by_tier[tier]['gpt-5.4']}/{total}", va="center", fontproperties=FONT_REG, fontsize=10)
        ax.text(codex_rates[idx] + 1.2, y[idx] + 0.18, f"{by_tier[tier]['gpt-5.3-codex']}/{total}", va="center", fontproperties=FONT_REG, fontsize=10)

    ax.set_yticks(y)
    ax.set_yticklabels([tier.title() for tier in tiers], fontproperties=FONT_REG, fontsize=11)
    ax.set_xlim(0, 100)
    ax.set_xlabel("Win Rate Excluding Ties (%)", fontproperties=FONT_BOLD, fontsize=12)
    ax.set_title("Direct Head-to-Head Win Rate by Reasoning Mode", fontproperties=FONT_BOLD, fontsize=14, pad=10)
    ax.grid(axis="x", alpha=0.25)
    ax.legend(frameon=False, prop=FONT_REG, loc="lower right")
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)

    fig.tight_layout()
    fig.savefig(output_path.with_suffix(".png"), dpi=220, bbox_inches="tight")
    fig.savefig(output_path.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(fig)


def plot_heatmap(by_arena_tier, output_path: Path) -> None:
    matrix = []
    annotations = []
    for arena in ARENA_ORDER:
        row = []
        ann_row = []
        for tier in TIER_ORDER:
            bucket = by_arena_tier[arena][tier]
            total = bucket["total"] or 1
            rate = 100 * bucket["gpt-5.4"] / total
            row.append(rate)
            ann_row.append(f"{bucket['gpt-5.4']}/{total}")
        matrix.append(row)
        annotations.append(ann_row)

    matrix = np.array(matrix)

    fig, ax = plt.subplots(figsize=(8.8, 5.8))
    image = ax.imshow(matrix, cmap="RdYlGn", vmin=0, vmax=100, aspect="auto")

    ax.set_xticks(np.arange(len(TIER_ORDER)))
    ax.set_xticklabels([tier.title() for tier in TIER_ORDER], fontproperties=FONT_REG, fontsize=11)
    ax.set_yticks(np.arange(len(ARENA_ORDER)))
    ax.set_yticklabels([ARENA_LABELS[a] for a in ARENA_ORDER], fontproperties=FONT_REG, fontsize=11)
    ax.set_title("GPT-5.4 Win Rate by Arena and Reasoning Mode", fontproperties=FONT_BOLD, fontsize=14, pad=10)

    for row_idx in range(len(ARENA_ORDER)):
        for col_idx in range(len(TIER_ORDER)):
            value = matrix[row_idx, col_idx]
            color = "#111111" if 25 <= value <= 75 else "#FFFFFF"
            ax.text(
                col_idx,
                row_idx,
                annotations[row_idx][col_idx],
                ha="center",
                va="center",
                color=color,
                fontproperties=FONT_REG,
                fontsize=10,
            )

    cbar = fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("GPT-5.4 Win Rate (%)", fontproperties=FONT_BOLD, fontsize=11)

    fig.tight_layout()
    fig.savefig(output_path.with_suffix(".png"), dpi=220, bbox_inches="tight")
    fig.savefig(output_path.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(fig)


def plot_per_game(by_arena_tier, output_path: Path) -> None:
    fig, axes = plt.subplots(2, 3, figsize=(13.5, 8.2), sharex=True)
    axes = axes.flatten()
    y = np.arange(len(TIER_ORDER))

    for ax, arena in zip(axes, ARENA_ORDER):
        gpt54_rates = []
        codex_rates = []
        for tier in TIER_ORDER:
            bucket = by_arena_tier[arena][tier]
            total = bucket["total"] or 1
            gpt54_rates.append(100 * bucket["gpt-5.4"] / total)
            codex_rates.append(100 * bucket["gpt-5.3-codex"] / total)

        ax.barh(y - 0.18, gpt54_rates, height=0.34, color="#0B8F55", label="GPT-5.4")
        ax.barh(y + 0.18, codex_rates, height=0.34, color="#C75B12", label="GPT-5.3-Codex")

        for idx, tier in enumerate(TIER_ORDER):
            total = by_arena_tier[arena][tier]["total"]
            ax.text(gpt54_rates[idx] + 1.0, y[idx] - 0.18, f"{by_arena_tier[arena][tier]['gpt-5.4']}/{total}", va="center", fontproperties=FONT_REG, fontsize=8.5)
            ax.text(codex_rates[idx] + 1.0, y[idx] + 0.18, f"{by_arena_tier[arena][tier]['gpt-5.3-codex']}/{total}", va="center", fontproperties=FONT_REG, fontsize=8.5)

        ax.set_title(ARENA_LABELS[arena], fontproperties=FONT_BOLD, fontsize=12, pad=8)
        ax.set_xlim(0, 100)
        ax.set_yticks(y)
        ax.set_yticklabels([tier.title() for tier in TIER_ORDER], fontproperties=FONT_REG, fontsize=10)
        ax.grid(axis="x", alpha=0.2)
        for spine in ("top", "right"):
            ax.spines[spine].set_visible(False)

    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, frameon=False, prop=FONT_REG, loc="lower center", ncol=2, bbox_to_anchor=(0.5, -0.01))
    fig.suptitle("Direct Head-to-Head Win Rate by Arena and Reasoning Mode", fontproperties=FONT_BOLD, fontsize=15, y=0.98)
    fig.supxlabel("Win Rate Excluding Ties (%)", fontproperties=FONT_BOLD, fontsize=12, y=0.04)
    fig.tight_layout(rect=(0, 0.05, 1, 0.95))
    fig.savefig(output_path.with_suffix(".png"), dpi=220, bbox_inches="tight")
    fig.savefig(output_path.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description="Plot direct head-to-head reasoning-mode results from tournament metadata.")
    parser.add_argument("run_root", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    by_tier, by_arena_tier = load_stats(args.run_root)
    plot_overall(by_tier, args.output_dir / "reasoning_mode_win_rate")
    plot_heatmap(by_arena_tier, args.output_dir / "reasoning_mode_arena_heatmap")
    plot_per_game(by_arena_tier, args.output_dir / "reasoning_mode_win_rate_per_game")


if __name__ == "__main__":
    main()
