"""RobotRumble replay renderer.

Parses a raw RobotRumble sim JSON (``rumblebot run term --raw``) into normalized playback
data and draws the grid — terrain/walls, units colored by team with health-as-brightness,
move/attack indicators, per-team unit + health totals. Ported from the former
``scripts/replay_robotrumble.py``.

The raw JSON: a single object {winner, errors, turns:[...]}. Each turn has ``state.objs``
(grid objects: Terrain/Wall and Unit/Soldier, each with ``coords`` [x,y], ``team``,
``health``), a ``state.turn`` index, and ``robot_actions`` (unit id ->
{"Ok": {"type": "Move"|"Attack", "direction": ...}} or {"Ok": "None"}). Blue is the first
(blue) bot, Red is the second.
"""

from __future__ import annotations

import json

from codeclash.replay.base import ReplayData, ReplayRenderer

MAX_HEALTH = 5
TEAM_COLORS = {"Blue": "#3B78FF", "Red": "#E5484D"}

DRAW_JS = """
const ARENA = (function(){
  let W, H, CELL, PAD, COL, NAMES, MAXHP, WALLS, px, py;
  const DIRV = {North:[0,-1], South:[0,1], East:[1,0], West:[-1,0]};
  function setup(cv, G){
    W = G.w; H = G.h; COL = G.colors; NAMES = G.names; MAXHP = G.maxhp; WALLS = G.walls;
    CELL = Math.max(16, Math.min(40, Math.floor(640 / Math.max(W, H)))); PAD = CELL * 0.14;
    cv.width = W * CELL; cv.height = H * CELL;
    px = (x) => x * CELL; py = (y) => y * CELL;  // RobotRumble: y=0 at top, render straight down
  }
  function draw(ctx, cv, G, i){
    const f = G.frames[i];
    ctx.clearRect(0, 0, cv.width, cv.height);
    ctx.strokeStyle = '#21262d'; ctx.lineWidth = 1;
    for(let x=0;x<=W;x++){ctx.beginPath();ctx.moveTo(x*CELL,0);ctx.lineTo(x*CELL,H*CELL);ctx.stroke();}
    for(let y=0;y<=H;y++){ctx.beginPath();ctx.moveTo(0,y*CELL);ctx.lineTo(W*CELL,y*CELL);ctx.stroke();}
    ctx.fillStyle = '#2d333b';
    WALLS.forEach(([x,y])=>{ctx.fillRect(px(x)+1,py(y)+1,CELL-2,CELL-2);});
    f.units.forEach(u=>{
      const base = COL[u.team] || '#888';
      const frac = Math.max(0.28, u.hp / MAXHP);  // health -> opacity (full hp brightest)
      ctx.globalAlpha = frac;
      ctx.fillStyle = base;
      const r = CELL * 0.28;
      ctx.beginPath(); ctx.roundRect(px(u.x)+PAD,py(u.y)+PAD,CELL-2*PAD,CELL-2*PAD,r); ctx.fill();
      ctx.globalAlpha = 1;
      const cx = px(u.x)+CELL/2, cy = py(u.y)+CELL/2;
      if(u.act === 'Attack'){
        ctx.strokeStyle = '#ffd21f'; ctx.lineWidth = 2;
        ctx.beginPath(); ctx.arc(cx,cy,CELL*0.42,0,7); ctx.stroke();
        const d = DIRV[u.dir]; if(d){
          ctx.fillStyle = '#ffd21f';
          ctx.beginPath(); ctx.arc(cx+d[0]*CELL*0.5, cy+d[1]*CELL*0.5, CELL*0.12,0,7); ctx.fill();
        }
      }
      if(u.act === 'Move'){
        const d = DIRV[u.dir];
        if(d){
          ctx.strokeStyle = 'rgba(255,255,255,0.85)'; ctx.lineWidth = 2;
          ctx.beginPath(); ctx.moveTo(cx,cy); ctx.lineTo(cx+d[0]*CELL*0.28, cy+d[1]*CELL*0.28); ctx.stroke();
        }
      }
      const bw = CELL-2*PAD, bx = px(u.x)+PAD, by = py(u.y)+CELL-PAD*0.5;
      ctx.fillStyle = 'rgba(0,0,0,0.45)'; ctx.fillRect(bx,by-3,bw,3);
      ctx.fillStyle = '#eafff0'; ctx.fillRect(bx,by-3,bw*(u.hp/MAXHP),3);
    });
  }
  function side(G, i){
    const f = G.frames[i], COL = G.colors, NAMES = G.names, MAXHP = G.maxhp;
    const agg = {Blue:{n:0,hp:0}, Red:{n:0,hp:0}};
    f.units.forEach(u=>{ if(agg[u.team]){ agg[u.team].n++; agg[u.team].hp += u.hp; } });
    return ['Blue','Red'].map(tm=>{
      const a = agg[tm], dead = a.n===0, maxhp = 8*MAXHP;
      return `<div class="team ${dead?'tdead':''}">
        <div class="tname"><span class="sw" style="background:${COL[tm]}"></span>${NAMES[tm]} <span class="muted">(${tm})</span></div>
        <div class="stat"><span>units</span><b>${a.n}</b></div>
        <div class="stat"><span>total health</span><b>${a.hp}</b></div>
        <div class="hb"><span class="hf" style="width:${Math.min(100,100*a.hp/maxhp)}%;background:${COL[tm]}"></span></div>
      </div>`;
    }).join('') + '<div class="row muted" style="font-size:12px">move arrow \\u00b7 \\u2726 attacking \\u00b7 health = brightness</div>';
  }
  return {setup, draw, side};
})();
"""


class RobotRumbleReplayer(ReplayRenderer):
    arena = "RobotRumble"
    sim_glob = "sim*.json"  # matches both sim_<i>.json and an ad-hoc flat sim.json
    DRAW_JS = DRAW_JS

    def parse(self, raw: bytes, players=None) -> ReplayData:
        data = json.loads(raw.decode())
        turns_raw = data.get("turns", [])
        blue_name = players[0]["name"] if players and len(players) > 0 else None
        red_name = players[1]["name"] if players and len(players) > 1 else None

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
                units.append(
                    {
                        "team": o.get("team"),
                        "hp": o.get("health", 0),
                        "x": o["coords"][0],
                        "y": o["coords"][1],
                        "act": atype,
                        "dir": adir,
                    }
                )
            frames.append({"turn": t["state"].get("turn"), "units": units})

        winner_raw = data.get("winner")
        names = {"Blue": blue_name or "Blue", "Red": red_name or "Red"}
        if winner_raw in ("Blue", "Red"):
            winner, draw = names[winner_raw], False
        else:
            winner, draw = None, True

        return ReplayData(
            w=max_x + 1,
            h=max_y + 1,
            frames=frames,
            winner=winner,
            draw=draw,
            extra={
                "walls": walls,
                "names": names,
                "colors": TEAM_COLORS,
                "maxhp": MAX_HEALTH,
                "errors": data.get("errors", {}),
            },
        )
