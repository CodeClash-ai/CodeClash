#!/usr/bin/env python3
"""Standalone BattleSnake replayer/visualizer.

Turns a recorded sim_*.jsonl (from a CodeClash BattleSnake game) into a self-contained
HTML file you can open in any browser — animated board, play/pause/step, per-snake health,
and the winner. No server, no internet, no dependencies.

Usage:
    python scripts/replay_battlesnake.py path/to/sim_18.jsonl            # writes sim_18.html
    python scripts/replay_battlesnake.py sim_18.jsonl -o out.html
    python scripts/replay_battlesnake.py sim_18.jsonl --ascii           # quick terminal dump

The jsonl format: one metadata line, per-turn v1 state frames ({game,turn,board,you}),
and a final result line ({winnerName,isDraw}).
"""

import argparse
import json
import sys
from pathlib import Path

PALETTE = ["#3B78FF", "#E5484D", "#30A46C", "#F5A623", "#8E4EC6", "#12A594", "#E93D82", "#F76B15"]


def load(path):
    rows = [json.loads(l) for l in Path(path).read_text().splitlines() if l.strip()]
    # per-turn board states (dedupe: keep the last frame seen for each turn)
    by_turn = {}
    for r in rows:
        if isinstance(r, dict) and "board" in r and "turn" in r:
            by_turn[r["turn"]] = r["board"]
    turns = sorted(by_turn)
    result = next((r for r in reversed(rows) if isinstance(r, dict) and "winnerName" in r), {})

    # stable color per snake name (use the snake's own color if the log has it)
    names, colors = [], {}
    for t in turns:
        for s in by_turn[t]["board"]["snakes"] if "board" in by_turn[t] else by_turn[t]["snakes"]:
            if s["name"] not in names:
                names.append(s["name"])
    for i, nm in enumerate(names):
        colors[nm] = PALETTE[i % len(PALETTE)]
    for t in turns:  # prefer explicit color from the log if present
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
    return {
        "w": b0["width"],
        "h": b0["height"],
        "frames": frames,
        "colors": colors,
        "winner": result.get("winnerName"),
        "draw": result.get("isDraw", False),
    }


def to_ascii(g):
    for f in g["frames"]:
        grid = [["." for _ in range(g["w"])] for _ in range(g["h"])]
        for fx, fy in f["food"]:
            grid[fy][fx] = "*"
        for s in f["snakes"]:
            ch = s["name"][0].upper()
            for j, (x, y) in enumerate(s["body"]):
                grid[y][x] = ch if j else ch.lower()  # head lowercase-ish marker
        print(f"\n--- turn {f['turn']} ---  " + "  ".join(f"{s['name']}:{s['health']}" for s in f["snakes"]))
        for row in reversed(grid):  # y-up: print top row last
            print(" ".join(row))
    print(f"\nWinner: {'TIE' if g['draw'] else g['winner']}")


HTML = """<!doctype html><html><head><meta charset="utf-8"><title>BattleSnake replay</title>
<style>
 body{{background:#0d1117;color:#e6edf3;font:14px system-ui,sans-serif;margin:0;padding:16px;display:flex;gap:20px}}
 canvas{{background:#161b22;border-radius:8px}}
 #side{{min-width:220px}} .row{{margin:8px 0}} button{{background:#21262d;color:#e6edf3;border:1px solid #30363d;border-radius:6px;padding:6px 10px;cursor:pointer;font-size:14px}}
 button:hover{{background:#30363d}} .sn{{display:flex;align-items:center;gap:8px;margin:6px 0}} .sw{{width:14px;height:14px;border-radius:3px}}
 .hb{{height:8px;background:#30363d;border-radius:4px;flex:1;overflow:hidden}} .hf{{height:100%}} .dead{{opacity:.4;text-decoration:line-through}}
 #winner{{font-weight:700;font-size:16px;margin-top:12px}}
</style></head><body>
<canvas id="c"></canvas>
<div id="side">
 <div class="row"><b>Turn <span id="t">0</span></b> / {maxturn}</div>
 <div class="row">
  <button id="first">⏮</button><button id="prev">◀</button>
  <button id="play">▶ play</button><button id="next">▶</button><button id="last">⏭</button>
 </div>
 <div class="row">speed <input id="speed" type="range" min="1" max="30" value="8"></div>
 <input id="scrub" type="range" min="0" max="{maxturn}" value="0" style="width:100%">
 <div id="snakes"></div>
 <div id="winner"></div>
</div>
<script>
const G = {data};
const W=G.w, H=G.h, F=G.frames, COL=G.colors;
const cv=document.getElementById('c'), ctx=cv.getContext('2d');
const CELL=Math.max(18, Math.min(44, Math.floor(560/Math.max(W,H)))), PAD=CELL*0.12;
cv.width=W*CELL; cv.height=H*CELL;
let i=0, playing=false, timer=null;
const px=(x)=>x*CELL, py=(y)=>(H-1-y)*CELL;  // v1 y-up -> canvas y-down
function draw(){{
  const f=F[i];
  ctx.clearRect(0,0,cv.width,cv.height);
  // grid
  ctx.strokeStyle='#21262d';
  for(let x=0;x<=W;x++){{ctx.beginPath();ctx.moveTo(x*CELL,0);ctx.lineTo(x*CELL,H*CELL);ctx.stroke();}}
  for(let y=0;y<=H;y++){{ctx.beginPath();ctx.moveTo(0,y*CELL);ctx.lineTo(W*CELL,y*CELL);ctx.stroke();}}
  f.hazards.forEach(([x,y])=>{{ctx.fillStyle='rgba(245,166,35,0.15)';ctx.fillRect(px(x),py(y),CELL,CELL);}});
  f.food.forEach(([x,y])=>{{ctx.fillStyle='#ff5252';ctx.beginPath();ctx.arc(px(x)+CELL/2,py(y)+CELL/2,CELL*0.22,0,7);ctx.fill();}});
  f.snakes.forEach(s=>{{
    const c=COL[s.name]||'#888';
    s.body.forEach(([x,y],j)=>{{
      ctx.fillStyle=c; ctx.globalAlpha=j===0?1:0.85;
      const r=j===0?CELL*0.5:CELL*0.32;
      ctx.beginPath(); ctx.roundRect(px(x)+PAD,py(y)+PAD,CELL-2*PAD,CELL-2*PAD, r); ctx.fill();
    }});
    ctx.globalAlpha=1;
    // eye on head
    const [hx,hy]=s.body[0]; ctx.fillStyle='#0d1117';
    ctx.beginPath();ctx.arc(px(hx)+CELL*0.62,py(hy)+CELL*0.38,CELL*0.08,0,7);ctx.fill();
  }});
  document.getElementById('t').textContent=f.turn;
  document.getElementById('scrub').value=i;
  // side panel: health + alive/dead
  const alive=new Set(f.snakes.map(s=>s.name));
  document.getElementById('snakes').innerHTML=Object.keys(COL).map(nm=>{{
    const s=f.snakes.find(x=>x.name===nm); const hp=s?s.health:0; const dead=!alive.has(nm);
    return `<div class="sn ${{dead?'dead':''}}"><span class="sw" style="background:${{COL[nm]}}"></span>
      <span style="min-width:80px">${{nm}}</span>
      <span class="hb"><span class="hf" style="width:${{hp}}%;background:${{COL[nm]}}"></span></span>
      <span>${{dead?'☠':hp}}</span></div>`;
  }}).join('');
  document.getElementById('winner').textContent = (i===F.length-1)?('Winner: '+(G.draw?'TIE':G.winner)) : '';
}}
function go(n){{ i=Math.max(0,Math.min(F.length-1,n)); draw(); }}
function play(){{ playing=!playing; document.getElementById('play').textContent=playing?'⏸ pause':'▶ play';
  if(playing){{ timer=setInterval(()=>{{ if(i>=F.length-1){{play();return;}} go(i+1); }}, 1000/ +document.getElementById('speed').value); }}
  else clearInterval(timer); }}
document.getElementById('play').onclick=play;
document.getElementById('next').onclick=()=>go(i+1);
document.getElementById('prev').onclick=()=>go(i-1);
document.getElementById('first').onclick=()=>go(0);
document.getElementById('last').onclick=()=>go(F.length-1);
document.getElementById('scrub').oninput=(e)=>go(+e.target.value);
document.getElementById('speed').oninput=()=>{{ if(playing){{play();play();}} }};
if(!CanvasRenderingContext2D.prototype.roundRect){{CanvasRenderingContext2D.prototype.roundRect=function(x,y,w,h,r){{this.beginPath();this.moveTo(x+r,y);this.arcTo(x+w,y,x+w,y+h,r);this.arcTo(x+w,y+h,x,y+h,r);this.arcTo(x,y+h,x,y,r);this.arcTo(x,y,x+w,y,r);this.closePath();return this;}};}}
draw();
</script></body></html>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("jsonl")
    ap.add_argument("-o", "--out")
    ap.add_argument("--ascii", action="store_true")
    a = ap.parse_args()
    g = load(a.jsonl)
    if not g["frames"]:
        print("No state frames found in that file.", file=sys.stderr)
        sys.exit(1)
    if a.ascii:
        to_ascii(g)
        return
    out = a.out or str(Path(a.jsonl).with_suffix(".html"))
    html = HTML.format(data=json.dumps(g), maxturn=len(g["frames"]) - 1)
    Path(out).write_text(html)
    print(f"Wrote {out}  ({len(g['frames'])} turns, winner={'TIE' if g['draw'] else g['winner']})")
    print(f"Open it in a browser:  open {out}")


if __name__ == "__main__":
    main()
