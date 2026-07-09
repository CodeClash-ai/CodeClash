"""LightCycles replay renderer.

Parses a per-game ``sim_*.json`` written by the engine and renders the Tron grid:
each cycle's growing trail plus its bright head, with a side panel of who's alive.

The JSON format (see engine.py ``write_replay``)::

    {"width":40, "height":30, "num_players":2, "names":["p1","p2"],
     "winner": 0 | null,
     "frames":[{"t":0, "heads":[[x,y,alive], ...]}, ...]}

Frames store only each cycle's head (``[x, y, alive]``, ``alive`` is 1/0) per tick;
the trail for a player is the set of every head cell it has occupied so far, which
the renderer rebuilds by accumulating heads up to the frame being shown. ``winner``
is the winning player id, or ``null`` for a draw.
"""

from __future__ import annotations

import json

from codeclash.replay.base import ReplayData, ReplayRenderer

DRAW_JS = """
const ARENA = (function(){
  const PAL = ['#e5484d','#4593ff','#46a758','#f5d90a','#8e4ec6','#f76b15','#e93d82','#12a594'];
  const BG = '#0d1117', GRID_LINE = 'rgba(255,255,255,0.05)', ROCK_COL = '#4b5563';
  let W, H, CELL;
  function col(i){ return PAL[i % PAL.length]; }
  function setup(cv, G){
    W = G.w; H = G.h;
    CELL = Math.max(6, Math.min(20, Math.floor(640 / W)));
    cv.width = W * CELL; cv.height = H * CELL;
  }
  function draw(ctx, cv, G, i){
    ctx.fillStyle = BG; ctx.fillRect(0, 0, cv.width, cv.height);
    // faint grid
    ctx.strokeStyle = GRID_LINE; ctx.lineWidth = 1;
    for(let x=0;x<=W;x++){ ctx.beginPath(); ctx.moveTo(x*CELL,0); ctx.lineTo(x*CELL,cv.height); ctx.stroke(); }
    for(let y=0;y<=H;y++){ ctx.beginPath(); ctx.moveTo(0,y*CELL); ctx.lineTo(cv.width,y*CELL); ctx.stroke(); }
    // static rock obstacles
    ctx.fillStyle = ROCK_COL;
    (G.rocks || []).forEach(r => ctx.fillRect(r[0]*CELL, r[1]*CELL, CELL, CELL));
    const n = (G.frames[0].heads || []).length;
    // rebuild trails by accumulating every head cell up to frame i
    for(let p=0;p<n;p++){
      ctx.fillStyle = col(p); ctx.globalAlpha = 0.55;
      for(let f=0;f<=i;f++){
        const h = G.frames[f].heads[p];
        ctx.fillRect(h[0]*CELL, h[1]*CELL, CELL, CELL);
      }
      ctx.globalAlpha = 1;
    }
    // heads on top (bright, outlined); crashed cycles get an X
    const fr = G.frames[i];
    for(let p=0;p<n;p++){
      const h = fr.heads[p], hx = h[0]*CELL, hy = h[1]*CELL;
      ctx.fillStyle = col(p);
      ctx.fillRect(hx, hy, CELL, CELL);
      ctx.strokeStyle = '#fff'; ctx.lineWidth = 2;
      ctx.strokeRect(hx+1, hy+1, CELL-2, CELL-2);
      if(!h[2]){  // crashed
        ctx.strokeStyle = '#0d1117'; ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(hx+3, hy+3); ctx.lineTo(hx+CELL-3, hy+CELL-3);
        ctx.moveTo(hx+CELL-3, hy+3); ctx.lineTo(hx+3, hy+CELL-3);
        ctx.stroke();
      }
    }
  }
  function side(G, i){
    const fr = G.frames[i], NM = G.names || [], n = fr.heads.length;
    const done = i === G.frames.length - 1;
    let rows = '';
    for(let p=0;p<n;p++){
      const alive = fr.heads[p][2];
      // territory = distinct cells this cycle has occupied through frame i
      const cells = new Set();
      for(let f=0;f<=i;f++){ const h=G.frames[f].heads[p]; cells.add(h[0]+','+h[1]); }
      rows += `<div class="team ${alive?'':'tdead'}"><div class="tname">`
        + `<span class="sw" style="background:${col(p)}"></span>`
        + `${NM[p] || ('player'+(p+1))} ${alive?'':'&#10007;'}</div>`
        + `<div class="stat"><span>trail</span><b>${cells.size}</b></div></div>`;
    }
    const res = done ? (G.draw ? 'DRAW' : (G.winner || '\\u2014')) : '';
    return rows
      + `<div class="stat"><span>tick</span><b>${fr.turn} / ${G.max_ticks||''}</b></div>`
      + (done ? `<div class="stat"><span>result</span><b>${res}</b></div>` : '');
  }
  return {setup, draw, side};
})();
"""


class LightCyclesReplayer(ReplayRenderer):
    arena = "LightCycles"
    sim_glob = "sim_*.json"
    DRAW_JS = DRAW_JS

    def parse(self, raw: bytes, players: list[dict] | None = None) -> ReplayData:
        log = json.loads(raw.decode(errors="replace"))
        w = log.get("width", 40)
        h = log.get("height", 30)
        n = log.get("num_players", 2)

        names = list(log.get("names", []))
        if players:
            names = [p.get("name", names[i] if i < len(names) else f"player{i + 1}") for i, p in enumerate(players)]
        while len(names) < n:
            names.append(f"player{len(names) + 1}")

        frames = [{"turn": fr.get("t", idx), "heads": fr["heads"]} for idx, fr in enumerate(log.get("frames", []))]

        win = log.get("winner")
        draw = win is None
        winner = None if draw else names[win] if isinstance(win, int) and 0 <= win < len(names) else str(win)

        return ReplayData(
            w=w,
            h=h,
            frames=frames,
            winner=winner,
            draw=draw,
            extra={
                "names": names,
                "num_players": n,
                "max_ticks": log.get("max_ticks"),
                "rocks": log.get("rocks", []),
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
