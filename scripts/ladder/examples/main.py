"""Reference Gomoku bot for the CodeClash arena contract.

The arena calls ONE function per turn:

    get_move(board, color) -> (row, col)

  * board: 15x15 list-of-lists of ints, 0=empty, 1=black, 2=white.
  * color: "black" or "white" (black moves first).
  * return: (row, col) of an EMPTY cell. Win = 5 in a row (H/V/diagonal).

This reference is a compact, dependency-free heuristic used as the porting example
and the smoke-test opponent: (1) win now if possible, (2) block the opponent's
immediate win, (3) otherwise score empty cells near existing stones by the line
potential they create for me and deny to the opponent, and play the best.
"""

SIZE = 15
_DIRS = [(1, 0), (0, 1), (1, 1), (1, -1)]


def _stones(color):
    me = 1 if color == "black" else 2
    return me, (2 if me == 1 else 1)


def _on(r, c):
    return 0 <= r < SIZE and 0 <= c < SIZE


def _makes_five(board, r, c, stone):
    """Would playing `stone` at (r,c) complete 5+ in a row?"""
    for dr, dc in _DIRS:
        n = 1
        for sgn in (1, -1):
            rr, cc = r + dr * sgn, c + dc * sgn
            while _on(rr, cc) and board[rr][cc] == stone:
                n += 1
                rr += dr * sgn
                cc += dc * sgn
        if n >= 5:
            return True
    return False


def _line_score(board, r, c, stone):
    """Rough potential of playing `stone` at (r,c): sum over directions of the
    contiguous run length it extends, weighted super-linearly."""
    total = 0
    for dr, dc in _DIRS:
        run = 0
        for sgn in (1, -1):
            rr, cc = r + dr * sgn, c + dc * sgn
            while _on(rr, cc) and board[rr][cc] == stone:
                run += 1
                rr += dr * sgn
                cc += dc * sgn
        total += (run + 1) ** 2
    return total


def _candidates(board):
    """Empty cells adjacent (incl. diagonally) to any stone; center if board empty."""
    cells = set()
    any_stone = False
    for r in range(SIZE):
        for c in range(SIZE):
            if board[r][c] != 0:
                any_stone = True
                for dr in (-1, 0, 1):
                    for dc in (-1, 0, 1):
                        rr, cc = r + dr, c + dc
                        if _on(rr, cc) and board[rr][cc] == 0:
                            cells.add((rr, cc))
    if not any_stone:
        return [(SIZE // 2, SIZE // 2)]
    return list(cells)


def get_move(board, color):
    me, opp = _stones(color)
    cands = _candidates(board)

    # 1. win now
    for r, c in cands:
        if _makes_five(board, r, c, me):
            return (r, c)
    # 2. block opponent's win
    for r, c in cands:
        if _makes_five(board, r, c, opp):
            return (r, c)
    # 3. best heuristic cell (my potential + defensive value)
    best, best_rc = -1, cands[0]
    for r, c in cands:
        s = _line_score(board, r, c, me) + 0.9 * _line_score(board, r, c, opp)
        if s > best:
            best, best_rc = s, (r, c)
    return best_rc
