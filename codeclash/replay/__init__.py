"""Replay layer: turn recorded tournament games into browsable playback.

``codeclash replay <folder>`` is the CLI consumer of this package. The reusable core
lives here (:mod:`codeclash.replay.base`) plus per-arena renderers under
``codeclash/arenas/<arena>/replay.py``; a future viewer integration can consume the
same renderers.
"""

from __future__ import annotations

import json
from pathlib import Path

from codeclash.replay.base import (
    GameRef,
    ReplayData,
    ReplayRenderer,
    TournamentInfo,
    build_index,
    build_page,
    discover_games,
    read_sim,
)

__all__ = [
    "GameRef",
    "ReplayData",
    "ReplayRenderer",
    "TournamentInfo",
    "build_index",
    "build_page",
    "discover_games",
    "get_replayer",
    "load_tournament",
    "read_sim",
]


def get_replayer(arena: str) -> ReplayRenderer | None:
    """Return the renderer for an arena, or ``None`` if none exists yet.

    Imports are lazy so pulling in one arena's replay code never drags in the others.
    """
    if arena == "BattleSnake":
        from codeclash.arenas.battlesnake.replay import BattleSnakeReplayer

        return BattleSnakeReplayer()
    if arena == "RobotRumble":
        from codeclash.arenas.robotrumble.replay import RobotRumbleReplayer

        return RobotRumbleReplayer()
    if arena == "Chess":
        from codeclash.arenas.chess.replay import ChessReplayer

        return ChessReplayer()
    if arena == "Gomoku":
        from codeclash.arenas.gomoku.replay import GomokuReplayer

        return GomokuReplayer()
    if arena == "PaintVolley":
        from codeclash.arenas.paintvolley.replay import PaintVolleyReplayer

        return PaintVolleyReplayer()
    if arena == "Ants":
        from codeclash.arenas.ants.replay import AntsReplayer

        return AntsReplayer()
    if arena == "Halite":
        from codeclash.arenas.halite.replay import HaliteReplayer

        return HaliteReplayer()
    if arena == "Halite2":
        from codeclash.arenas.halite2.replay import Halite2Replayer

        return Halite2Replayer()
    if arena == "Halite3":
        from codeclash.arenas.halite3.replay import Halite3Replayer

        return Halite3Replayer()
    if arena == "Bomberland":
        from codeclash.arenas.bomberland.replay import BomberlandReplayer

        return BomberlandReplayer()
    if arena == "Bridge":
        from codeclash.arenas.bridge.replay import BridgeReplayer

        return BridgeReplayer()
    if arena == "Figgie":
        from codeclash.arenas.figgie.replay import FiggieReplayer

        return FiggieReplayer()
    return None


def _player_model(player: dict) -> str | None:
    """Extract a display model name from a player config (mirrors the viewer)."""
    config = player.get("config", {}) or {}
    model = config.get("model")
    if isinstance(model, dict):
        return model.get("model_name")
    return model


def _arena_from_name(folder: Path) -> str:
    """Derive the arena from a tournament folder name.

    e.g. ``PvpTournament.RobotRumble.r1.s1.p2.flail.luisa.260702175500`` -> ``RobotRumble``.
    """
    parts = folder.name.split(".")
    return parts[1] if len(parts) > 1 else ""


def _fill_sim_winners(games: list[GameRef], renderer: ReplayRenderer | None, players: list[dict]) -> None:
    """Populate each game's per-sim winner via the renderer's cheap ``peek_winner``.
    Skipped entirely for arenas that don't implement it (avoids extra sim I/O)."""
    if renderer is None or type(renderer).peek_winner is ReplayRenderer.peek_winner:
        return
    for g in games:
        try:
            res = renderer.peek_winner(read_sim(g), players)
        except Exception:
            res = None
        if res is not None:
            g.sim_winner, g.sim_draw = res


def load_tournament(folder: Path) -> TournamentInfo:
    """Read a tournament folder: metadata (if present) plus every discoverable game.

    The arena comes from ``metadata.json`` when available, otherwise from the folder name
    (which encodes it, e.g. ``PvpTournament.RobotRumble.r1.s1.p2...``).
    """
    folder = Path(folder)
    meta_path = folder / "metadata.json"
    if not meta_path.exists():
        # A ladder / aggregate folder is a parent of PvP sub-tournaments, each with its own
        # metadata.json (e.g. LadderTournament.<Arena>.../ from `ladder run`, or logs/ladder/<Arena>/
        # from `ladder make`). Merge every sub-tournament's games, tagged by matchup.
        children = [d for d in sorted(folder.iterdir()) if d.is_dir() and (d / "metadata.json").exists()]
        if children:
            arena, players, games = _arena_from_name(folder), [], []
            for child in children:
                ct = load_tournament(child)
                arena = arena or ct.arena
                players = players or ct.players
                matchup = ", ".join(p["name"] for p in ct.players) or child.name
                for g in ct.games:
                    g.group = matchup
                    games.append(g)
            games.sort(key=lambda g: (g.group, g.round, g.sim))
            return TournamentInfo(
                folder=folder,
                arena=arena,
                players=players,
                rounds=None,
                sims_per_round=None,
                round_winners={},
                games=games,
            )
        # Otherwise a bare sim folder — arena comes from the folder name.
        arena = _arena_from_name(folder)
        renderer = get_replayer(arena)
        games = discover_games(folder, renderer.sim_glob) if renderer else []
        _fill_sim_winners(games, renderer, [])
        return TournamentInfo(
            folder=folder, arena=arena, players=[], rounds=None, sims_per_round=None, round_winners={}, games=games
        )
    meta = json.loads(meta_path.read_text())
    config = meta.get("config", {})
    game = config.get("game", {})
    arena = game.get("name") or meta.get("game", {}).get("name") or _arena_from_name(folder)

    players = [
        {"name": p.get("name", "?"), "model": _player_model(p)}
        for p in config.get("players", [])
        if isinstance(p, dict)
    ]
    round_winners = {int(k): v.get("winner") for k, v in meta.get("round_stats", {}).items()}

    renderer = get_replayer(arena)
    games = discover_games(folder, renderer.sim_glob) if renderer else []
    for g in games:  # attach each game's round winner for the index
        g.winner = round_winners.get(g.round)
    _fill_sim_winners(games, renderer, players)

    return TournamentInfo(
        folder=folder,
        arena=arena,
        players=players,
        rounds=config.get("tournament", {}).get("rounds"),
        sims_per_round=game.get("sims_per_round"),
        round_winners=round_winners,
        games=games,
    )
