#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt

from codeclash.analysis.viz.utils import FONT_BOLD, FONT_REG, MARKERS, MODEL_TO_COLOR, model_display_name


GAME_ORDER = ["halite", "huskybench", "corewar", "robotrumble", "robocode", "battlesnake", "all"]
GAME_LABELS = {
    "halite": "Halite",
    "huskybench": "HuskyBench",
    "corewar": "CoreWar",
    "robotrumble": "RobotRumble",
    "robocode": "RoboCode",
    "battlesnake": "BattleSnake",
    "all": "Overall",
}


def canonical_model_name(name: str) -> str:
    lowered = name.lower()
    if lowered == "gpt-5":
        return "gpt-5"
    return lowered


def base_model_name(name: str) -> str:
    for suffix in ("-default", "-low", "-medium", "-high"):
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return name


def load_rows(leaderboards_path: Path) -> tuple[list[str], dict[str, dict[str, tuple[int, int]]]]:
    raw = json.loads(leaderboards_path.read_text())
    models: list[str] = []
    rows: dict[str, dict[str, tuple[int, int]]] = {}

    for game_key in GAME_ORDER:
        board = raw.get(game_key, {}).get("board", [])
        rows[game_key] = {}
        for entry in board:
            model = canonical_model_name(entry["model"])
            if model not in models:
                models.append(model)
            rows[game_key][model] = (int(entry["elo"]), int(entry["elo_std"]))
    return models, rows


def plot(rows: dict[str, dict[str, tuple[int, int]]], models: list[str], output_base: Path, title: str) -> None:
    fig, ax = plt.subplots(figsize=(11.5, 7.0))

    y_positions = list(range(len(GAME_ORDER)))
    spread = 0.48
    if len(models) == 1:
        offsets = [0.0]
    else:
        step = spread / (len(models) - 1)
        offsets = [(-spread / 2) + (i * step) for i in range(len(models))]

    for idx, model in enumerate(models):
        ys = [y + offsets[idx] for y in y_positions]
        xs = [rows[g][model][0] for g in GAME_ORDER]
        xerr = [rows[g][model][1] for g in GAME_ORDER]
        color = MODEL_TO_COLOR.get(model, MODEL_TO_COLOR.get(base_model_name(model), "#4C78A8"))
        marker = MARKERS[idx % len(MARKERS)]

        ax.errorbar(
            xs,
            ys,
            xerr=xerr,
            fmt=marker,
            color=color,
            ecolor=color,
            elinewidth=1.6,
            capsize=3,
            markersize=7,
            label=model_display_name(model),
        )

    ax.set_yticks(y_positions)
    ax.set_yticklabels([GAME_LABELS[g] for g in GAME_ORDER], fontproperties=FONT_REG, fontsize=12)
    ax.invert_yaxis()
    ax.set_xlabel("Elo", fontproperties=FONT_BOLD, fontsize=13)
    ax.set_title(title, fontproperties=FONT_BOLD, fontsize=15, pad=12)
    ax.grid(axis="x", alpha=0.25)
    ax.axvline(1200, color="#888888", linestyle="--", linewidth=1, alpha=0.5)
    ax.legend(frameon=False, prop=FONT_REG, loc="lower right", ncol=2)

    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)

    fig.tight_layout()
    fig.savefig(output_base.with_suffix(".png"), dpi=220, bbox_inches="tight")
    fig.savefig(output_base.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a shareable per-game Elo comparison plot.")
    parser.add_argument("leaderboards_json", type=Path)
    parser.add_argument("--output-base", type=Path, required=True)
    parser.add_argument("--title", type=str, default="OpenAI Benchmark Results by Arena")
    args = parser.parse_args()

    models, rows = load_rows(args.leaderboards_json)
    plot(rows, models, args.output_base, args.title)


if __name__ == "__main__":
    main()
