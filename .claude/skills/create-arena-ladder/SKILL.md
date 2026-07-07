---
name: create-arena-ladder
description: >-
  Build a CC:Ladder for any CodeClash arena: import human-written solutions as git
  branches, rank them via round-robin PvP + Elo, and assemble the ladder configs.
  Use when asked to "create a ladder", "import human solutions", "push human bots as
  branches", or "make a CC:<arena> ladder" for arenas like BattleSnake, RobotRumble,
  CoreWar, Gomoku, RoboCode, SCML, etc.
---

# Create an Arena Ladder (CC:Ladder)

A **ladder** turns a curated set of human-written bots into a ranked gauntlet, then
measures how far up a model can climb. Two phases: **make the ladder** (rank the humans
via round-robin), then **run the ladder** (a model climbs rung by rung until it loses).

This skill produces, for arena `<A>`: `human/<author>/<name>` branches on `CodeClash-ai/<A>`,
a `make_<a>.yaml` (round-robin), a ranked `rungs/<a>.yaml`, and a run config `<a>.yaml`.

Work in the `repo/` clone. Reference implementations to mirror:
`configs/ablations/ladder/{make_battlesnake,battlesnake,rungs/battlesnake}.yaml` and its
`README.md`. For worked examples of the import step, the `john/*-ladder` branches show two
shapes end-to-end (gomoku = function-port, robocode = copy-in).

---

## Mechanics you must respect (arena-agnostic)

- **Where human code lives:** each arena has its **own** repo under `CodeClash-ai`
  (hardcoded `GH_ORG` in `codeclash/constants.py`). The arena Dockerfile `git clone`s it
  into `/workspace`. Human bots are **branches of that per-arena repo**, NOT of this
  monorepo — so `git branch -a` here shows no `human/*`.
- **How a branch becomes a player:** a player with `branch_init: human/foo/bar` makes
  `Player.__init__` (`codeclash/agents/player.py`) run `git fetch && git checkout` in the
  clone; that branch's files overlay `/workspace`. `agent: dummy` = static opponent.
  `push: True` (the climbing player) needs `GITHUB_TOKEN`.
- **What a branch must contain:** the arena's **submission file(s)** at the path its
  `validate_code` expects; everything else (engine, assets) comes from the base clone.
  **The single source of truth is `codeclash/arenas/<a>/<a>.py` — read its `submission`
  attribute and `validate_code` method.** Those two define the contract. Examples:
  BattleSnake → `main.py` HTTP server (`info/start/end/move`); Gomoku → `main.py` with
  `get_move(board,color)`; SCML → agent with `decide(observation)`; RoboCode → Java class
  under `robots/custom/`; CoreWar → `warrior.red`.

---

## Phase 0 — Prerequisites

- Arena class `codeclash/arenas/<a>/<a>.py` exists; record its `submission` path + exact
  `validate_code` requirements.
- Arena repo `github.com/CodeClash-ai/<A>` exists and its Dockerfile clones it.
- Docker running; `GITHUB_TOKEN` set (public repos → `gh auth token` works for push + run).

## Phase 1 — Source many human solutions

The hard part is finding a large set. Best sources: official leaderboards and
`awesome-<arena>` repos (BattleSnake used `awesome-battlesnake`; RobotRumble crawled
`robotrumble.org/boards/2`; RoboCode drew from RoboWiki/GitHub). Capture author + bot name
per candidate → these become the branch slugs. Keep a provenance record (source URL,
author, license) as you go — a table plus a header comment in each imported file.

## Phase 2 — Adapt each solution to the arena's contract

Every bot must end up matching the one submission contract. Do NOT discard a bot merely for
being in another language — pick the cheapest import shape:

- **Copy-in** — source is already in the arena's language/framework: drop the files in and
  rename/repackage (e.g. RoboCode: main class → `MyTank`, `package custom;`). Mechanical.
- **Function-contract port** — reimplement the core "given state, choose a move" logic as
  the arena's single entry function (Gomoku `get_move`, SCML `decide`, BattleSnake `move`).
  Ignore the source's GUI/protocol/CLI wrapper; keep its evaluation + search faithful.

Porting hard rules (adapt per arena; worth writing up as a guide for any porting agents):
- **Runtime-only deps** — match the arena image (often stdlib-only Python 3.10; re-express
  array math in pure Python). No trained weights / NN unless you can obtain the binary.
- **One entry point, never raise** — a crash or illegal move = a forfeit; wrap the body and
  fall back to a safe legal move.
- **Fast enough** — a round-robin plays many games; cap search depth / rollouts.
- Only skip a bot if it truly can't run. **Log every skip with a reason — never silently
  drop bots.**

## Phase 3 — Validate (two-stage), then push

Local validation is necessary but NOT sufficient — a local shim skips Docker, the repo's
`server.py`, and real payloads. Gate every bot in two stages before it earns a branch:

1. **Stage 1 (local):** syntax/import + the arena's `validate_code` legality check. Cheap;
   catches most breakage without Docker. Fix or drop failures.
2. **Stage 2 (arena, REQUIRED):** play each stage-1 pass through the real arena image and
   confirm it completes a full game without erroring. This is the step that actually gates.
   Requires Docker. (Scripting both stages over a folder of candidates is worth it at scale.)
3. **Push** each stage-2-healthy bot as `human/<author>/<name>` (dedupe identical content).
   Use consistent kebab/lowercase slugs; branches must be pushed before any arena run, since
   `branch_init` fetches from the remote.

## Phase 4 — Make the ladder (round-robin + Elo)

1. Write `configs/ablations/ladder/make_<a>.yaml` (mirror `make_battlesnake.yaml`):
   `tournament.rounds: 0`, a `game` block, and `players:` = every `human/*` branch as
   `{agent: dummy, branch_init: ...}`.
2. Pre-build the image **once** to avoid a build stampede under many workers:
   `docker build -t codeclash/<a> -f codeclash/arenas/<a>/<A>.Dockerfile .`
3. Run all-pairs PvP (resumable — skips pairs already logged; `--workers ≈ cores-2`):
   `GITHUB_TOKEN=$(gh auth token) uv run codeclash ladder make configs/ablations/ladder/make_<a>.yaml --workers N`
   → logs land under `logs/ladder/<A>/`. Fast arenas run on a laptop; big ones (e.g. SCML's
   ~1275 pairs) want an AWS box under `tmux`/`nohup`.
4. Rank: `uv run python -m codeclash.analysis.metrics.elo -d logs/ladder/<A> --include-round-0 --output-dir assets/<a>_elo`
   → prints the Bradley-Terry/Elo order (weakest → strongest); that ordering IS the ladder.
   - **`--include-round-0` is REQUIRED for ladder construction.** `ladder make` uses
     `tournament.rounds: 0`, so round 0 IS the match; without the flag every tournament is
     dropped (round 0 is normally the excluded identical-codebases baseline) and the fit
     crashes on an empty matrix. Do NOT pass it for normal multi-round PvP/climbing Elo.
   - Use `uv run python`, not bare `python` — the analysis deps (matplotlib) live in the uv venv.
   - Tip: run a cheap low-`sims` pilot first and eyeball that baselines sit near the bottom.

## Phase 5 — Assemble the ranked configs

1. `configs/ablations/ladder/rungs/<a>.yaml` — the ranked opponents, **weakest first,
   strongest last** (each `{agent: dummy, branch_init: human/...}`), in Elo order.
2. `configs/ablations/ladder/<a>.yaml` — the climber `player` (starting at the weakest
   rung, `push: True`) + `ladder: !include ablations/ladder/rungs/<a>.yaml` + a
   `ladder_rules` block. Model on `battlesnake.yaml`.
3. Optional `<a>__<model>.yaml` per-model variants (swap `model: !include mini/models/...`);
   they share the same `rungs/<a>.yaml` include.

`ladder_rules` (optional; defaults reproduce historical behavior):
```yaml
ladder_rules:
  min_round_win_fraction: 0.5   # must win strictly more than this fraction of rounds
  win_last_k: 1                 # ...and must win the last K rounds
```

## Phase 6 — Run the ladder

`uv run codeclash ladder run configs/ablations/ladder/<a>.yaml`
→ prints the highest rung reached; logs under `LOCAL_LOG_DIR/<user>/LadderTournament.*`.

---

## Deliverables checklist
- [ ] N validated `human/<author>/<name>` branches pushed to `CodeClash-ai/<A>`.
- [ ] **Stage-2 arena smoke passed** (each bot plays a real game in Docker), skips logged.
- [ ] `make_<a>.yaml` + round-robin run + Elo ranking (`assets/<a>_elo`).
- [ ] `rungs/<a>.yaml` (weakest→strongest) + `<a>.yaml` (climber + `ladder_rules`).
- [ ] `ladder run` executes end-to-end against a sample model.
- [ ] Provenance recorded (source/author/license per bot); note in `ladder/README.md` if
      the arena is new.

## Gotchas
- Human branches go to the **per-arena** repo, not the monorepo; `branch_init` fetches from
  the remote, so **push before any run** and keep Docker up.
- A bot that fails `validate_code` silently forfeits. A local shim can pass yet fail in the
  arena — the **stage-2 Docker smoke** is the real gate, not stage 1.
- Pre-build the arena image once before a `--workers N` run, or workers stampede the build.
- Port aggressively into the single submission contract; skip only un-runnable bots, and
  log every skip. A port must reproduce the original's behavior.
