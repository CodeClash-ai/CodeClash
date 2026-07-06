# Porting a Gomoku bot to the CodeClash `get_move` contract

You are porting ONE open-source Gomoku / Gobang / Renju bot into a single self-contained
`main.py` that defines **one function**:

```python
def get_move(board, color) -> tuple:   # returns (row, col)
```

- `board`: a 15x15 list-of-lists of ints — `0`=empty, `1`=black, `2`=white.
- `color`: `"black"` or `"white"`. Black moves first. Win = 5 in a row (H/V/either diagonal).
- Return `(row, col)` of an **empty** cell (0-indexed). Returning an occupied/off-board cell or
  raising an exception forfeits the game, so be defensive.

A clean, dependency-free reference implementation lives at
`scripts/ladder/examples/main.py` — read it first; mirror its structure and defensive style.

## Hard rules
- **Stdlib only.** No numpy/pygame/tkinter/torch/etc. The arena image is plain Python 3.10 with
  the standard library only. Re-express any array math in pure Python lists.
- **No trained weights / no NN.** If the source bot is AlphaZero/CNN/RL and has no rule-based
  fallback, DO NOT port it — say so in your report (it should have been filtered out already).
- **One file, one function.** Everything the bot needs (search, evaluation, tables) goes inside
  `main.py`. Helper functions/classes are fine; `get_move` is the entry point.
- **Never raise.** Wrap the body so any internal error falls back to a safe legal move (e.g. the
  first empty cell, or center). A crash = a forfeit.
- **Be reasonably fast.** There is no hard per-move timeout in the engine, but a game plays many
  moves and the round-robin plays many games — keep search depth/rollouts modest (a move should
  return in well under a second on a 15x15 board). Cap minimax depth / MCTS iterations sensibly.

## What to extract from the source
Most source repos wrap their AI in a GUI (pygame/tkinter), a Gomocup/piskvork stdin-stdout
protocol loop, or a class with its own board representation. Ignore all of that. Find the core
**"given a board, choose a move"** logic — usually a `minimax`/`negamax`/`alphabeta`, an MCTS
tree search, or a threat/shape evaluation over candidate cells — and re-express it as:

1. Convert the arena `board` (list-of-lists, 0/1/2) to whatever the algorithm wants (often the
   same, sometimes it uses -1/1 or 'X'/'O' — remap). Determine `me`/`opp` from `color`.
2. Run the source's move-selection over the current board.
3. Map the chosen move back to a `(row, col)` int tuple and return it.

Keep behavior faithful: same evaluation weights, same search depth, same tie-breaks where you can.
If the source relies on state across turns (opening books, transposition tables, incremental
board), either recompute from `board` each call or hold it in module-level globals keyed sensibly
— but the engine calls `get_move` fresh each turn with the full board, so stateless recomputation
is usually simplest and correct.

## For non-Python sources (JS / Java / C++ — the "PROTOCOL-PORT" bucket)
Reimplement the evaluation + search in Python. Prioritize faithfulness of the **evaluation
function** (shape/threat scoring tables) and the **search** (depth, pruning); these determine
strength. Drop language-specific perf tricks (bitboards, Zobrist/TT) unless easy — correctness and
the eval shape matter more than raw speed for the ladder.

## Deliverable
Write your port to `scripts/ladder/ports/<name>.py` (see the batch prompt for the exact filename,
e.g. `colingogogo.py`). It must:
- `python3 -c "import ast; ast.parse(open(FILE).read())"` cleanly,
- define a top-level `get_move(board, color)`,
- return a legal `(row, col)` on an empty starter board and mid-game, never raising.

Keep a short module docstring naming the source (repo + author + algorithm) and noting any
simplifications/dropped features (e.g. "dropped Zobrist TT", "MCTS iters capped at 2000").
