"""BattleSnake replay renderer.

Parses a recorded ``sim_*.jsonl`` (v1 API state frames) into normalized playback data
and draws the board — snakes with heads/eyes, food, hazards, per-snake health.
Ported from the former ``scripts/replay_battlesnake.py``.

The jsonl format: per-turn v1 state frames ({game, turn, board, you}) and a final result
line ({winnerName, isDraw}).
"""

from __future__ import annotations

import json

from codeclash.replay.base import ReplayData, ReplayRenderer

PALETTE = ["#3B78FF", "#E5484D", "#30A46C", "#F5A623", "#8E4EC6", "#12A594", "#E93D82", "#F76B15"]

DRAW_JS = """
const ARENA = (function(){
  let W, H, CELL, PAD, px, py;
  function setup(cv, G){
    W = G.w; H = G.h;
    CELL = Math.max(18, Math.min(44, Math.floor(560 / Math.max(W, H)))); PAD = CELL * 0.12;
    cv.width = W * CELL; cv.height = H * CELL;
    px = (x) => x * CELL; py = (y) => (H - 1 - y) * CELL;  // v1 y-up -> canvas y-down
  }
  function draw(ctx, cv, G, i){
    const f = G.frames[i], COL = G.colors;
    ctx.clearRect(0, 0, cv.width, cv.height);
    ctx.strokeStyle = '#21262d';
    for(let x=0;x<=W;x++){ctx.beginPath();ctx.moveTo(x*CELL,0);ctx.lineTo(x*CELL,H*CELL);ctx.stroke();}
    for(let y=0;y<=H;y++){ctx.beginPath();ctx.moveTo(0,y*CELL);ctx.lineTo(W*CELL,y*CELL);ctx.stroke();}
    f.hazards.forEach(([x,y])=>{ctx.fillStyle='rgba(245,166,35,0.15)';ctx.fillRect(px(x),py(y),CELL,CELL);});
    f.food.forEach(([x,y])=>{ctx.fillStyle='#ff5252';ctx.beginPath();ctx.arc(px(x)+CELL/2,py(y)+CELL/2,CELL*0.22,0,7);ctx.fill();});
    f.snakes.forEach(s=>{
      const c = COL[s.name] || '#888';
      s.body.forEach(([x,y],j)=>{
        ctx.fillStyle=c; ctx.globalAlpha=j===0?1:0.85;
        const r=j===0?CELL*0.5:CELL*0.32;
        ctx.beginPath(); ctx.roundRect(px(x)+PAD,py(y)+PAD,CELL-2*PAD,CELL-2*PAD, r); ctx.fill();
      });
      ctx.globalAlpha=1;
      const [hx,hy]=s.body[0]; ctx.fillStyle='#0d1117';
      ctx.beginPath();ctx.arc(px(hx)+CELL*0.62,py(hy)+CELL*0.38,CELL*0.08,0,7);ctx.fill();
    });
  }
  function side(G, i){
    const f = G.frames[i], COL = G.colors;
    const alive = new Set(f.snakes.map(s=>s.name));
    return Object.keys(COL).map(nm=>{
      const s = f.snakes.find(x=>x.name===nm); const hp = s?s.health:0; const dead = !alive.has(nm);
      return `<div class="sn ${dead?'dead':''}"><span class="sw" style="background:${COL[nm]}"></span>
        <span style="min-width:80px">${nm}</span>
        <span class="hb"><span class="hf" style="width:${hp}%;background:${COL[nm]}"></span></span>
        <span>${dead?'\\u2620':hp}</span></div>`;
    }).join('');
  }
  return {setup, draw, side};
})();
"""


class BattleSnakeReplayer(ReplayRenderer):
    arena = "BattleSnake"
    sim_glob = "sim_*.jsonl"
    DRAW_JS = DRAW_JS

    def parse(self, raw: bytes, players=None) -> ReplayData:
        rows = [json.loads(line) for line in raw.decode().splitlines() if line.strip()]
        # per-turn board states (dedupe: keep the last frame seen for each turn)
        by_turn = {}
        for r in rows:
            if isinstance(r, dict) and "board" in r and "turn" in r:
                by_turn[r["turn"]] = r["board"]
        turns = sorted(by_turn)
        result = next((r for r in reversed(rows) if isinstance(r, dict) and "winnerName" in r), {})
        if not turns:
            return ReplayData(w=0, h=0, frames=[], winner=result.get("winnerName"), draw=result.get("isDraw", False))

        # stable color per snake name (prefer the snake's own color from the log if present)
        names, colors = [], {}
        for t in turns:
            for s in by_turn[t]["snakes"]:
                if s["name"] not in names:
                    names.append(s["name"])
        for i, nm in enumerate(names):
            colors[nm] = PALETTE[i % len(PALETTE)]
        for t in turns:
            for s in by_turn[t]["snakes"]:
                if s.get("color"):
                    colors[s["name"]] = s["color"]

        b0 = by_turn[turns[0]]
        frames = []
        for t in turns:
            b = by_turn[t]
            frames.append(
                {
                    "turn": t,
                    "food": [[c["x"], c["y"]] for c in b.get("food", [])],
                    "hazards": [[c["x"], c["y"]] for c in b.get("hazards", [])],
                    "snakes": [
                        {
                            "name": s["name"],
                            "health": s.get("health", 0),
                            "body": [[c["x"], c["y"]] for c in s["body"]],
                        }
                        for s in b["snakes"]
                    ],
                }
            )
        return ReplayData(
            w=b0["width"],
            h=b0["height"],
            frames=frames,
            winner=result.get("winnerName"),
            draw=result.get("isDraw", False),
            extra={"colors": colors},
        )
