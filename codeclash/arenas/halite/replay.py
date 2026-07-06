"""Halite (v1) replay renderer.

Parses a Halite ``.hlt`` replay (classic JSON: ``frames`` = a per-turn ``height x width``
grid of ``[owner, strength]`` cells, plus a static ``productions`` grid) and renders the
board as animated territory — each cell tinted by its owner, brightened by its strength.

The arena already passes ``--replaydirectory`` so the engine deposits the ``.hlt`` into the
round logs; no arena change was needed.
"""

from __future__ import annotations

import json
from collections import Counter

from codeclash.replay.base import ReplayData, ReplayRenderer

PALETTE = ["#3B78FF", "#E5484D", "#30A46C", "#F5A623", "#8E4EC6", "#12A594", "#E93D82", "#F76B15"]

DRAW_JS = """
const ARENA = (function(){
  let W, H, CELL, COL, PROD, MAXP;
  function setup(cv, G){
    W = G.w; H = G.h; COL = G.colors; PROD = G.productions;
    MAXP = 1; for(const row of PROD) for(const v of row) if(v > MAXP) MAXP = v;
    CELL = Math.max(6, Math.min(20, Math.floor(620 / Math.max(W, H))));
    cv.width = W * CELL; cv.height = H * CELL;
  }
  function draw(ctx, cv, G, i){
    const cells = G.frames[i].cells;
    ctx.clearRect(0, 0, cv.width, cv.height);
    for(let r=0;r<H;r++) for(let c=0;c<W;c++){
      const [owner, strength] = cells[r][c];
      if(owner === 0){
        const g = 22 + Math.round(46 * (PROD[r][c] / MAXP));  // neutral: shade by production
        ctx.fillStyle = `rgb(${g},${g},${g})`;
      } else {
        ctx.fillStyle = COL[owner] || '#888';
        ctx.globalAlpha = 0.3 + 0.7 * Math.min(1, strength / 255);
      }
      ctx.fillRect(c*CELL, r*CELL, CELL, CELL);
      ctx.globalAlpha = 1;
    }
  }
  function side(G, i){
    const cells = G.frames[i].cells, NAMES = G.names || {};
    const terr = {}, str = {};
    for(const row of cells) for(const [o, s] of row){ if(o>0){ terr[o]=(terr[o]||0)+1; str[o]=(str[o]||0)+s; } }
    return Object.keys(COL).map(o=>`
      <div class="team"><div class="tname"><span class="sw" style="background:${COL[o]}"></span>${NAMES[o]||('Player '+o)}</div>
        <div class="stat"><span>territory</span><b>${terr[o]||0}</b></div>
        <div class="stat"><span>strength</span><b>${str[o]||0}</b></div></div>`).join('');
  }
  return {setup, draw, side};
})();
"""


class HaliteReplayer(ReplayRenderer):
    arena = "Halite"
    sim_glob = "*.hlt"
    DRAW_JS = DRAW_JS

    def parse(self, raw: bytes, players=None) -> ReplayData:
        d = json.loads(raw.decode())
        w, h = d["width"], d["height"]
        frames_raw = d["frames"]
        num_players = d.get("num_players", 2)
        engine_names = d.get("player_names", [])

        def name_for(owner: int) -> str:
            if players and len(players) >= owner:
                return players[owner - 1]["name"]
            if len(engine_names) >= owner:
                return engine_names[owner - 1]
            return f"Player {owner}"

        colors = {o: PALETTE[(o - 1) % len(PALETTE)] for o in range(1, num_players + 1)}
        names = {o: name_for(o) for o in range(1, num_players + 1)}

        frames = [{"turn": i, "cells": grid} for i, grid in enumerate(frames_raw)]

        # Winner = most territory in the final frame (Halite is territory control); tie -> draw.
        tally = Counter()
        for row in frames_raw[-1]:
            for owner, _strength in row:
                if owner > 0:
                    tally[owner] += 1
        top = tally.most_common()
        if not top or (len(top) > 1 and top[0][1] == top[1][1]):
            winner, draw = None, True
        else:
            winner, draw = name_for(top[0][0]), False

        return ReplayData(
            w=w,
            h=h,
            frames=frames,
            winner=winner,
            draw=draw,
            extra={"productions": d.get("productions", []), "colors": colors, "names": names},
        )
