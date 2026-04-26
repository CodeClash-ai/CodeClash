#!/usr/bin/env python3
import argparse
import json
from pathlib import Path


GAME_ORDER = ["halite", "huskybench", "corewar", "robotrumble", "robocode", "battlesnake", "all"]


def load_board(path: Path) -> dict:
    with path.open() as f:
        return json.load(f)


def as_lookup(board: list[dict]) -> dict[str, tuple[int, int]]:
    return {row["model"]: (int(row["elo"]), int(row["elo_std"])) for row in board}


def main(input: Path, out: Path) -> None:
    data = load_board(input)
    models = {row["model"] for section in data.values() for row in section.get("board", [])}

    rows = []
    for model in sorted(models):
        all_board = data.get("all", {}).get("board", [])
        rank = next((int(r["rank"]) for r in all_board if r["model"] == model), 999)

        vals = []
        for game in GAME_ORDER:
            lookup = as_lookup(data.get(game, {}).get("board", []))
            elo, std = lookup.get(model, (0, 0))
            vals.append(f"{elo} ± {std}")
        rows.append((rank, model, vals))

    rows.sort(key=lambda x: x[0])

    header = "| Rank | Model | Halite | HuskyBench | CoreWar | RobotRumble | Robocode | BattleSnake | All |\n"
    header += "|---:|---|---:|---:|---:|---:|---:|---:|---:|\n"
    lines = [header]
    for rank, model, vals in rows:
        lines.append(
            f"| {rank} | {model} | {vals[0]} | {vals[1]} | {vals[2]} | {vals[3]} | {vals[4]} | {vals[5]} | {vals[6]} |\n"
        )

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(lines))
    print(f"Wrote {out}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    main(args.input, args.out)
