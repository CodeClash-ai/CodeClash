# Running the Gomoku round-robin (Elo ranking)

Rank the human bots in `configs/ablations/ladder/make_gomoku.yaml` via all-pairs PvP, then fit
Elo. Gomoku games are fast and stdlib-only, so — unlike SCML — this runs comfortably **on a
laptop** (no AWS needed). The bots already live on `CodeClash-ai/Gomoku` `human/*` branches;
`branch_init` fetches them at runtime, so you only need this repo branch + Docker + a GitHub token.

## Prerequisites
- Docker running, git, `uv`, and a token for `CodeClash-ai/Gomoku` (public → `gh auth token` works).

## Step 0 — pre-build the arena image once (avoids a build stampede under -w N)
```bash
docker build -t codeclash/gomoku -f codeclash/arenas/gomoku/Gomoku.Dockerfile .
bash scripts/ladder/smoke_gomoku.sh    # sanity: reference vs default, prints PASS
```

## Step 1 — round-robin
`N` bots → `N*(N-1)/2` pairs; each pair is a short match, so this is quick. Keep
`--workers ≈ cores-2`.
```bash
GITHUB_TOKEN=$(gh auth token) \
  uv run codeclash ladder make configs/ablations/ladder/make_gomoku.yaml --workers 6
```
Resumable — reruns skip pairs already logged under `logs/ladder/Gomoku/`.

## Step 2 — rank
```bash
python -m codeclash.analysis.metrics.elo -d logs/ladder/Gomoku --output-dir assets/gomoku_elo
```
Prints the Bradley-Terry/Elo ordering and writes `assets/gomoku_elo/elo_results.log`.

## Step 3 — assemble the ladder configs (once you have the ranking)
1. `configs/ablations/ladder/rungs/gomoku.yaml` — ranked opponents, weakest first, strongest last.
2. `configs/ablations/ladder/gomoku.yaml` — climber `player` + `ladder: !include ablations/ladder/rungs/gomoku.yaml`
   + a `ladder_rules` block (model on `battlesnake.yaml`).
3. Optional `gomoku__<model>.yaml` per-model variants.
