# CC:Ladder

For a more static and hill-climb-able version of CodeClash, we introduce CC:Ladder - for each arena, we curate a collection of human-written solutions, determine their relative rankings, and then see how "high up" the ladder models can climb.

For instance, for RobotRumble, we created a ladder by doing the following steps:
1. From the online [leaderboard](https://robotrumble.org/boards/2), we manually crawled all open source, published bots and pushed them as branches to the [CC:RobotRumble](https://github.com/CodeClash-ai/RobotRumble) repository.
2. We then created the `robotrumble.yaml` file in this folder.
3. Next, from the repository root, we run `uv run codeclash ladder run configs/ladder/robotrumble.yaml`, which runs PvP Tournaments against all pairs of branches.
4. From these logs, we then calculate win rate to rank all models.

You can follow these steps to create your own "CC:<arena>" ladder.
The tricky part is typically finding a large collection of human solutions for a particular arena.
We've typically found that googling for online leaderboards or awesome-<arena> repositories (e.g. [BattleSnake](https://github.com/BattlesnakeOfficial/awesome-battlesnake)) is a good strategy.

### Gomoku (newly added)

The [CC:Gomoku](https://github.com/CodeClash-ai/Gomoku) repo hosts the human bots on `human/*`
branches (like the other arenas, bot code lives only on the branches, not in this repo): 21
open-source Gomoku/Gobang AIs ported into the arena's single-file `get_move(board, color)` contract
— pure-Python minimax/MCTS/threat-search bots imported directly, plus JS/Java/C++ engines (e.g.
lihongxun945, blackstone, blupig) reimplemented in stdlib Python — alongside a strategic starter.
AlphaZero/CNN bots were skipped (need trained weights).

### RoboCode (newly added)

The [CC:RoboCode](https://github.com/CodeClash-ai/RoboCode) repo hosts 116 human bots on `human/robocode/*`
branches (bot code lives only on the branches, not in this repo). This arena is **classic Robocode**
(`robocode.*` API compiled against `robocode.jar`), so importing open-source bots is mostly a
mechanical copy-in + rename rather than a strategy rewrite: each bot's Java class(es) are placed in
`robots/custom/`, the main class renamed to `MyTank`, `package custom;`. The set spans the shipped
sample bots (SittingDuck/Walls/Corners/…) through famous RoboWiki/PEZ micro-mini bots (Aristocles,
Pugilist, HawkOnFire) up to a single-file **DrussGT** (a world-class bot) as the top rung; a few use
Robocode's sanctioned `getDataFile` persistence (degrades gracefully without cross-battle saves).
Diamond/BeepBoop remain as future top rungs (nested-package multi-file → need flattening). Each import
was verified to **compile and play a real battle**; every bot's source repo/author/license is recorded
as a header comment in its branch files.

## Config layout

Each arena has a few kinds of config in this folder:

- `make_<arena>.yaml` — the round-robin used to **build** the ladder (`ladder make`), running PvP tournaments across all pairs of human bots to rank them.
- `<arena>.yaml` — the **run** config (`ladder run`): a climber ascends the ranked ladder rung by rung until it loses.
- `<arena>__<model>.yaml` — per-model run configs (e.g. `battlesnake__opus_4_8.yaml`) that swap in a specific model via `model: !include mini/models/llama_<model>.yaml`.
- `rungs/<arena>.yaml` — the ranked opponent list (worst first, strongest last), shared by both `<arena>.yaml` and every `<arena>__<model>.yaml` through `ladder: !include ladder/rungs/<arena>.yaml`. Edit the ladder in this one file and every config for that arena picks it up.

## Ladder advancement rule (`ladder_rules`)

Each run config carries a `ladder_rules` block controlling what it takes to clear a rung and continue climbing:

```yaml
ladder_rules:
  min_round_wins: 2   # must win >= this many of the agent rounds to advance (round 0 excluded)
  win_last_k: 0       # ...and must win the last K rounds (1 == just the final round, 0 == disabled)
```

These keys are read only by `codeclash ladder run`; a plain PvP `codeclash run` rejects any config that carries a `ladder_rules` block (so `early_clinch`/`fast_forward` can't silently no-op there).

Both keys are **required** — there are no defaults; a config that omits either one errors out. `min_round_wins` is a whole number: the player advances when `player_wins >= min_round_wins`. Round 0 (before any edits against the opponent — identical codebases at the first rung, carried-over at later rungs) is excluded, so with `tournament.rounds: 5` there are 5 scored agent rounds (rounds 1–5). Validation:

- `min_round_wins` must be an integer with `1 <= min_round_wins <= tournament.rounds`.
- `win_last_k` must be an integer with `0 <= win_last_k <= min_round_wins`. `0` **disables** the trailing-rounds requirement; `1` means "just win the final round".

### Fast-forward (optional)

Since the north-star metric is *the highest rung a bot can reach*, you can skip the (usually redundant) grind of playing edit rounds against opponents your carried-over bot already crushes:

```yaml
ladder_rules:
  min_round_wins: 2
  win_last_k: 0
  fast_forward:
    enabled: true
    min_sim_win_rate: 0.9   # skip a rung if the bot wins >= 90% of that rung's round-0 sims
```

At each rung, a **round-0-only probe** runs the carried-over bot against the opponent. If the climber wins at least `min_sim_win_rate` of the simulations (ties count as non-wins), the rung is **cleared without playing edit rounds** and recorded with `ladder_advancement.fast_forwarded: true`. Any rung *not* cleanly won still plays in full under the normal `ladder_rules`, so this is safe under non-transitive matchups and never skips a rung it would actually lose. Rung 1 is identical-code (~coin flip at round 0), so it never fast-forwards — the climber always has to earn the first rung. Omit the block (or `enabled: false`) for today's full-play behavior. Validation: `enabled` is a bool (required if the block is present); `min_sim_win_rate` is a number in `(0.5, 1.0]` (required when enabled).

### Early clinch (optional)

Where fast-forward skips a rung entirely, `early_clinch` stops a rung mid-way once the outcome is decided — the climber has already won `min_round_wins` rounds, so the remaining rounds can't change whether it advances:

```yaml
ladder_rules:
  min_round_wins: 2
  win_last_k: 0
  early_clinch: true
```

The rung plays rounds normally and breaks the moment `player_wins >= min_round_wins`; advancement is recorded from the rounds actually played. Requires `win_last_k == 0` — a trailing-rounds requirement can't be satisfied before the final round, so the two can't be combined (validation errors otherwise). Composes with `fast_forward` (probe first, then early-clinch the rounds that do get played). Off by default.
