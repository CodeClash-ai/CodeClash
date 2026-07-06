# Running the SCML round-robin (Elo ranking) on AWS

Goal: run the 1,275-pair round-robin in `make_scml.yaml` to rank the 51 human bots, then
compute Elo and assemble the ladder. The 51 bots already live on `CodeClash-ai/SCML` as
`human/*` branches — `branch_init` fetches them at runtime, so nothing bot-side needs shipping;
you only need this repo branch + Docker + a GitHub token.

## Prerequisites on the AWS box
- Docker running (`docker info`), git, and `uv` (repo uses `uv run codeclash ...`).
- A GitHub token with read access to `CodeClash-ai/SCML` (public, so a default `gh auth token`
  or any classic PAT works). Export it as `GITHUB_TOKEN` for the run.
- This branch pulled: `git fetch && git checkout <branch> && uv sync` (or the repo's usual setup).

## Step 0 — pre-build the arena image ONCE (avoids a build stampede)
`ladder make --workers N` builds the image lazily per pair; with many workers they'd all try to
build at once. Build it a single time up front (it `git clone`s CodeClash-ai/SCML and installs
`scml==0.8.2`):

```bash
docker build -t codeclash/scml -f codeclash/arenas/scml/SCML.Dockerfile .
```

Sanity check one pair end-to-end before the big run:

```bash
bash scripts/ladder/smoke_scml.sh   # greedy vs dummy, should print PASS
```

## Step 1 (recommended) — cheap pilot ranking (~1 h on 32 cores)
Edit `configs/ablations/ladder/make_scml.yaml`: comment out `sims_per_round: 400`, uncomment
`sims_per_round: 30`. Then:

```bash
GITHUB_TOKEN=$(gh auth token) \
  uv run codeclash ladder make configs/ablations/ladder/make_scml.yaml --workers 30
python -m codeclash.analysis.metrics.elo -d logs/ladder/SCML --output-dir assets/scml_elo_pilot
```

Eyeball the printed Elo ordering: the baselines (`nice` < `random` < `greedy`) should sit near
the bottom, and disciplined bots should outrank very concessive ones. If it looks sane, proceed.
(The pilot logs live in a different pair-count than the full run only in `sims`; to force fresh
full-sim logs, run the full pass in a clean `logs/` or a separate `-o` dir — see note below.)

## Step 2 — full ranking run (400 sims, ~23 h on 32 cores)
Restore `sims_per_round: 400` in the config, then launch under `nohup`/`tmux` so it survives
disconnects:

```bash
tmux new -s scml
GITHUB_TOKEN=$(gh auth token) \
  uv run codeclash ladder make configs/ablations/ladder/make_scml.yaml --workers 30 \
  2>&1 | tee scml_make.log
# detach: Ctrl-b d   |   reattach: tmux attach -t scml
```

- **Resumable:** each pair writes to `logs/ladder/SCML/PvpTournament.<a>_vs_<b>/`; a rerun skips
  pairs whose folder already exists. Safe to stop/restart. If it dies, just relaunch the same
  command — it continues where it left off.
- **`--workers 30`** on a 32-core box (leave 2 cores headroom; the `decide` 3s timeout can trip
  under CPU oversubscription). Progress = count of `logs/ladder/SCML/PvpTournament.*` dirs
  (target 1275): `ls -d logs/ladder/SCML/PvpTournament.* | wc -l`.

> NOTE on pilot→full log mixing: if you ran the Step-1 pilot into `logs/`, move or delete
> `logs/ladder/SCML/` before the full run (or point the pilot elsewhere) so the Elo fit uses only
> the 400-sim results. The make command has no `-o`; it always writes under `logs/ladder/<Arena>/`.

## Step 3 — compute Elo and rank
```bash
python -m codeclash.analysis.metrics.elo -d logs/ladder/SCML --output-dir assets/scml_elo
```
Prints the Bradley-Terry/Elo ranking and writes `assets/scml_elo/elo_results.log` (+ plots,
LaTeX/website tables). The ordering is what becomes the ladder (weakest → strongest).

## Step 4 — assemble the ladder configs (do this once you have the ranking)
1. `configs/ablations/ladder/rungs/scml.yaml` — the ranked opponent list, worst first, strongest
   last (each `{agent: dummy, branch_init: human/...}`), in Elo order from Step 3.
2. `configs/ablations/ladder/scml.yaml` — the run config: a climbing `player` (starting at the
   weakest rung) + `ladder: !include ablations/ladder/rungs/scml.yaml` + a `ladder_rules` block.
   Model on `battlesnake.yaml`.
3. Optional `scml__<model>.yaml` per-model variants (swap `model: !include mini/models/...`).

(Ping me with `logs/ladder/SCML/` or the `elo_results.log` and I'll generate the rungs + run
configs automatically.)
