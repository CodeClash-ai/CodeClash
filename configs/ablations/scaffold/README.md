# Scaffold / Harness Ablation

This folder defines a concrete experiment matrix for answering:

1. How much of CodeClash performance is due to the model versus the agent harness?
2. Do Codex-style agent stacks help because of the scaffold alone, or because the model and scaffold are co-designed?

## Current repository limitation

Today this repository only exposes two agent types:

- `mini`
- `dummy`

See `codeclash/agents/__init__.py`.

That means the experiments below are split into:

- `ready_now`: Can be run once the referenced model exists in `configs/models.yaml`
- `blocked_on_adapter`: Requires adding a new agent adapter for `swe-agent`, `openhands`, or `codex-sdk`

## Design rules

All harness comparisons should keep the following fixed unless the experiment explicitly says otherwise:

- same arena
- same opponent panel
- same model
- same number of rounds
- same per-round step limit
- same per-round dollar limit
- same tool surface
- same repository snapshot
- same visibility into logs and docs
- same replication count

Do not give one harness extra tools, hidden memory, or a longer prompt unless that is the variable under test.

## Phases

### Phase A: Cheap scaffold-only screen

Purpose:
Measure scaffold effects while holding the model fixed.

System under test:

- model: `@openai/gpt-5-mini`
- harnesses:
  - `mini` (existing baseline)
  - `swe-agent` (planned)
  - `openhands` (planned)
  - `codex-sdk` (planned thin adapter, not the full Codex product stack)

Opponents:

- `@anthropic/claude-sonnet-4-5-20250929`
- `@openai/o3`
- `@x-ai/grok-code-fast-1`

Arenas:

- `BattleSnake` (`r5`, `s1000`)
- `CoreWar` (`r5`, `s1000`)
- `RobotRumble` (`r5`, `s250`)

Replications:

- `2` independent tournaments per cell

Run count:

- `4 harnesses x 3 opponents x 3 arenas x 2 reps = 72 tournaments`

Advance rule:

- Promote the best two harnesses by pooled Elo / win rate
- Require no obvious regression in validation rate, bash success, or recovery after failure

### Phase B: Cheap Codex stack test

Purpose:
Separate generic scaffold effects from model-stack co-design.

Systems:

- `best_generic_harness + @openai/gpt-5-mini`
- `best_generic_harness + @openai/gpt-5.1-codex-mini`
- `codex-sdk + @openai/gpt-5.1-codex-mini`

Opponents:

- same as Phase A

Arenas:

- same as Phase A

Replications:

- `2` independent tournaments per cell

Run count:

- `3 systems x 3 opponents x 3 arenas x 2 reps = 54 tournaments`

Interpretation:

- If `codex-sdk + gpt-5.1-codex-mini` beats `best_generic_harness + gpt-5.1-codex-mini`, the scaffold matters.
- If `best_generic_harness + gpt-5.1-codex-mini` already captures most of the gain, the model matters more than the scaffold.

### Phase C: Expensive confirmation

Purpose:
Confirm the screen on a stronger model after the cheap runs identify promising cells.

Systems:

- top `2` systems from Phase B

Model:

- `@openai/gpt-5.4`

Opponents:

- `@anthropic/claude-sonnet-4-5-20250929`
- `@openai/o3`

Arenas:

- all six benchmark arenas

Tournament budget:

- `r15`
- standard paper simulation counts per arena

Replications:

- `1` independent tournament per cell

Run count:

- `2 systems x 2 opponents x 6 arenas x 1 rep = 24 tournaments`

## Primary metrics

- pooled Elo
- per-arena Elo
- head-to-head win rate excluding ties
- top-1 consistency under bootstrap
- pairwise order agreement under bootstrap

## Diagnostic metrics

- bash/action success rate
- next-step recovery after failed command
- fraction of rounds with grounded edits
- fraction of rounds with simulation-based validation
- fraction of rounds with unit-test validation
- mean files edited per round
- mean thought length / steps per round

## Minimum logging requirements

For every tournament, retain:

- `metadata.json`
- trajectories
- per-round diffs
- round stats
- cost and API call counts

For scaffold adapters, also log:

- prompt template used
- tool whitelist / sandbox mode
- whether notes persist across rounds
- any harness-specific retries or auto-fixes

## Why this matrix

This matrix deliberately starts with cheap screening. `GPT-5.4` should only be used after the cheap phase narrows the search space. The point is not to prove that one harness wins one benchmark snapshot; the point is to isolate whether improvements survive when model, budget, and arena are held fixed.
