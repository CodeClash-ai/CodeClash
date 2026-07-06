"""Stage 1 validator: mirrors the Gomoku arena's validate_code locally (no Docker needed,
since ports are stdlib-only). For each ports/*.py: syntax-compile, import, assert a top-level
callable get_move, and call it on an empty 15x15 board and a mid-game board — the return must be
a legal (row, col) tuple pointing at an EMPTY cell. Prints PASS/FAIL per file, writes ports/_stage1.json.
"""

import ast
import importlib.util
import json
import sys
from pathlib import Path

PORTS = Path(__file__).parent / "ports"
SIZE = 15
BANNED = ("numpy", "torch", "tensorflow", "pygame", "tkinter", "sklearn", "pandas")


def _empty():
    return [[0] * SIZE for _ in range(SIZE)]


def _midgame():
    b = _empty()
    b[7][7] = 1
    b[7][8] = 2
    b[8][7] = 1
    b[6][6] = 2
    return b


def _legal(mv, board):
    if not (isinstance(mv, (tuple, list)) and len(mv) == 2):
        return False, f"return must be (row, col), got {mv!r}"
    r, c = mv
    if not (isinstance(r, int) and isinstance(c, int)):
        return False, f"row/col must be ints, got {mv!r}"
    if not (0 <= r < SIZE and 0 <= c < SIZE):
        return False, f"move {mv} off 15x15 board"
    if board[r][c] != 0:
        return False, f"move {mv} lands on an occupied cell"
    return True, ""


def check(path: Path):
    src = path.read_text()
    try:
        ast.parse(src)
    except SyntaxError as e:
        return False, f"syntax: {e}"
    for b in BANNED:
        if f"import {b}" in src or f"from {b}" in src:
            return False, f"imports banned (non-stdlib) module: {b}"
    try:
        spec = importlib.util.spec_from_file_location(f"port_{path.stem}", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    except Exception as e:
        return False, f"import: {type(e).__name__}: {e}"
    if not hasattr(mod, "get_move") or not callable(mod.get_move):
        return False, "no callable get_move"
    for label, board, color in [("empty", _empty(), "black"), ("midgame", _midgame(), "white")]:
        try:
            mv = mod.get_move([row[:] for row in board], color)
        except Exception as e:
            return False, f"get_move raised on {label}: {type(e).__name__}: {e}"
        ok, why = _legal(mv, board)
        if not ok:
            return False, f"{label}: {why}"
    return True, "ok"


def main():
    files = sorted(f for f in PORTS.glob("*.py") if not f.name.startswith("_"))
    results, npass = {}, 0
    for f in files:
        ok, msg = check(f)
        results[f.name] = {"pass": ok, "msg": msg}
        print(f"  {'PASS' if ok else 'FAIL'}  {f.name}" + ("" if ok else f"   <- {msg}"))
        npass += ok
    (PORTS / "_stage1.json").write_text(json.dumps(results, indent=2, sort_keys=True))
    print(f"\nStage 1: {npass} pass / {len(files) - npass} fail  of {len(files)} ports")


if __name__ == "__main__":
    main()
