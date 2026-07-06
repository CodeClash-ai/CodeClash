# Ladder build tooling (RoboCode)

Operational one-off scripts for constructing a CC:Ladder for **classic Robocode**. Unlike the
SCML/Gomoku ladders (which re-express bots into a function contract), Robocode importing is mostly
a mechanical **copy-in + rename**: classic bots are Java classes that drop into `robots/custom/`.

This is scaffolding, not product code — nothing under `codeclash/` imports it. The durable outputs
are the `human/*` branches on `CodeClash-ai/RoboCode` (the bots) and the
`configs/ablations/ladder/*.yaml` configs. Ports are **not** committed here (see `.gitignore`).

## Files
- `PORTING_GUIDE.md` — the classic-Robocode submission contract + copy-in/rename rules (main class
  → `MyTank`, `package custom;`, flat files, no stray "custom" token). Hand to an import agent with
  `examples/robots/custom/MyTank.java` as the reference.
- `examples/robots/custom/MyTank.java` — reference bot (AdvancedRobot) + porting example.
- `validate_ports.py` — stage 1 (structural, local): each `ports/<slug>/` has `MyTank.java` with
  `class MyTank extends <RobocodeBase>`, `package custom;`, flat, no sed-hazard token. Writes `_stage1.json`.
- `run_smoke_all.sh` — **stage 2 (the real gate):** in the arena Docker image, compile each port
  (`javac -cp libs/robocode.jar`) and run a real 3-round battle vs `sample.Walls`; confirm it
  compiles AND plays. Writes `_stage2.json` + per-bot compile/battle logs in `out/`.
- `push_branches.sh` — push each stage-2-healthy `ports/<slug>/` to `CodeClash-ai/RoboCode` as
  `human/robocode/<slug>` with the files under `robots/custom/`.
- `RUN.md` — round-robin (`ladder make`) + Elo ranking instructions.

## Typical flow
1. Populate `ports/<slug>/MyTank.java` (fan out import agents with `PORTING_GUIDE.md`).
2. `python3 scripts/ladder/validate_ports.py`   → stage 1 (structural)
3. `bash scripts/ladder/run_smoke_all.sh`        → stage 2 (compile + battle each; needs Docker)
4. `bash scripts/ladder/push_branches.sh`        → push healthy ports to branches
5. Rank + assemble configs — see `RUN.md`.

Note: `ports/` and `out/` are gitignored and shared on disk across branches — clean stale files
(`rm -rf scripts/ladder/ports/* scripts/ladder/out`) when switching between arena ladder branches.
