"""Ants replay renderer.

Parses a per-game ``sim_*.json`` written by the engine and renders the toroidal grid
from the spectator's view (no fog): water, food, hills, and every player's ants.

The JSON format (see engine.py ``write_replay``)::

    {"rows":32, "cols":32, "num_players":2, "water":[[r,c], ...],
     "names":["p1","p2"], "winner": 0 | null,
     "frames":[{"t":0, "ants":[[r,c,owner], ...], "hills":[[r,c,owner], ...],
                "food":[[r,c], ...]}, ...]}

Water is static (recorded once). Each frame lists the live ants, living hills, and
food. ``winner`` is the winning player id, or ``null`` for a draw. Grid cells are
``[row, col]`` (row = y, col = x); the board wraps, but the renderer just draws it flat.
"""

from __future__ import annotations

import json

from codeclash.replay.base import ReplayData, ReplayRenderer

DRAW_JS = """
const ARENA = (function(){
  const PAL = ['#e5484d','#4593ff','#46a758','#f5d90a','#8e4ec6','#f76b15','#e93d82','#12a594'];
  const BG = '#0d1117', WATER = '#15304a', FOOD = '#e6edf3', LINE = 'rgba(255,255,255,0.04)';
  let COLS, ROWS, CELL, WATERSET;
  function col(i){ return PAL[i % PAL.length]; }
  function setup(cv, G){
    COLS = G.w; ROWS = G.h;
    CELL = Math.max(8, Math.min(22, Math.floor(640 / COLS)));
    cv.width = COLS * CELL; cv.height = ROWS * CELL;
    WATERSET = G.water || [];
  }
  function draw(ctx, cv, G, i){
    const f = G.frames[i];
    ctx.fillStyle = BG; ctx.fillRect(0, 0, cv.width, cv.height);
    // water
    ctx.fillStyle = WATER;
    WATERSET.forEach(w => ctx.fillRect(w[1]*CELL, w[0]*CELL, CELL, CELL));
    // grid lines
    ctx.strokeStyle = LINE; ctx.lineWidth = 1;
    for(let x=0;x<=COLS;x++){ ctx.beginPath(); ctx.moveTo(x*CELL,0); ctx.lineTo(x*CELL,cv.height); ctx.stroke(); }
    for(let y=0;y<=ROWS;y++){ ctx.beginPath(); ctx.moveTo(0,y*CELL); ctx.lineTo(cv.width,y*CELL); ctx.stroke(); }
    // hills (large bordered square in the owner's color)
    (f.hills||[]).forEach(h => {
      const x = h[1]*CELL, y = h[0]*CELL;
      ctx.fillStyle = col(h[2]); ctx.globalAlpha = 0.35; ctx.fillRect(x, y, CELL, CELL); ctx.globalAlpha = 1;
      ctx.strokeStyle = col(h[2]); ctx.lineWidth = 2; ctx.strokeRect(x+1.5, y+1.5, CELL-3, CELL-3);
    });
    // food (small white diamonds)
    ctx.fillStyle = FOOD;
    (f.food||[]).forEach(fd => {
      const cx = fd[1]*CELL + CELL/2, cy = fd[0]*CELL + CELL/2, s = Math.max(2, CELL*0.22);
      ctx.beginPath(); ctx.moveTo(cx, cy-s); ctx.lineTo(cx+s, cy); ctx.lineTo(cx, cy+s); ctx.lineTo(cx-s, cy); ctx.closePath(); ctx.fill();
    });
    // ants (filled rounded cells in the owner's color)
    (f.ants||[]).forEach(a => {
      ctx.fillStyle = col(a[2]);
      const x = a[1]*CELL, y = a[0]*CELL, p = Math.max(1, CELL*0.12);
      ctx.fillRect(x+p, y+p, CELL-2*p, CELL-2*p);
    });
  }
  function side(G, i){
    const f = G.frames[i], NM = G.names || [], n = G.num_players || NM.length;
    const done = i === G.frames.length - 1;
    const ants = {}, hills = {};
    (f.ants||[]).forEach(a => ants[a[2]] = (ants[a[2]]||0) + 1);
    (f.hills||[]).forEach(h => hills[h[2]] = (hills[h[2]]||0) + 1);
    let rows = '';
    for(let p=0;p<n;p++){
      const dead = (ants[p]||0) === 0 && (hills[p]||0) === 0;
      rows += `<div class="team ${dead?'tdead':''}"><div class="tname">`
        + `<span class="sw" style="background:${col(p)}"></span>${NM[p] || ('player'+(p+1))}</div>`
        + `<div class="stat"><span>ants</span><b>${ants[p]||0}</b></div>`
        + `<div class="stat"><span>hills</span><b>${hills[p]||0}</b></div></div>`;
    }
    const res = done ? (G.draw ? 'DRAW' : (G.winner || '\\u2014')) : '';
    return rows
      + `<div class="stat"><span>turn</span><b>${f.turn} / ${G.max_turns||''}</b></div>`
      + (done ? `<div class="stat"><span>result</span><b>${res}</b></div>` : '');
  }
  return {setup, draw, side};
})();
"""


class AntsReplayer(ReplayRenderer):
    arena = "Ants"
    sim_glob = "sim_*.json"
    DRAW_JS = DRAW_JS

    def parse(self, raw: bytes, players: list[dict] | None = None) -> ReplayData:
        log = json.loads(raw.decode(errors="replace"))
        rows = log.get("rows", 32)
        cols = log.get("cols", 32)
        n = log.get("num_players", 2)

        names = list(log.get("names", []))
        if players:
            names = [p.get("name", names[i] if i < len(names) else f"player{i + 1}") for i, p in enumerate(players)]
        while len(names) < n:
            names.append(f"player{len(names) + 1}")

        frames = [
            {"turn": fr.get("t", idx), "ants": fr.get("ants", []), "hills": fr.get("hills", []), "food": fr.get("food", [])}
            for idx, fr in enumerate(log.get("frames", []))
        ]

        win = log.get("winner")
        draw = win is None
        winner = None if draw else names[win] if isinstance(win, int) and 0 <= win < len(names) else str(win)

        return ReplayData(
            w=cols,
            h=rows,
            frames=frames,
            winner=winner,
            draw=draw,
            extra={
                "names": names,
                "num_players": n,
                "max_turns": log.get("max_turns", 500),
                "water": log.get("water", []),
            },
        )

    def peek_winner(self, raw: bytes, players: list[dict] | None = None) -> tuple[str | None, bool] | None:
        log = json.loads(raw.decode(errors="replace"))
        win = log.get("winner")
        if win is None:
            return (None, True)
        names = list(log.get("names", []))
        if players:
            names = [p.get("name", names[i] if i < len(names) else f"player{i + 1}") for i, p in enumerate(players)]
        name = names[win] if isinstance(win, int) and 0 <= win < len(names) else str(win)
        return (name, False)
