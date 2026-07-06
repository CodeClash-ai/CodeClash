"""Bomberland replay renderer.

Parses a per-game Bomberland trace (written by ``run_bomberland.py`` as
``sim_<idx>.json``) into normalized playback data and draws the grid: metal /
wood walls, bombs, blasts, and units colored per agent with health-as-brightness.
A ``side(G, i)`` panel shows per-agent unit counts / total hp / current tick.

The trace JSON is a single object ``{width, height, winner, sim, player_order,
frames:[...]}``. Each frame has ``tick``, ``units`` (each with ``unit_id``,
``agent_id``, ``coordinates`` [x,y], ``hp``) and ``entities`` (each with ``type``
in {"m" metal, "w" wood, "b" bomb, "x" blast} and ``coordinates`` [x,y]; bombs
additionally carry ``timer`` / ``owner`` / ``blast_diameter``, blasts carry
``ttl``). ``player_order`` is the two agent ids for this sim; the first is Blue,
the second Red.
"""

from __future__ import annotations

import json

from codeclash.replay.base import ReplayData, ReplayRenderer

START_HP = 3
TEAM_COLORS = {"Blue": "#3B78FF", "Red": "#E5484D"}

DRAW_JS = """
const ARENA = (function(){
  let W, H, CELL, PAD, COL, NAMES, AGENTS, MAXHP;
  function teamOf(agentId){ return (AGENTS[0] === agentId) ? 'Blue' : 'Red'; }
  function setup(cv, G){
    W = G.w; H = G.h; COL = G.colors; NAMES = G.names; AGENTS = G.agents; MAXHP = G.maxhp;
    CELL = Math.max(16, Math.min(40, Math.floor(640 / Math.max(W, H)))); PAD = CELL * 0.14;
    cv.width = W * CELL; cv.height = H * CELL;
  }
  function px(x){ return x * CELL; }
  function py(y){ return y * CELL; }
  function draw(ctx, cv, G, i){
    const f = G.frames[i];
    ctx.clearRect(0, 0, cv.width, cv.height);
    ctx.fillStyle = '#0d1117'; ctx.fillRect(0, 0, cv.width, cv.height);
    ctx.strokeStyle = '#21262d'; ctx.lineWidth = 1;
    for(let x=0;x<=W;x++){ctx.beginPath();ctx.moveTo(x*CELL,0);ctx.lineTo(x*CELL,H*CELL);ctx.stroke();}
    for(let y=0;y<=H;y++){ctx.beginPath();ctx.moveTo(0,y*CELL);ctx.lineTo(W*CELL,y*CELL);ctx.stroke();}
    // World entities: draw walls first, then blasts, then bombs.
    const bombs = [], blasts = [];
    f.entities.forEach(e=>{
      const x = e.coordinates[0], y = e.coordinates[1];
      if(e.type === 'm'){
        ctx.fillStyle = '#6e7681';
        ctx.fillRect(px(x)+1, py(y)+1, CELL-2, CELL-2);
      } else if(e.type === 'w'){
        ctx.fillStyle = '#8a5a2b';
        ctx.fillRect(px(x)+2, py(y)+2, CELL-4, CELL-4);
        ctx.strokeStyle = '#5c3a1c'; ctx.lineWidth = 1;
        ctx.strokeRect(px(x)+2, py(y)+2, CELL-4, CELL-4);
      } else if(e.type === 'b'){
        bombs.push(e);
      } else if(e.type === 'x'){
        blasts.push(e);
      }
    });
    blasts.forEach(e=>{
      const x = e.coordinates[0], y = e.coordinates[1];
      ctx.fillStyle = 'rgba(255,140,0,0.55)';
      ctx.fillRect(px(x)+1, py(y)+1, CELL-2, CELL-2);
      ctx.fillStyle = 'rgba(255,220,60,0.7)';
      ctx.beginPath(); ctx.arc(px(x)+CELL/2, py(y)+CELL/2, CELL*0.22, 0, 7); ctx.fill();
    });
    bombs.forEach(e=>{
      const x = e.coordinates[0], y = e.coordinates[1];
      const cx = px(x)+CELL/2, cy = py(y)+CELL/2;
      ctx.fillStyle = '#0b0b0b';
      ctx.beginPath(); ctx.arc(cx, cy, CELL*0.3, 0, 7); ctx.fill();
      ctx.strokeStyle = '#ff5722'; ctx.lineWidth = 2;
      ctx.beginPath(); ctx.arc(cx, cy, CELL*0.3, 0, 7); ctx.stroke();
      if(e.timer != null){
        ctx.fillStyle = '#ffd21f'; ctx.font = `${Math.floor(CELL*0.34)}px system-ui`;
        ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
        ctx.fillText(String(e.timer), cx, cy);
      }
    });
    // Units on top.
    f.units.forEach(u=>{
      if(u.hp <= 0) return;
      const tm = teamOf(u.agent_id);
      const base = COL[tm] || '#888';
      const frac = Math.max(0.3, u.hp / MAXHP);
      ctx.globalAlpha = frac;
      ctx.fillStyle = base;
      const r = CELL * 0.28;
      ctx.beginPath(); ctx.roundRect(px(u.x)+PAD, py(u.y)+PAD, CELL-2*PAD, CELL-2*PAD, r); ctx.fill();
      ctx.globalAlpha = 1;
      const bw = CELL-2*PAD, bx = px(u.x)+PAD, by = py(u.y)+CELL-PAD*0.5;
      ctx.fillStyle = 'rgba(0,0,0,0.45)'; ctx.fillRect(bx, by-3, bw, 3);
      ctx.fillStyle = '#eafff0'; ctx.fillRect(bx, by-3, bw*Math.min(1, u.hp/MAXHP), 3);
    });
  }
  function side(G, i){
    const f = G.frames[i], COL = G.colors, NAMES = G.names, AGENTS = G.agents, MAXHP = G.maxhp;
    const agg = {Blue:{n:0,hp:0}, Red:{n:0,hp:0}};
    let totalUnits = {Blue:0, Red:0};
    f.units.forEach(u=>{
      const tm = (AGENTS[0] === u.agent_id) ? 'Blue' : 'Red';
      totalUnits[tm]++;
      if(u.hp > 0){ agg[tm].n++; agg[tm].hp += u.hp; }
    });
    return ['Blue','Red'].map(tm=>{
      const a = agg[tm], dead = a.n===0, maxhp = Math.max(1, totalUnits[tm]) * MAXHP;
      return `<div class="team ${dead?'tdead':''}">
        <div class="tname"><span class="sw" style="background:${COL[tm]}"></span>${NAMES[tm]} <span class="muted">(${tm})</span></div>
        <div class="stat"><span>units alive</span><b>${a.n}</b></div>
        <div class="stat"><span>total hp</span><b>${a.hp}</b></div>
        <div class="hb"><span class="hf" style="width:${Math.min(100,100*a.hp/maxhp)}%;background:${COL[tm]}"></span></div>
      </div>`;
    }).join('') + `<div class="row muted" style="font-size:12px">tick ${f.tick} \\u00b7 hp = brightness \\u00b7 \\ud83d\\udca3 bomb (timer) \\u00b7 \\ud83d\\udd25 blast</div>`;
  }
  return {setup, draw, side};
})();
"""


class BomberlandReplayer(ReplayRenderer):
    arena = "Bomberland"
    sim_glob = "sim_*.json"
    DRAW_JS = DRAW_JS

    def parse(self, raw: bytes, players=None) -> ReplayData:
        data = json.loads(raw.decode())
        width = int(data.get("width", 0))
        height = int(data.get("height", 0))
        frames_raw = data.get("frames", [])
        player_order = data.get("player_order", [])

        frames = []
        for fr in frames_raw:
            units = []
            for u in fr.get("units", []):
                coords = u.get("coordinates", [0, 0])
                units.append(
                    {
                        "unit_id": u.get("unit_id"),
                        "agent_id": u.get("agent_id"),
                        "x": coords[0],
                        "y": coords[1],
                        "hp": u.get("hp", 0),
                    }
                )
            entities = []
            for e in fr.get("entities", []):
                coords = e.get("coordinates", [0, 0])
                ent = {"type": e.get("type"), "coordinates": [coords[0], coords[1]]}
                if "timer" in e:
                    ent["timer"] = e["timer"]
                if "owner" in e:
                    ent["owner"] = e["owner"]
                if "ttl" in e:
                    ent["ttl"] = e["ttl"]
                entities.append(ent)
            frames.append({"turn": fr.get("tick"), "tick": fr.get("tick"), "units": units, "entities": entities})

        # First player_order id -> Blue, second -> Red. Fall back to display names.
        blue_id = player_order[0] if len(player_order) > 0 else "Blue"
        red_id = player_order[1] if len(player_order) > 1 else "Red"
        names = {"Blue": blue_id, "Red": red_id}

        winner_raw = data.get("winner")
        if winner_raw == blue_id:
            winner, draw = names["Blue"], False
        elif winner_raw == red_id:
            winner, draw = names["Red"], False
        else:  # "TIE" or unknown
            winner, draw = None, True

        return ReplayData(
            w=width,
            h=height,
            frames=frames,
            winner=winner,
            draw=draw,
            extra={
                "names": names,
                "colors": TEAM_COLORS,
                "agents": [blue_id, red_id],
                "maxhp": START_HP,
            },
        )
