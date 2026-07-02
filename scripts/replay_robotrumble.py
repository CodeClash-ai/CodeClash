#!/usr/bin/env python3
"""Standalone RobotRumble replayer/visualizer.

Turns a recorded sim_*.json (from a CodeClash RobotRumble game, produced with
`rumblebot run term --raw`) into a self-contained HTML file you can open in any
browser — animated grid, play/pause/step, per-team unit counts + health, move/
attack indicators, and the winner. No server, no internet, no dependencies.

Usage:
    python scripts/replay_robotrumble.py path/to/sim.json                 # writes sim.html
    python scripts/replay_robotrumble.py sim.json -o out.html
    python scripts/replay_robotrumble.py sim.json --ascii                 # quick terminal dump
    python scripts/replay_robotrumble.py sim.json --blue-name luisa --red-name flail

The raw JSON format: a single object {winner, errors, turns:[...]}. Each turn has
`state.objs` (a dict of grid objects — Terrain/Wall and Unit/Soldier, each with
`coords` [x,y], `team`, `health`), a `state.turn` index, and `robot_actions`
(unit id -> {"Ok": {"type":"Move"|"Attack","direction":...}} or {"Ok":"None"}).
Blue is the first (blue) bot, Red is the second.
"""
import argparse
import json
import sys
from pathlib import Path

MAX_HEALTH = 5
TEAM_COLORS = {"Blue": "#3B78FF", "Red": "#E5484D"}


def load(path, blue_name=None, red_name=None):
    data = json.loads(Path(path).read_text())
    turns_raw = data.get("turns", [])

    # Walls (terrain) are static across the game — grab them from the first frame.
    walls = []
    max_x = max_y = 0
    if turns_raw:
        for o in turns_raw[0]["state"]["objs"].values():
            x, y = o["coords"]
            max_x, max_y = max(max_x, x), max(max_y, y)
            if o["obj_type"] == "Terrain":
                walls.append([x, y])

    frames = []
    for t in turns_raw:
        objs = t["state"]["objs"]
        actions = t.get("robot_actions") or {}
        units = []
        for oid, o in objs.items():
            if o["obj_type"] != "Unit":
                continue
            act = actions.get(oid)
            atype, adir = None, None
            if isinstance(act, dict) and "Ok" in act:
                ok = act["Ok"]
                if isinstance(ok, dict):
                    atype, adir = ok.get("type"), ok.get("direction")
            units.append({
                "team": o.get("team"),
                "hp": o.get("health", 0),
                "x": o["coords"][0],
                "y": o["coords"][1],
                "act": atype,
                "dir": adir,
            })
        frames.append({"turn": t["state"].get("turn"), "units": units})

    winner_raw = data.get("winner")
    names = {"Blue": blue_name or "Blue", "Red": red_name or "Red"}
    if winner_raw in ("Blue", "Red"):
        winner, draw = names[winner_raw], False
    else:
        winner, draw = None, True

    return {
        "w": max_x + 1,
        "h": max_y + 1,
        "walls": walls,
        "frames": frames,
        "names": names,
        "colors": TEAM_COLORS,
        "winner": winner,
        "draw": draw,
        "errors": data.get("errors", {}),
    }


def to_ascii(g):
    W, H = g["w"], g["h"]
    wall_set = {(x, y) for x, y in g["walls"]}
    for f in g["frames"]:
        grid = [["#" if (x, y) in wall_set else "." for x in range(W)] for y in range(H)]
        for u in f["units"]:
            grid[u["y"]][u["x"]] = "B" if u["team"] == "Blue" else "R"
        counts = {"Blue": 0, "Red": 0}
        hp = {"Blue": 0, "Red": 0}
        for u in f["units"]:
            counts[u["team"]] += 1
            hp[u["team"]] += u["hp"]
        print(f"\n--- turn {f['turn']} ---  "
              f"{g['names']['Blue']}(B): {counts['Blue']} units / {hp['Blue']} hp   "
              f"{g['names']['Red']}(R): {counts['Red']} units / {hp['Red']} hp")
        for row in grid:
            print(" ".join(row))
    print(f"\nWinner: {'TIE' if g['draw'] else g['winner']}")


HTML = """<!doctype html><html><head><meta charset="utf-8"><title>RobotRumble replay</title>
<style>
 body{{background:#0d1117;color:#e6edf3;font:14px system-ui,sans-serif;margin:0;padding:16px;display:flex;gap:20px;flex-wrap:wrap}}
 canvas{{background:#161b22;border-radius:8px}}
 #side{{min-width:260px}} .row{{margin:8px 0}} button{{background:#21262d;color:#e6edf3;border:1px solid #30363d;border-radius:6px;padding:6px 10px;cursor:pointer;font-size:14px}}
 button:hover{{background:#30363d}} h2{{margin:0 0 4px;font-size:15px}}
 .team{{margin:12px 0;padding:10px;background:#161b22;border-radius:8px}}
 .tname{{display:flex;align-items:center;gap:8px;font-weight:700}} .sw{{width:14px;height:14px;border-radius:3px}}
 .stat{{display:flex;justify-content:space-between;margin:6px 0;font-variant-numeric:tabular-nums}}
 .hb{{height:8px;background:#30363d;border-radius:4px;overflow:hidden;margin-top:4px}} .hf{{height:100%;transition:width .12s}}
 .dead{{opacity:.45}} #winner{{font-weight:700;font-size:16px;margin-top:14px}} .muted{{color:#8b949e}}
</style></head><body>
<canvas id="c"></canvas>
<div id="side">
 <h2>RobotRumble replay</h2>
 <div class="row muted"><b>Turn <span id="t">0</span></b> / {maxturn}</div>
 <div class="row">
  <button id="first">⏮</button><button id="prev">◀</button>
  <button id="play">▶ play</button><button id="next">▶</button><button id="last">⏭</button>
 </div>
 <div class="row">speed <input id="speed" type="range" min="1" max="30" value="8"></div>
 <input id="scrub" type="range" min="0" max="{maxturn}" value="0" style="width:100%">
 <div id="teams"></div>
 <div id="winner"></div>
 <div class="row muted" style="font-size:12px">■ move arrow · ✦ attacking · health = brightness</div>
</div>
<script>
const G = {data};
const W=G.w, H=G.h, F=G.frames, COL=G.colors, NAMES=G.names, MAXHP={maxhp};
const WALLS=G.walls;
const cv=document.getElementById('c'), ctx=cv.getContext('2d');
const CELL=Math.max(16, Math.min(40, Math.floor(640/Math.max(W,H)))), PAD=CELL*0.14;
cv.width=W*CELL; cv.height=H*CELL;
let i=0, playing=false, timer=null;
const px=(x)=>x*CELL, py=(y)=>y*CELL;   // RobotRumble: y=0 at top, render straight down
const DIRV={{North:[0,-1],South:[0,1],East:[1,0],West:[-1,0]}};
const wallSet=new Set(WALLS.map(([x,y])=>x+','+y));
function draw(){{
  const f=F[i];
  ctx.clearRect(0,0,cv.width,cv.height);
  // grid lines
  ctx.strokeStyle='#21262d'; ctx.lineWidth=1;
  for(let x=0;x<=W;x++){{ctx.beginPath();ctx.moveTo(x*CELL,0);ctx.lineTo(x*CELL,H*CELL);ctx.stroke();}}
  for(let y=0;y<=H;y++){{ctx.beginPath();ctx.moveTo(0,y*CELL);ctx.lineTo(W*CELL,y*CELL);ctx.stroke();}}
  // walls / terrain
  ctx.fillStyle='#2d333b';
  WALLS.forEach(([x,y])=>{{ctx.fillRect(px(x)+1,py(y)+1,CELL-2,CELL-2);}});
  // units
  f.units.forEach(u=>{{
    const base=COL[u.team]||'#888';
    // health -> opacity (full hp brightest)
    const frac=Math.max(0.28, u.hp/MAXHP);
    ctx.globalAlpha=frac;
    ctx.fillStyle=base;
    const r=CELL*0.28;
    ctx.beginPath(); ctx.roundRect(px(u.x)+PAD,py(u.y)+PAD,CELL-2*PAD,CELL-2*PAD,r); ctx.fill();
    ctx.globalAlpha=1;
    const cx=px(u.x)+CELL/2, cy=py(u.y)+CELL/2;
    // attack indicator: bright ring + directional spark
    if(u.act==='Attack'){{
      ctx.strokeStyle='#ffd21f'; ctx.lineWidth=2;
      ctx.beginPath(); ctx.arc(cx,cy,CELL*0.42,0,7); ctx.stroke();
      const d=DIRV[u.dir]; if(d){{
        ctx.fillStyle='#ffd21f';
        ctx.beginPath();
        ctx.arc(cx+d[0]*CELL*0.5, cy+d[1]*CELL*0.5, CELL*0.12,0,7); ctx.fill();
      }}
    }}
    // move indicator: small arrow toward move direction
    if(u.act==='Move'){{
      const d=DIRV[u.dir];
      if(d){{
        ctx.strokeStyle='rgba(255,255,255,0.85)'; ctx.lineWidth=2;
        ctx.beginPath();
        ctx.moveTo(cx,cy); ctx.lineTo(cx+d[0]*CELL*0.28, cy+d[1]*CELL*0.28); ctx.stroke();
      }}
    }}
    // health pips (tiny bar under the unit)
    const bw=CELL-2*PAD, bx=px(u.x)+PAD, by=py(u.y)+CELL-PAD*0.5;
    ctx.fillStyle='rgba(0,0,0,0.45)'; ctx.fillRect(bx,by-3,bw,3);
    ctx.fillStyle='#eafff0'; ctx.fillRect(bx,by-3,bw*(u.hp/MAXHP),3);
  }});
  document.getElementById('t').textContent=f.turn;
  document.getElementById('scrub').value=i;
  // side panel: per-team unit count + total health
  const agg={{Blue:{{n:0,hp:0}},Red:{{n:0,hp:0}}}};
  f.units.forEach(u=>{{ if(agg[u.team]){{ agg[u.team].n++; agg[u.team].hp+=u.hp; }} }});
  document.getElementById('teams').innerHTML=['Blue','Red'].map(tm=>{{
    const a=agg[tm], dead=a.n===0, maxhp=8*MAXHP;
    return `<div class="team ${{dead?'dead':''}}">
      <div class="tname"><span class="sw" style="background:${{COL[tm]}}"></span>${{NAMES[tm]}} <span class="muted">(${{tm}})</span></div>
      <div class="stat"><span>units</span><b>${{a.n}}</b></div>
      <div class="stat"><span>total health</span><b>${{a.hp}}</b></div>
      <div class="hb"><span class="hf" style="width:${{Math.min(100,100*a.hp/maxhp)}}%;background:${{COL[tm]}}"></span></div>
    </div>`;
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
document.addEventListener('keydown',(e)=>{{
  if(e.key==='ArrowRight')go(i+1); else if(e.key==='ArrowLeft')go(i-1);
  else if(e.key===' '){{e.preventDefault();play();}}
}});
if(!CanvasRenderingContext2D.prototype.roundRect){{CanvasRenderingContext2D.prototype.roundRect=function(x,y,w,h,r){{this.beginPath();this.moveTo(x+r,y);this.arcTo(x+w,y,x+w,y+h,r);this.arcTo(x+w,y+h,x,y+h,r);this.arcTo(x,y+h,x,y,r);this.arcTo(x,y,x+w,y,r);this.closePath();return this;}};}}
draw();
</script></body></html>"""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("json", help="Path to a raw RobotRumble sim JSON (rumblebot run term --raw)")
    ap.add_argument("-o", "--out")
    ap.add_argument("--ascii", action="store_true", help="Dump frames to the terminal instead of HTML")
    ap.add_argument("--blue-name", help="Display name for the Blue (first) bot")
    ap.add_argument("--red-name", help="Display name for the Red (second) bot")
    a = ap.parse_args()

    g = load(a.json, a.blue_name, a.red_name)
    if not g["frames"]:
        print("No turn frames found in that file.", file=sys.stderr)
        sys.exit(1)
    if a.ascii:
        to_ascii(g)
        return
    out = a.out or str(Path(a.json).with_suffix(".html"))
    html = HTML.format(data=json.dumps(g), maxturn=len(g["frames"]) - 1, maxhp=MAX_HEALTH)
    Path(out).write_text(html)
    print(f"Wrote {out}  ({len(g['frames'])} turns, winner={'TIE' if g['draw'] else g['winner']})")
    print(f"Open it in a browser:  open {out}")


if __name__ == "__main__":
    main()
