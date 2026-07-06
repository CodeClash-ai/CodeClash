"""Chess replay renderer.

Parses a fastchess ``match_*.pgn`` (standard PGN: headers + a SAN move list) into a board
position per ply and renders an 8x8 board you can step through. Because PGN records moves in
SAN (not a board per ply), :meth:`parse` replays the moves through a small move engine to
produce the board at each ply — including castling, en passant, promotion, and disambiguation
(with king-safety as the final tie-breaker for pins).
"""

from __future__ import annotations

import re

from codeclash.replay.base import ReplayData, ReplayRenderer

START = [
    list("rnbqkbnr"),
    list("pppppppp"),
    [""] * 8,
    [""] * 8,
    [""] * 8,
    [""] * 8,
    list("PPPPPPPP"),
    list("RNBQKBNR"),
]

KNIGHT = [(-2, -1), (-2, 1), (-1, -2), (-1, 2), (1, -2), (1, 2), (2, -1), (2, 1)]
KING = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
BISHOP = [(-1, -1), (-1, 1), (1, -1), (1, 1)]
ROOK = [(-1, 0), (1, 0), (0, -1), (0, 1)]


def _sq(s: str) -> tuple[int, int]:
    """Algebraic square (e.g. 'e4') -> (row, col), row 0 = rank 8."""
    return (8 - int(s[1]), ord(s[0]) - ord("a"))


def _white(p: str) -> bool:
    return p.isupper()


def _clone(b):
    return [row[:] for row in b]


def _attacked(board, r, c, by_white: bool) -> bool:
    """Is square (r, c) attacked by a piece of the given color?"""
    # pawns
    pr = 1 if by_white else -1  # white pawns attack from row r+1 (below), moving up
    for dc in (-1, 1):
        ar, ac = r + pr, c + dc
        if 0 <= ar < 8 and 0 <= ac < 8:
            p = board[ar][ac]
            if p and _white(p) == by_white and p.upper() == "P":
                return True
    for dr, dc in KNIGHT:
        ar, ac = r + dr, c + dc
        if 0 <= ar < 8 and 0 <= ac < 8:
            p = board[ar][ac]
            if p and _white(p) == by_white and p.upper() == "N":
                return True
    for dr, dc in KING:
        ar, ac = r + dr, c + dc
        if 0 <= ar < 8 and 0 <= ac < 8:
            p = board[ar][ac]
            if p and _white(p) == by_white and p.upper() == "K":
                return True
    for dirs, kinds in ((BISHOP, "BQ"), (ROOK, "RQ")):
        for dr, dc in dirs:
            ar, ac = r + dr, c + dc
            while 0 <= ar < 8 and 0 <= ac < 8:
                p = board[ar][ac]
                if p:
                    if _white(p) == by_white and p.upper() in kinds:
                        return True
                    break
                ar, ac = ar + dr, ac + dc
    return False


def _king(board, white: bool):
    k = "K" if white else "k"
    for r in range(8):
        for c in range(8):
            if board[r][c] == k:
                return (r, c)
    return None


def _reaches(board, piece, fr, fc, tr, tc, ep) -> bool:
    """Can `piece` at (fr,fc) pseudo-legally move/capture to (tr,tc)? (path + pattern only)"""
    kind = piece.upper()
    dr, dc = tr - fr, tc - fc
    target = board[tr][tc]
    if kind == "N":
        return (abs(dr), abs(dc)) in ((1, 2), (2, 1))
    if kind == "K":
        return max(abs(dr), abs(dc)) == 1
    if kind == "P":
        white = _white(piece)
        step = -1 if white else 1
        start_row = 6 if white else 1
        if dc == 0 and target == "":  # push
            if dr == step:
                return True
            if dr == 2 * step and fr == start_row and board[fr + step][fc] == "":
                return True
            return False
        if abs(dc) == 1 and dr == step:  # capture (incl. en passant)
            return target != "" or (tr, tc) == ep
        return False
    # sliders
    dirs = BISHOP if kind == "B" else ROOK if kind == "R" else BISHOP + ROOK
    for ddr, ddc in dirs:
        r, c = fr + ddr, fc + ddc
        while 0 <= r < 8 and 0 <= c < 8:
            if (r, c) == (tr, tc):
                return True
            if board[r][c]:
                break
            r, c = r + ddr, c + ddc
    return False


def _apply(board, san, white, ep):
    """Apply one SAN move for the side to move. Returns (new_board, from, to, new_ep)."""
    m = san.rstrip("+#!?")
    b = _clone(board)

    if m in ("O-O", "O-O-O", "0-0", "0-0-0"):
        row = 7 if white else 0
        k = "K" if white else "k"
        rk = "R" if white else "r"
        if m in ("O-O", "0-0"):
            b[row][4], b[row][6], b[row][7], b[row][5] = "", k, "", rk
            return b, (row, 4), (row, 6), None
        b[row][4], b[row][2], b[row][0], b[row][3] = "", k, "", rk
        return b, (row, 4), (row, 2), None

    promo = ""
    if "=" in m:
        m, promo = m.split("=")
        promo = promo[0]
    m = m.replace("x", "")
    dest = m[-2:]
    tr, tc = _sq(dest)
    head = m[:-2]
    kind = head[0] if head and head[0] in "NBRQK" else "P"
    hint = head[1:] if kind != "P" else head  # disambiguation (file/rank), or pawn's from-file
    want = kind if white else kind.lower()

    candidates = []
    for r in range(8):
        for c in range(8):
            if board[r][c] == want and _reaches(board, want, r, c, tr, tc, ep):
                candidates.append((r, c))
    for ch in hint:  # filter by file/rank disambiguation
        if ch.isalpha():
            candidates = [(r, c) for (r, c) in candidates if c == ord(ch) - ord("a")]
        elif ch.isdigit():
            candidates = [(r, c) for (r, c) in candidates if r == 8 - int(ch)]
    if len(candidates) > 1:  # remaining ambiguity = pins; keep only king-safe moves
        safe = []
        for r, c in candidates:
            t = _clone(board)
            t[tr][tc] = t[r][c]
            t[r][c] = ""
            kp = _king(t, white)
            if kp and not _attacked(t, kp[0], kp[1], not white):
                safe.append((r, c))
        if safe:
            candidates = safe
    fr, fc = candidates[0]

    piece = b[fr][fc]
    new_ep = None
    if kind == "P":
        if (tr, tc) == ep and board[tr][tc] == "":  # en passant: remove passed pawn
            b[fr][tc] = ""
        if abs(tr - fr) == 2:  # double push sets the en-passant square
            new_ep = ((fr + tr) // 2, fc)
        if promo:
            piece = promo if white else promo.lower()
    b[fr][fc] = ""
    b[tr][tc] = piece
    return b, (fr, fc), (tr, tc), new_ep


def _movetext(pgn: str) -> list[str]:
    """Extract the SAN token list from PGN movetext (strip headers/comments/numbers/result)."""
    lines = [ln for ln in pgn.splitlines() if not ln.startswith("[")]
    text = " ".join(lines)
    text = re.sub(r"\{[^}]*\}", " ", text)  # comments
    text = re.sub(r"\([^)]*\)", " ", text)  # variations
    text = re.sub(r"\$\d+", " ", text)  # NAGs
    text = re.sub(r"\d+\.(\.\.)?", " ", text)  # move numbers
    out = []
    for tok in text.split():
        if tok in ("1-0", "0-1", "1/2-1/2", "*"):
            break
        out.append(tok)
    return out


def _header(pgn: str, key: str) -> str | None:
    m = re.search(rf'\[{key}\s+"([^"]*)"\]', pgn)
    return m.group(1) if m else None


DRAW_JS = """
const ARENA = (function(){
  const GLYPH = {K:'\\u2654',Q:'\\u2655',R:'\\u2656',B:'\\u2657',N:'\\u2658',P:'\\u2659',
                 k:'\\u265a',q:'\\u265b',r:'\\u265c',b:'\\u265d',n:'\\u265e',p:'\\u265f'};
  let CELL;
  function setup(cv, G){ CELL = 60; cv.width = 8*CELL; cv.height = 8*CELL; }
  function draw(ctx, cv, G, i){
    const f = G.frames[i];
    for(let r=0;r<8;r++) for(let c=0;c<8;c++){
      const light = (r+c)%2===0;
      ctx.fillStyle = light ? '#ebecd0' : '#739552';
      ctx.fillRect(c*CELL, r*CELL, CELL, CELL);
    }
    const hl = (sq)=>{ if(sq){ ctx.fillStyle='rgba(255,241,120,0.55)'; ctx.fillRect(sq[1]*CELL, sq[0]*CELL, CELL, CELL); } };
    hl(f.from); hl(f.to);
    ctx.textAlign='center'; ctx.textBaseline='middle'; ctx.font = Math.floor(CELL*0.78)+'px serif';
    for(let r=0;r<8;r++) for(let c=0;c<8;c++){
      const p = f.board[r][c];
      if(p){
        ctx.fillStyle = (p===p.toUpperCase()) ? '#fff' : '#111';
        ctx.strokeStyle = (p===p.toUpperCase()) ? '#333' : '#000'; ctx.lineWidth = 1;
        const x = c*CELL+CELL/2, y = r*CELL+CELL/2;
        ctx.strokeText(GLYPH[p], x, y); ctx.fillText(GLYPH[p], x, y);
      }
    }
  }
  function side(G, i){
    const f = G.frames[i], N = G.names || {};
    const mover = i===0 ? '\\u2014' : (i%2===1 ? 'White' : 'Black');
    return `<div class="team"><div class="tname">&#9812; White <span class="muted">${N.white||''}</span></div></div>
      <div class="team"><div class="tname" style="color:#111;background:#ddd;padding:2px 6px;border-radius:4px;display:inline-block">&#9818; Black <span class="muted">${N.black||''}</span></div></div>
      <div class="stat"><span>ply</span><b>${i} / ${G.frames.length-1}</b></div>
      <div class="stat"><span>just moved</span><b>${mover}</b></div>`;
  }
  return {setup, draw, side};
})();
"""


class ChessReplayer(ReplayRenderer):
    arena = "Chess"
    sim_glob = "match_*.pgn"
    DRAW_JS = DRAW_JS

    def parse(self, raw: bytes, players=None) -> ReplayData:
        pgn = raw.decode(errors="replace")
        white = _header(pgn, "White") or "White"
        black = _header(pgn, "Black") or "Black"
        result = _header(pgn, "Result") or "*"

        board = _clone(START)
        frames = [{"turn": 0, "board": _clone(board), "from": None, "to": None}]
        ep = None
        turn_white = True
        for ply, san in enumerate(_movetext(pgn), start=1):
            try:
                board, frm, to, ep = _apply(board, san, turn_white, ep)
            except Exception:
                break  # malformed / unexpected token — stop where we are
            frames.append({"turn": ply, "board": _clone(board), "from": list(frm), "to": list(to)})
            turn_white = not turn_white

        if result == "1-0":
            winner, draw = white, False
        elif result == "0-1":
            winner, draw = black, False
        elif result == "1/2-1/2":
            winner, draw = None, True
        else:
            winner, draw = None, False

        return ReplayData(
            w=8, h=8, frames=frames, winner=winner, draw=draw, extra={"names": {"white": white, "black": black}}
        )
