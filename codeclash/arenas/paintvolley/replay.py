"""PaintVolley replay renderer.

Parses a per-game ``sim_*.json`` written by the engine into one frame per recorded
tick and renders the painted tile grid, the flying balls, and the helmet characters
patrolling the bottom, with a live scoreboard.

The JSON format (see engine.py ``write_replay``)::

    {"cols":32, "rows":24, "num_players":2, "max_ticks":1500,
     "names":["p1","p2"], "winner": 0 | null, "final_scores": {"0":399,"1":255},
     "frames":[{"tick":0, "grid":["...01.",...], "balls":[{"x","y","c"}],
                "players":[{"x","y","id"}], "scores":{"0":n,"1":m}}, ...]}

Each frame's ``grid`` is one string per row; each char is the tile owner encoded in
base36 (``'0'``..), or ``'.'`` for a neutral (unpainted) tile. Ball/player ``color``
values are player ids (0-based) or ``-1`` for an unclaimed ball. ``winner`` is the
winning player id, or ``null`` for a draw.
"""

from __future__ import annotations

import json

from codeclash.replay.base import ReplayData, ReplayRenderer

DRAW_JS = """
const ARENA = (function(){
  // Visual constants mirror the engine (BALL_RADIUS, PLAYER_HALF_WIDTH, PLAYER_HEIGHT).
  const CELL = 18, BALL_R = 0.6, BODY_HW = 0.9, PH = 2.5;
  // Player palette (index by player id); neutral tiles use the dark background.
  const PAL = ['#e5484d','#4593ff','#46a758','#f5d90a','#8e4ec6','#f76b15','#e93d82','#12a594'];
  const NEUTRAL = '#161b22';
  let COLS, ROWS;
  function col(c){ return c < 0 ? NEUTRAL : PAL[c % PAL.length]; }
  function setup(cv, G){
    COLS = G.w; ROWS = G.h;
    cv.width = COLS * CELL; cv.height = ROWS * CELL;
  }
  function draw(ctx, cv, G, i){
    const f = G.frames[i];
    // background
    ctx.fillStyle = NEUTRAL; ctx.fillRect(0, 0, cv.width, cv.height);
    // painted tiles (each row is a string; '.' = neutral, else base36 owner id)
    for(let r=0;r<ROWS;r++){
      const row = f.grid[r];
      for(let c=0;c<COLS;c++){
        const ch = row[c];
        if(ch !== '.'){ ctx.fillStyle = col(parseInt(ch, 36)); ctx.fillRect(c*CELL, r*CELL, CELL, CELL); }
      }
    }
    // faint grid lines
    ctx.strokeStyle = 'rgba(255,255,255,0.05)'; ctx.lineWidth = 1;
    for(let c=0;c<=COLS;c++){ ctx.beginPath(); ctx.moveTo(c*CELL,0); ctx.lineTo(c*CELL,cv.height); ctx.stroke(); }
    for(let r=0;r<=ROWS;r++){ ctx.beginPath(); ctx.moveTo(0,r*CELL); ctx.lineTo(cv.width,r*CELL); ctx.stroke(); }
    // players — each a distinct fixed-size character (helmet head + body) whose feet
    // rest at helmet_y + PH. When it jumps, helmet_y decreases so the whole figure
    // lifts off the floor (a gap opens under its feet) instead of stretching. A shadow
    // on the floor shrinks with height to sell the jump.
    const FLOOR = ROWS*CELL;
    (f.players||[]).forEach(p=>{
      const px = p.x*CELL, py = p.y*CELL, bw = BODY_HW*2*CELL, cc = col(p.id);
      const feet = py + PH*CELL;                 // fixed offset below the helmet
      const lift = Math.max(0, FLOOR - feet);    // how far off the floor (px)
      // floor shadow (shrinks as the character rises)
      const sw = (bw/2) * (1 - Math.min(0.6, lift/(6*CELL)));
      ctx.fillStyle = 'rgba(0,0,0,0.28)';
      ctx.beginPath(); ctx.ellipse(px, FLOOR-3, Math.max(3, sw), 3.5, 0, 0, 7); ctx.fill();
      // body (fixed height, from just under the head down to the feet)
      const hr = bw/2, hcy = py + hr*0.85;
      ctx.strokeStyle = 'rgba(0,0,0,0.55)'; ctx.lineWidth = 2; ctx.fillStyle = cc;
      ctx.beginPath(); ctx.roundRect(px-bw/2, hcy, bw, Math.max(6, feet-hcy), Math.min(7, bw/2)); ctx.fill(); ctx.stroke();
      // head + helmet rim
      ctx.beginPath(); ctx.arc(px, hcy, hr, 0, 7); ctx.fillStyle = cc; ctx.fill(); ctx.stroke();
      ctx.strokeStyle = 'rgba(0,0,0,0.3)'; ctx.lineWidth = 3;
      ctx.beginPath(); ctx.arc(px, hcy, hr, Math.PI, 2*Math.PI); ctx.stroke();
      // eyes
      ctx.fillStyle = '#fff';
      ctx.beginPath(); ctx.arc(px-hr*0.33, hcy+2, 2.4, 0, 7); ctx.arc(px+hr*0.33, hcy+2, 2.4, 0, 7); ctx.fill();
      ctx.fillStyle = '#111';
      ctx.beginPath(); ctx.arc(px-hr*0.33, hcy+2, 1.1, 0, 7); ctx.arc(px+hr*0.33, hcy+2, 1.1, 0, 7); ctx.fill();
    });
    // balls — glow ring + body + highlight so the color (and who owns it) reads clearly
    (f.balls||[]).forEach(b=>{
      const bx = b.x*CELL, by = b.y*CELL, br = BALL_R*CELL, cc = b.c < 0 ? '#c9d1d9' : col(b.c);
      ctx.globalAlpha = 0.25; ctx.fillStyle = cc;
      ctx.beginPath(); ctx.arc(bx, by, br+3, 0, 7); ctx.fill();
      ctx.globalAlpha = 1;
      ctx.beginPath(); ctx.arc(bx, by, br, 0, 7); ctx.fillStyle = cc; ctx.fill();
      ctx.strokeStyle = '#0d1117'; ctx.lineWidth = 2; ctx.stroke();
      ctx.beginPath(); ctx.arc(bx-br*0.3, by-br*0.3, br*0.35, 0, 7); ctx.fillStyle = 'rgba(255,255,255,0.75)'; ctx.fill();
    });
  }
  function side(G, i){
    const f = G.frames[i], NM = G.names || [], total = COLS*ROWS;
    const done = i === G.frames.length - 1;
    let rows = '';
    const n = G.num_players || NM.length;
    for(let p=0;p<n;p++){
      const s = (f.scores && (f.scores[p] != null ? f.scores[p] : f.scores[String(p)])) || 0;
      const pct = total ? (100*s/total).toFixed(1) : '0.0';
      rows += `<div class="team"><div class="tname">`
        + `<span class="sw" style="background:${col(p)}"></span>`
        + `${NM[p] || ('player'+(p+1))}</div>`
        + `<div class="stat"><span>tiles</span><b>${s}</b></div>`
        + `<div class="stat"><span>share</span><b>${pct}%</b></div></div>`;
    }
    const res = done ? (G.draw ? 'TIE' : (G.winner || '\\u2014')) : '';
    return rows
      + `<div class="stat"><span>tick</span><b>${f.turn} / ${G.max_ticks||''}</b></div>`
      + (done ? `<div class="stat"><span>result</span><b>${res}</b></div>` : '');
  }
  return {setup, draw, side};
})();
"""


class PaintVolleyReplayer(ReplayRenderer):
    arena = "PaintVolley"
    sim_glob = "sim_*.json"
    DRAW_JS = DRAW_JS

    def peek_winner(self, raw: bytes, players: list[dict] | None = None) -> tuple[str | None, bool] | None:
        """Cheap per-sim winner for the index (reads the top-level ``winner`` without
        touching the frames). ``winner`` is a 0-based player id, or null for a draw."""
        log = json.loads(raw.decode(errors="replace"))
        win = log.get("winner")
        if win is None:
            return (None, True)
        names = list(log.get("names", []))
        if players:
            names = [p.get("name", names[i] if i < len(names) else f"player{i + 1}") for i, p in enumerate(players)]
        name = names[win] if isinstance(win, int) and 0 <= win < len(names) else str(win)
        return (name, False)

    def parse(self, raw: bytes, players: list[dict] | None = None) -> ReplayData:
        log = json.loads(raw.decode(errors="replace"))
        cols = log.get("cols", 32)
        rows = log.get("rows", 24)
        n = log.get("num_players", 2)

        # Prefer the tournament's real player names; fall back to what the engine recorded.
        names = list(log.get("names", []))
        if players:
            names = [p.get("name", names[i] if i < len(names) else f"player{i + 1}") for i, p in enumerate(players)]
        while len(names) < n:
            names.append(f"player{len(names) + 1}")

        frames = [
            {
                "turn": fr.get("tick", idx),
                "grid": fr["grid"],
                "balls": fr.get("balls", []),
                "players": fr.get("players", []),
                "scores": fr.get("scores", {}),
            }
            for idx, fr in enumerate(log.get("frames", []))
        ]

        win = log.get("winner")
        draw = win is None
        winner = None if draw else names[win] if 0 <= win < len(names) else str(win)

        return ReplayData(
            w=cols,
            h=rows,
            frames=frames,
            winner=winner,
            draw=draw,
            extra={"names": names, "num_players": n, "max_ticks": log.get("max_ticks")},
        )
