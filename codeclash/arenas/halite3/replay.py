"""Halite III replay renderer.

Halite III is a grid resource game: ships spawn from a factory, mine ``halite`` (energy)
from cells, and bank it. Its ``.hlt`` replay is **zstd-compressed** JSON with a static
``production_map`` (per-cell ``{energy}``), per-frame ``entities`` (ships with x/y/energy),
per-frame banked ``energy`` per player, and ``game_statistics`` (ranks). We render the
halite map as a green field with factories marked and ships as owner-colored dots.

Requires the Halite3 arena to emit ``--replay-directory`` (the hyphenated flag the engine
actually uses) so the replay is captured — see ``halite3.py``.
"""

from __future__ import annotations

import json

from codeclash.replay.base import ReplayData, ReplayRenderer

PALETTE = ["#3B78FF", "#E5484D", "#30A46C", "#F5A623", "#8E4EC6", "#12A594", "#E93D82", "#F76B15"]

DRAW_JS = """
const ARENA = (function(){
  let W, H, CELL, GRID, MAXE, COL, FACT;
  function setup(cv, G){
    W = G.w; H = G.h; GRID = G.grid; MAXE = G.maxenergy || 1; COL = G.colors; FACT = G.factories || [];
    CELL = Math.max(8, Math.min(20, Math.floor(620 / Math.max(W, H))));
    cv.width = W * CELL; cv.height = H * CELL;
  }
  function draw(ctx, cv, G, i){
    const f = G.frames[i];
    // halite field (static production map): brighter teal = more halite
    for(let y=0;y<H;y++) for(let x=0;x<W;x++){
      const v = GRID[y][x] / MAXE;
      ctx.fillStyle = `rgb(${Math.round(18+30*v)},${Math.round(34+120*v)},${Math.round(34+96*v)})`;
      ctx.fillRect(x*CELL, y*CELL, CELL, CELL);
    }
    // factories: owner-colored square with white border
    for(const fc of FACT){
      ctx.fillStyle = COL[fc.o] || '#888'; ctx.fillRect(fc.x*CELL+1, fc.y*CELL+1, CELL-2, CELL-2);
      ctx.strokeStyle = '#fff'; ctx.lineWidth = 2; ctx.strokeRect(fc.x*CELL+1, fc.y*CELL+1, CELL-2, CELL-2);
    }
    // ships: owner-colored dots, brightness by carried halite
    for(const s of f.ships){
      ctx.globalAlpha = 0.55 + 0.45 * Math.min(1, s.e / 1000);
      ctx.fillStyle = COL[s.o] || '#888';
      ctx.beginPath(); ctx.arc(s.x*CELL+CELL/2, s.y*CELL+CELL/2, CELL*0.34, 0, 7); ctx.fill();
    }
    ctx.globalAlpha = 1;
  }
  function side(G, i){
    const f = G.frames[i], NAMES = G.names || {}, EN = f.energy || {};
    const ships = {};
    for(const s of f.ships) ships[s.o] = (ships[s.o]||0) + 1;
    return Object.keys(COL).map(o=>`
      <div class="team"><div class="tname"><span class="sw" style="background:${COL[o]}"></span>${NAMES[o]||('Player '+o)}</div>
        <div class="stat"><span>banked halite</span><b>${EN[o]||0}</b></div>
        <div class="stat"><span>ships</span><b>${ships[o]||0}</b></div></div>`).join('');
  }
  return {setup, draw, side};
})();
"""


class Halite3Replayer(ReplayRenderer):
    arena = "Halite3"
    sim_glob = "*.hlt"
    DRAW_JS = DRAW_JS

    def parse(self, raw: bytes, players=None) -> ReplayData:
        import zstandard as zstd

        d = json.loads(zstd.ZstdDecompressor().decompress(raw))
        pm = d["production_map"]
        w, h = pm["width"], pm["height"]
        grid = [[pm["grid"][y][x].get("energy", 0) for x in range(w)] for y in range(h)]
        maxe = max((max(row) for row in grid), default=1) or 1

        players_meta = d.get("players", [])
        num = d.get("number_of_players", len(players_meta)) or 2

        def name_for(pid: int) -> str:
            if players and len(players) > pid:
                return players[pid]["name"]
            if len(players_meta) > pid:
                return players_meta[pid].get("name", f"Player {pid}")
            return f"Player {pid}"

        colors = {p: PALETTE[p % len(PALETTE)] for p in range(num)}
        names = {p: name_for(p) for p in range(num)}
        factories = [
            {"o": pm_["player_id"], "x": pm_["factory_location"]["x"], "y": pm_["factory_location"]["y"]}
            for pm_ in players_meta
            if "factory_location" in pm_
        ]

        frames = []
        for i, f in enumerate(d["full_frames"]):
            ships = [
                {"o": int(pid), "x": e["x"], "y": e["y"], "e": e.get("energy", 0)}
                for pid, ents in f.get("entities", {}).items()
                for e in ents.values()
            ]
            energy = {int(k): v for k, v in f.get("energy", {}).items()}
            frames.append({"turn": i, "ships": ships, "energy": energy})

        # Winner = rank 1 in game_statistics (multiple rank-1 -> draw).
        stats = d.get("game_statistics", {}).get("player_statistics", [])
        rank1 = [p for p in stats if p.get("rank") == 1]
        if len(rank1) == 1:
            winner, draw = name_for(rank1[0]["player_id"]), False
        else:
            winner, draw = None, bool(rank1)

        return ReplayData(
            w=w,
            h=h,
            frames=frames,
            winner=winner,
            draw=draw,
            extra={"grid": grid, "maxenergy": maxe, "colors": colors, "names": names, "factories": factories},
        )
