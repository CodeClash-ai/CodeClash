# CC:Ladder

For a more static and hill-climb-able version of CodeClash, we introduce CC:Ladder - for each arena, we curate a collection of human-written solutions, determine their relative rankings, and then see how "high up" the ladder models can climb.

For instance, for RobotRumble, we created a ladder by doing the following steps:
1. From the online [leaderboard](https://robotrumble.org/boards/2), we manually crawled all open source, published bots and pushed them as branches to the [CC:RobotRumble](https://github.com/CodeClash-ai/RobotRumble) repository.
2. We then created the `robotrumble.yaml` file in this folder.
3. Next, from the repository root, we run `uv run codeclash ladder run configs/ablations/ladder/robotrumble.yaml`, which runs PvP Tournaments against all pairs of branches.
4. From these logs, we then calculate win rate to rank all models.

You can follow these steps to create your own "CC:<arena>" ladder.
The tricky part is typically finding a large collection of human solutions for a particular arena.
We've typically found that googling for online leaderboards or awesome-<arena> repositories (e.g. [BattleSnake](https://github.com/BattlesnakeOfficial/awesome-battlesnake)) is a good strategy.

## Config layout

Each arena has a few kinds of config in this folder:

- `make_<arena>.yaml` — the round-robin used to **build** the ladder (`ladder make`), running PvP tournaments across all pairs of human bots to rank them.
- `<arena>.yaml` — the **run** config (`ladder run`): a climber ascends the ranked ladder rung by rung until it loses.
- `<arena>__<model>.yaml` — per-model run configs (e.g. `battlesnake__opus_4_8.yaml`) that swap in a specific model via `model: !include mini/models/llama_<model>.yaml`.
- `rungs/<arena>.yaml` — the ranked opponent list (worst first, strongest last), shared by both `<arena>.yaml` and every `<arena>__<model>.yaml` through `ladder: !include ablations/ladder/rungs/<arena>.yaml`. Edit the ladder in this one file and every config for that arena picks it up.

## Ladder advancement rule (`ladder_rules`)

Each run config carries a `ladder_rules` block controlling what it takes to clear a rung and continue climbing:

```yaml
ladder_rules:
  min_round_win_fraction: 0.5   # must win strictly more than this fraction of rounds
  win_last_k: 1                 # ...and must win the last K rounds (1 == just the final round)
```

The defaults shown above reproduce the historical behavior (strict majority of rounds **and** win the final round); the block is optional and falls back to these values if omitted. Validation:

- `win_last_k` must be an integer with `1 <= win_last_k <= tournament.rounds`.
- `min_round_win_fraction` must be a number in `[0, 1)`; `0` drops the majority requirement (e.g. `min_round_win_fraction: 0` + `win_last_k: 1` means "just win the final round").
