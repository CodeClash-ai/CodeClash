# Running the RoboCode round-robin (Elo ranking)

Rank the human bots in `configs/ablations/ladder/make_robocode.yaml` via all-pairs battles, then fit
Elo. Each pair plays `sims_per_round` battle-rounds (the arena batches them `SIMS_PER_RUN=10` at a
time, `sim_concurrency` in parallel). Battles are headless Java; cost is moderate — measure one pair
first (below) to size the full run. Bots live on `CodeClash-ai/RoboCode` `human/*` branches;
`branch_init` fetches them at runtime, so you only need this repo branch + Docker + a GitHub token.

## Prerequisites
- Docker running, git, `uv`, and a token for `CodeClash-ai/RoboCode` (public → `gh auth token`).

## Step 0 — pre-build the arena image once (avoids a build stampede under -w N)
```bash
docker build -t codeclash/robocode -f codeclash/arenas/robocode/RoboCode.Dockerfile .
```

## Step 1 — round-robin
`N` bots → `N*(N-1)/2` pairs. Keep `--workers ≈ cores-2`. Resumable (skips logged pairs).
```bash
GITHUB_TOKEN=$(gh auth token) \
  uv run codeclash ladder make configs/ablations/ladder/make_robocode.yaml --workers 6
```
Tip: time one pair first to size the run — e.g. run a 2-player `codeclash run` config and note the
wall time, then multiply by pair count / workers.

## Step 2 — rank
```bash
python -m codeclash.analysis.metrics.elo -d logs/ladder/RoboCode --output-dir assets/robocode_elo
```
Prints the Bradley-Terry/Elo ordering and writes `assets/robocode_elo/elo_results.log`.

## Step 3 — assemble the ladder configs (once you have the ranking)
1. `configs/ablations/ladder/rungs/robocode.yaml` — ranked opponents, weakest first, strongest last.
2. `configs/ablations/ladder/robocode.yaml` — climber `player` + `ladder: !include ablations/ladder/rungs/robocode.yaml`
   + a `ladder_rules` block (model on `battlesnake.yaml`).
3. Optional `robocode__<model>.yaml` per-model variants.
