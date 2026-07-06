"""Halite II replay renderer.

Halite II is the continuous-space "ships & planets" game (distinct from Halite I's
territory grid), so it gets its own renderer. Its ``.hlt`` replay is **zstd-compressed**
JSON: a static ``planets`` list (x/y/radius) plus per-frame ``ships`` (``{owner: {id:
{x, y, health, docking, ...}}}``) and per-frame planet ownership. Ships are drawn as dots
in continuous space; planets as circles tinted by their current owner.

The arena already passes ``--replaydirectory``; the OCaml-starter symlink fix (see
``halite.py``) is what lets a dummy game actually produce this replay.
"""

from __future__ import annotations

import json

from codeclash.replay.base import ReplayData, ReplayRenderer

PALETTE = ["#3B78FF", "#E5484D", "#30A46C", "#F5A623", "#8E4EC6", "#12A594", "#E93D82", "#F76B15"]

DRAW_JS = """
const ARENA = (function(){
  let W, H, SC, COL, PLANETS, MAXHP;
  function setup(cv, G){
    W = G.w; H = G.h; COL = G.colors; PLANETS = G.planets; MAXHP = G.maxhp || 255;
    SC = Math.min(760 / W, 500 / H);
    cv.width = Math.round(W * SC); cv.height = Math.round(H * SC);
  }
  function draw(ctx, cv, G, i){
    const f = G.frames[i];
    ctx.clearRect(0, 0, cv.width, cv.height);
    // planets: circle tinted by this frame's owner (neutral grey if unowned)
    for(const p of PLANETS){
      const owner = f.planets[p.id];
      ctx.beginPath(); ctx.arc(p.x*SC, p.y*SC, Math.max(2, p.r*SC), 0, 7);
      ctx.fillStyle = (owner==null) ? '#3a3f46' : (COL[owner] || '#888');
      ctx.globalAlpha = (owner==null) ? 0.8 : 0.5; ctx.fill(); ctx.globalAlpha = 1;
      ctx.strokeStyle = 'rgba(255,255,255,0.15)'; ctx.lineWidth = 1; ctx.stroke();
    }
    // ships: dots colored by owner, brightness by health
    for(const s of f.ships){
      ctx.globalAlpha = 0.4 + 0.6 * Math.min(1, s.hp / MAXHP);
      ctx.fillStyle = COL[s.o] || '#888';
      ctx.beginPath(); ctx.arc(s.x*SC, s.y*SC, Math.max(1.5, SC*0.9), 0, 7); ctx.fill();
    }
    ctx.globalAlpha = 1;
  }
  function side(G, i){
    const f = G.frames[i], NAMES = G.names || {};
    const ships = {}, planets = {};
    for(const s of f.ships) ships[s.o] = (ships[s.o]||0) + 1;
    for(const id in f.planets){ const o = f.planets[id]; if(o!=null) planets[o] = (planets[o]||0) + 1; }
    return Object.keys(COL).map(o=>`
      <div class="team"><div class="tname"><span class="sw" style="background:${COL[o]}"></span>${NAMES[o]||('Player '+o)}</div>
        <div class="stat"><span>ships</span><b>${ships[o]||0}</b></div>
        <div class="stat"><span>planets</span><b>${planets[o]||0}</b></div></div>`).join('');
  }
  return {setup, draw, side};
})();
"""


class Halite2Replayer(ReplayRenderer):
    arena = "Halite2"
    sim_glob = "*.hlt"
    DRAW_JS = DRAW_JS

    def parse(self, raw: bytes, players=None) -> ReplayData:
        import zstandard as zstd

        d = json.loads(zstd.ZstdDecompressor().decompress(raw))
        w, h = d["width"], d["height"]
        num_players = d.get("num_players", 2)
        engine_names = d.get("player_names", [])

        def name_for(owner: int) -> str:
            if players and len(players) > owner:
                return players[owner]["name"]
            if len(engine_names) > owner:
                return engine_names[owner]
            return f"Player {owner}"

        static_planets = [
            {"id": p["id"], "x": round(p["x"], 2), "y": round(p["y"], 2), "r": round(p["r"], 2)}
            for p in d.get("planets", [])
        ]
        colors = {o: PALETTE[o % len(PALETTE)] for o in range(num_players)}  # owner is 0-based here
        names = {o: name_for(o) for o in range(num_players)}

        frames = []
        for i, f in enumerate(d["frames"]):
            ships = [
                {"o": int(owner), "x": round(s["x"], 2), "y": round(s["y"], 2), "hp": s.get("health", 0)}
                for owner, fleet in f.get("ships", {}).items()
                for s in fleet.values()
            ]
            planet_owner = {pid: pl.get("owner") for pid, pl in f.get("planets", {}).items()}
            frames.append({"turn": i, "ships": ships, "planets": planet_owner})

        # Winner = most ships alive in the final frame (Halite II is elimination/dominance).
        last = d["frames"][-1]
        counts = {int(o): len(fleet) for o, fleet in last.get("ships", {}).items()}
        ranked = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
        if not ranked or (len(ranked) > 1 and ranked[0][1] == ranked[1][1]):
            winner, draw = None, True
        else:
            winner, draw = name_for(ranked[0][0]), False

        return ReplayData(
            w=w,
            h=h,
            frames=frames,
            winner=winner,
            draw=draw,
            extra={"planets": static_planets, "colors": colors, "names": names, "maxhp": 255},
        )
