# Ladder build tooling

Operational one-off scripts for constructing a **porting-based** CC:Ladder — one where the
human bots are open-source agents written against a different framework API and must be ported
into an arena's single-file submission contract before they can be ranked. Built for SCML OneShot
(`decide(observation)`), but the workflow generalizes to other arenas (e.g. Halite).

This is scaffolding, not product code — nothing under `codeclash/` imports it. The durable
outputs of a build are: the `human/*` branches on `CodeClash-ai/<arena>` (the bots), the
`configs/ablations/ladder/*.yaml` configs, and the arena's Dockerfile wiring. Ports themselves
are **not** committed here (see `.gitignore`); they live on the branches.

## Files
- `PORTING_GUIDE.md` — the `decide(observation)` contract + how to port a source agent. Hand this
  to a porting agent (with `examples/scml_agent.py` as the worked reference).
- `examples/` — a reference port (`scml_agent.py` = GreedyOneShotAgent) + `dummy_agent.py` + an
  arena smoke config (`scml_ffa.yaml`). Used by the smoke scripts.
- `validate_ports.py` — stage 1: local syntax/import/`decide` check over `ports/*.py`.
- `run_smoke_all.sh` — stage 2: run every stage-1 pass through the real runtime in Docker,
  batched, to confirm each plays without crashing/erroring. Writes `ports/_stage2.json`.
- `smoke_scml.sh` — quick single-pair smoke (example greedy vs dummy) through the arena image.
- `push_branches.sh` — push each stage-2-healthy port to `CodeClash-ai/SCML` as a
  `human/<author>/<name>` branch (dedupes identical content; skips a SKIP list).
- `RUN_ON_AWS.md` — how to run the round-robin (`ladder make`) + Elo ranking on a big box.

## Typical flow
1. Populate `ports/<year>__<team>.py` (fan out porting agents with `PORTING_GUIDE.md`).
2. `python3 scripts/ladder/validate_ports.py`  → stage 1
3. `bash scripts/ladder/run_smoke_all.sh`       → stage 2 (needs Docker)
4. `bash scripts/ladder/push_branches.sh`       → push healthy ports to branches
5. Rank + assemble configs — see `RUN_ON_AWS.md`.
