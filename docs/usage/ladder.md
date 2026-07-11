# Ladder Tournament

A ladder is a ranked list of opponents, weakest first.
One model (the "climber") plays them one rung at a time and keeps going until it fails to advance.
Its score is how high it climbs.

## Two commands

Build the ladder once — ranks the human bots by round-robin:

```bash
uv run codeclash ladder make configs/ladder/make_battlesnake.yaml
```

Then send a model up it:

```bash
uv run codeclash ladder run configs/ladder/battlesnake__opus_4_8.yaml
```

Resume an interrupted climb from its log dir (needs `push: True`):

```bash
uv run codeclash ladder run configs/ladder/battlesnake__opus_4_8.yaml -r logs/<user>/LadderTournament...
```

Options: `-c/--cleanup`, `-o/--output-dir`, `-s/--suffix`, `-k/--keep-containers`, `-r/--resume`.

## Minimal run config

```yaml
tournament:
  rounds: 5
ladder_rules: !include ladder/ladder_rules.yaml
game:
  name: RobotRumble
  sims_per_round: 250
player:
  agent: mini
  name: claude-sonnet-4-5
  branch_init: human/anton/anton3000
  config:
    agent: !include mini/default.yaml
    model:
      model_name: anthropic/claude-sonnet-4-5-20250929
  push: True
prompts: !include ladder/ladder_prompt.yaml
ladder: !include ladder/rungs/robotrumble.yaml
```

`ladder` is the ranked opponent list; `player` is the climber.

## Advancement settings (`ladder_rules`)

These live in `configs/ladder/ladder_rules.yaml` and decide what it takes to clear a rung.

**`min_round_wins`** (required)
How many rounds the climber must win to move up a rung.
Round 0, before any edits, doesn't count.

**`win_last_k`** (required)
Also require winning the last `k` rounds — `1` means just the final round.
Set to `0` to turn this off.

**`early_clinch`** (optional)
Stop a rung early the moment the climber has already won `min_round_wins` rounds.
Saves time, and the outcome is identical to playing every round.
Only allowed when `win_last_k` is `0`.

**`fast_forward`** (optional)
Skip a rung entirely if the climber already crushes it before making any edits.
It plays only round 0; if the climber wins at least `min_sim_win_rate` of the sims, the rung clears.

## Copy-paste examples

Win 2+ of `n` rounds:

```yaml
min_round_wins: 2
win_last_k: 0
```

Win 2+ rounds, and the final round must be one of them:

```yaml
min_round_wins: 2
win_last_k: 1
```

Fastest eval:

```yaml
min_round_wins: 2
win_last_k: 0
early_clinch: true
fast_forward:
  enabled: true
  min_sim_win_rate: 0.9
```

* Win 2+ of `n` rounds
* `early_clinch`: If the model wins 2 rounds before playing all `n`, skip remaining rounds
* `fast_forward`: If the model's current solution beats the next opponent, skip playing that opponent all together.

--8<-- "docs/_footer.md"
