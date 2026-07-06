"""Gomoku replay renderer.

Parses a per-game ``log-*.json`` written by the upstream engine into one frame per move
and renders a 15x15 goban you can step through — stones placed in order, with the
last-placed stone highlighted.

The JSON format: ``{"board_size":15, "players":{"black":{"name":"player1"|"player2"},
"white":{...}}, "winner":"player1"|"player2"|"draw"|null, "moves":[{"move_number":1,
"player":"black","x":7,"y":7}, ...]}``. Colors are randomized per game, so ``players``
records which of player1/player2 was black and which was white. Moves use ``board[x][y]``
indexing (``x`` = row, ``y`` = column). Black plays first; win = 5 in a row.
"""

from __future__ import annotations

import json

from codeclash.replay.base import ReplayData, ReplayRenderer

DRAW_JS = """
const ARENA = (function(){
  let N, CELL, PAD, R;  // N = board size, CELL = grid spacing, PAD = board margin, R = stone radius
  const STAR = {15:[[3,3],[3,11],[11,3],[11,11],[7,7]]};
  function setup(cv, G){
    N = G.w; CELL = 36; PAD = CELL; R = CELL * 0.42;
    cv.width = cv.height = PAD * 2 + (N - 1) * CELL;
  }
  function pos(k){ return PAD + k * CELL; }
  function draw(ctx, cv, G, i){
    const f = G.frames[i];
    ctx.fillStyle = '#dcb35c';
    ctx.fillRect(0, 0, cv.width, cv.height);
    // goban grid lines
    ctx.strokeStyle = '#6b4f1d'; ctx.lineWidth = 1;
    for(let k=0;k<N;k++){
      ctx.beginPath(); ctx.moveTo(pos(0), pos(k)); ctx.lineTo(pos(N-1), pos(k)); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(pos(k), pos(0)); ctx.lineTo(pos(k), pos(N-1)); ctx.stroke();
    }
    // star points
    ctx.fillStyle = '#6b4f1d';
    (STAR[N] || []).forEach(([r,c])=>{ ctx.beginPath(); ctx.arc(pos(c), pos(r), 3, 0, 7); ctx.fill(); });
    // stones (x = row, y = column)
    f.board.forEach(([x,y,stone],j)=>{
      const cx = pos(y), cy = pos(x);
      ctx.beginPath(); ctx.arc(cx, cy, R, 0, 7);
      ctx.fillStyle = stone === 1 ? '#111' : '#f6f6f6';
      ctx.fill();
      ctx.strokeStyle = stone === 1 ? '#000' : '#999'; ctx.lineWidth = 1; ctx.stroke();
    });
    // highlight the last-placed stone
    if(f.last){
      const [lx,ly] = f.last;
      ctx.strokeStyle = '#d64545'; ctx.lineWidth = 2;
      ctx.beginPath(); ctx.arc(pos(ly), pos(lx), R + 3, 0, 7); ctx.stroke();
    }
  }
  function side(G, i){
    const f = G.frames[i], NM = G.names || {};
    const nextTxt = i === 0 ? 'Black' : (f.next || '\\u2014');
    const done = i === G.frames.length - 1;
    return `<div class="team"><div class="tname" style="color:#111;background:#ddd;padding:2px 6px;border-radius:4px;display:inline-block">&#9679; Black <span class="muted">${NM.black||''}</span></div></div>
      <div class="team"><div class="tname">&#9675; White <span class="muted">${NM.white||''}</span></div></div>
      <div class="stat"><span>move</span><b>${i} / ${G.frames.length-1}</b></div>
      <div class="stat"><span>black stones</span><b>${f.blackCount}</b></div>
      <div class="stat"><span>white stones</span><b>${f.whiteCount}</b></div>
      <div class="stat"><span>${done ? 'result' : 'to move'}</span><b>${done ? (G.draw ? 'draw' : (G.winner || '\\u2014')) : nextTxt}</b></div>`;
  }
  return {setup, draw, side};
})();
"""


class GomokuReplayer(ReplayRenderer):
    arena = "Gomoku"
    sim_glob = "log-*.json"
    DRAW_JS = DRAW_JS

    def parse(self, raw: bytes, players=None) -> ReplayData:
        log = json.loads(raw.decode(errors="replace"))
        size = log.get("board_size", 15)
        moves = log.get("moves", [])

        # Resolve the engine's internal "player1"/"player2" tokens to real bot names.
        # The engine writes those tokens as the black/white names; the tournament's own
        # player list gives us the human-facing names (player1 == players[0]).
        token_name = {}
        if players:
            if len(players) > 0:
                token_name["player1"] = players[0].get("name", "player1")
            if len(players) > 1:
                token_name["player2"] = players[1].get("name", "player2")
        pl = log.get("players", {})
        black_token = pl.get("black", {}).get("name", "player1")
        white_token = pl.get("white", {}).get("name", "player2")
        black_name = token_name.get(black_token, black_token)
        white_name = token_name.get(white_token, white_token)

        # frame 0 = empty board, then one frame per placed stone
        board: list[list[int]] = []
        black_count = white_count = 0
        frames = [
            {
                "turn": 0,
                "board": [],
                "last": None,
                "next": "Black",
                "blackCount": 0,
                "whiteCount": 0,
            }
        ]
        for mv in moves:
            x, y = mv["x"], mv["y"]
            stone = 1 if mv["player"] == "black" else 2
            board.append([x, y, stone])
            if stone == 1:
                black_count += 1
            else:
                white_count += 1
            frames.append(
                {
                    "turn": mv.get("move_number", len(board)),
                    "board": [c[:] for c in board],
                    "last": [x, y],
                    "next": "White" if mv["player"] == "black" else "Black",
                    "blackCount": black_count,
                    "whiteCount": white_count,
                }
            )

        result = log.get("winner")
        if result in ("draw", None):
            winner, draw = None, result == "draw"
        elif result in ("player1", "player2"):
            winner, draw = token_name.get(result, result), False
        else:
            # winner recorded directly as a color, or some unknown token
            winner = {"black": black_name, "white": white_name}.get(result, result)
            draw = False

        return ReplayData(
            w=size,
            h=size,
            frames=frames,
            winner=winner,
            draw=draw,
            extra={"names": {"black": black_name, "white": white_name}},
        )
