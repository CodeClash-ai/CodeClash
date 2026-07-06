# Ladder build tooling (Gomoku)

Operational one-off scripts for constructing a **porting-based** CC:Ladder — one where the
human bots are open-source agents that must be ported into the arena's single-file submission
contract before they can be ranked. This branch targets **Gomoku** (`main.py` defining
`get_move(board, color) -> (row, col)`); the same workflow was used for SCML OneShot.

This is scaffolding, not product code — nothing under `codeclash/` imports it. The durable
outputs of a build are: the `human/*` branches on `CodeClash-ai/Gomoku` (the bots) and the
`configs/ablations/ladder/*.yaml` configs. Ports themselves are **not** committed here (see
`.gitignore`); they live on the branches.

## Files
- `PORTING_GUIDE.md` — the `get_move` contract + how to port a source bot. Hand this to a porting
  agent (with `examples/main.py` as the worked reference).
- `examples/main.py` — a clean, dependency-free reference bot (win/block/heuristic). Used as the
  worked porting example and the stage-2 smoke opponent.
- `examples/gomoku_smoke.yaml` — a 2-player arena smoke config (branch bot vs default).
- `validate_ports.py` — stage 1: local syntax/import/`get_move` legality check over `ports/*.py`.
- `run_smoke_all.sh` — stage 2: play every stage-1 pass vs the reference bot through the real
  engine in Docker; confirm each plays full games without erroring/hanging. Writes `ports/_stage2.json`.
- `smoke_gomoku.sh` — quick single-pair smoke (reference vs the arena default) through the image.
- `push_branches.sh` — push each stage-2-healthy port to `CodeClash-ai/Gomoku` as a
  `human/gomoku/<slug>` branch (submission `main.py`; dedupes identical content).
- `RUN.md` — how to run the round-robin (`ladder make`) + Elo ranking (cheap — runs locally).

## Typical flow
1. Populate `ports/<slug>.py` (fan out porting agents with `PORTING_GUIDE.md`).
2. `python3 scripts/ladder/validate_ports.py`  → stage 1
3. `bash scripts/ladder/run_smoke_all.sh`       → stage 2 (needs Docker)
4. `bash scripts/ladder/push_branches.sh`       → push healthy ports to branches
5. Rank + assemble configs — see `RUN.md`.
