#!/usr/bin/env python3
"""Scrape viewer.codeclash.ai completed runs and download metadata.json files.

By default this targets the 8-model public leaderboard cohort and the 6 arenas:
BattleSnake, CoreWar, Halite, RobotRumble, RoboCode, HuskyBench.
"""

from __future__ import annotations

import argparse
import json
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path


DEFAULT_MODELS = [
    "claude-sonnet-4-5-20250929",
    "gpt-5",
    "o3",
    "claude-sonnet-4-20250514",
    "gpt-5-mini",
    "gemini-2.5-pro",
    "grok-code-fast-1",
    "qwen3-coder-plus-2025-09-23",
]

DEFAULT_GAMES = ["BattleSnake", "CoreWar", "Halite", "RobotRumble", "RoboCode", "HuskyBench"]

VIEWER_BASE = "https://viewer.codeclash.ai"


@dataclass(frozen=True)
class RunRef:
    rel_path: str
    game: str
    rounds: int
    sims: int
    players: int
    p1: str
    p2: str
    ts: str


def fetch_index_html() -> str:
    with urllib.request.urlopen(VIEWER_BASE + "/", timeout=60) as r:
        return r.read().decode("utf-8", errors="replace")


def extract_paths(html: str) -> list[str]:
    # Example: data-path="completed/PvpTournament.BattleSnake.r15.s1000.p2.a.b.251002061714"
    return sorted(set(re.findall(r'data-path="(completed/PvpTournament\.[^"]+)"', html)))


def _alias_variants(alias: str) -> set[str]:
    norm = re.sub(r"[^a-zA-Z0-9]", "", alias).lower()
    return {alias, norm}


def _build_variant_lookup(models: set[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for m in models:
        for v in _alias_variants(m):
            out[v] = m
    return out


def parse_run(path: str, models: set[str], variant_to_alias: dict[str, str]) -> RunRef | None:
    # Parse fixed front/back first, then decode the middle p1.p2 region safely.
    if not path.startswith("completed/PvpTournament."):
        return None
    # Strip prefix "completed/PvpTournament."
    body = path[len("completed/PvpTournament.") :]
    # Find timestamp token (12 digits), allowing optional suffix after it
    # (e.g. ".<uuid>-uuid" in some games).
    try:
        pre = body
        parts = pre.split(".")
        ts_idx = None
        for i in range(len(parts) - 1, -1, -1):
            if re.fullmatch(r"\d{12}", parts[i]):
                ts_idx = i
                break
        if ts_idx is None:
            return None
        ts = parts[ts_idx]
        pre = ".".join(parts[:ts_idx])
    except ValueError:
        return None
    parts = pre.split(".")
    if len(parts) < 5:
        return None
    game = parts[0]
    rounds_s = parts[1]
    sims_s = parts[2]
    players_s = parts[3]
    model_region = ".".join(parts[4:])

    if not rounds_s.startswith("r") or not sims_s.startswith("s") or not players_s.startswith("p"):
        return None

    rounds = int(rounds_s[1:])
    sims = int(sims_s[1:])
    players = int(players_s[1:])

    # Identify p1/p2 using known model aliases (including normalized
    # hyphenless variants used in some logs).
    p1 = p2 = None
    variants = sorted(variant_to_alias.keys(), key=len, reverse=True)
    for alias_variant in variants:
        pref = alias_variant + "."
        if model_region.startswith(pref):
            tail = model_region[len(pref) :]
            if tail in variant_to_alias:
                p1 = variant_to_alias[alias_variant]
                p2 = variant_to_alias[tail]
                break
    if p1 is None or p2 is None:
        return None

    return RunRef(
        rel_path=path,
        game=game,
        rounds=rounds,
        sims=sims,
        players=players,
        p1=p1,
        p2=p2,
        ts=ts,
    )


def build_download_url(rel_path: str) -> str:
    # Endpoint expects absolute path on the viewer host.
    abs_path = f"/home/klieret/CodeClash/logs/{rel_path}/metadata.json"
    q = urllib.parse.urlencode({"path": abs_path})
    return f"{VIEWER_BASE}/download-file/?{q}"


def build_game_page_url(rel_path: str) -> str:
    return f"{VIEWER_BASE}/game/{rel_path}.html"


def _extract_json_object_after_marker(text: str, marker: str) -> str | None:
    idx = text.find(marker)
    if idx < 0:
        return None
    i = idx + len(marker)
    while i < len(text) and text[i].isspace():
        i += 1
    if i >= len(text) or text[i] != "{":
        return None

    # Brace-match while respecting quoted strings.
    depth = 0
    in_str = False
    escaped = False
    start = i
    for j in range(i, len(text)):
        ch = text[j]
        if in_str:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : j + 1]
    return None


def _extract_embedded_metadata_from_game_html(html: str) -> dict | None:
    blob = _extract_json_object_after_marker(html, "initializeJSONEditors(")
    if not blob:
        return None
    return json.loads(blob)


def download(url: str, out_file: Path) -> bool:
    out_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        with urllib.request.urlopen(url, timeout=60) as r:
            data = r.read()
        out_file.write_bytes(data)
        # basic sanity
        json.loads(out_file.read_text())
        return True
    except Exception:
        return False


def download_metadata_via_game_page(rel_path: str, out_file: Path) -> bool:
    out_file.parent.mkdir(parents=True, exist_ok=True)
    page_url = build_game_page_url(rel_path)
    try:
        with urllib.request.urlopen(page_url, timeout=60) as r:
            html = r.read().decode("utf-8", errors="replace")
        payload = _extract_embedded_metadata_from_game_html(html)
        if payload is None:
            return False
        # Viewer pages embed a wrapper object used by front-end widgets. The
        # actual tournament metadata is under "results".
        metadata = payload.get("results") if isinstance(payload, dict) else None
        if not isinstance(metadata, dict):
            metadata = payload
        out_file.write_text(json.dumps(metadata, indent=2))
        # basic sanity
        json.loads(out_file.read_text())
        return True
    except Exception:
        return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--output-root",
        type=Path,
        required=True,
        help="Local root to save downloaded runs (folders with metadata.json).",
    )
    ap.add_argument("--models", nargs="*", default=DEFAULT_MODELS, help="Model aliases to include.")
    ap.add_argument("--games", nargs="*", default=DEFAULT_GAMES, help="Game names to include.")
    ap.add_argument("--rounds", type=int, default=15)
    ap.add_argument("--players", type=int, default=2)
    ap.add_argument(
        "--strategy",
        choices=["latest-per-pair-game", "all-matching"],
        default="latest-per-pair-game",
        help="Download only latest run per (game,unordered pair), or all matching runs.",
    )
    args = ap.parse_args()

    models = set(args.models)
    games = set(args.games)
    variant_to_alias = _build_variant_lookup(models)

    html = fetch_index_html()
    paths = extract_paths(html)

    runs: list[RunRef] = []
    for p in paths:
        r = parse_run(p, models, variant_to_alias)
        if r is None:
            continue
        if r.game not in games:
            continue
        if r.rounds != args.rounds or r.players != args.players:
            continue
        runs.append(r)

    if args.strategy == "latest-per-pair-game":
        best: dict[tuple[str, tuple[str, str]], RunRef] = {}
        for r in runs:
            pair = tuple(sorted((r.p1, r.p2)))
            k = (r.game, pair)
            prev = best.get(k)
            if prev is None or int(r.ts) > int(prev.ts):
                best[k] = r
        selected = sorted(best.values(), key=lambda x: (x.game, tuple(sorted((x.p1, x.p2))), x.ts))
    else:
        selected = sorted(runs, key=lambda x: (x.game, x.p1, x.p2, x.ts))

    ok = 0
    fail = 0
    manifest = []
    for r in selected:
        url = build_download_url(r.rel_path)
        page_url = build_game_page_url(r.rel_path)
        out_file = args.output_root / r.rel_path / "metadata.json"
        success = download_metadata_via_game_page(r.rel_path, out_file)
        if not success:
            success = download(url, out_file)
        manifest.append(
            {
                "rel_path": r.rel_path,
                "game": r.game,
                "p1": r.p1,
                "p2": r.p2,
                "rounds": r.rounds,
                "players": r.players,
                "sims": r.sims,
                "ts": r.ts,
                "page_url": page_url,
                "download_url": url,
                "ok": success,
                "local_metadata": str(out_file),
            }
        )
        if success:
            ok += 1
        else:
            fail += 1

    args.output_root.mkdir(parents=True, exist_ok=True)
    (args.output_root / "download_manifest.json").write_text(json.dumps(manifest, indent=2))

    summary = {
        "selected_runs": len(selected),
        "download_ok": ok,
        "download_failed": fail,
        "output_root": str(args.output_root),
        "strategy": args.strategy,
        "models": sorted(models),
        "games": sorted(games),
    }
    (args.output_root / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    return 0 if fail == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
