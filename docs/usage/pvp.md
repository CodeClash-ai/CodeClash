# PvP Tournament

A PvP tournament pits two or more agents against each other over several edit-and-compete rounds.
Each round, every agent edits its own codebase, then all agents play the game.
The winner is whoever takes the most rounds.

## Run one

```bash
uv run codeclash run <config.yaml>
```

```bash
# Basic run
uv run codeclash run configs/pvp/BattleSnake__claude-sonnet-4-5-20250929__o3__r15__s1000.yaml

# Keep containers around for debugging
uv run codeclash run configs/test/battlesnake.yaml -k

# Custom output dir + suffix
uv run codeclash run configs/my_config.yaml -o ./experiments -s trial1
```

Options: `-c/--cleanup`, `-o/--output-dir`, `-s/--suffix`, `-k/--keep-containers`.

## Minimal config

```yaml
tournament:
  rounds: 5
game:
  name: BattleSnake
  sims_per_round: 1000
players:
- agent: mini
  name: claude
  config:
    agent: !include mini/default.yaml
    model:
      model_name: '@anthropic/claude-sonnet-4-5-20250929'
- agent: mini
  name: o3
  config:
    agent: !include mini/default.yaml
    model:
      model_name: '@openai/o3'
prompts:
  game_description: |
    You are competing in BattleSnake...
```

For every config field, arena args, env vars, and the output layout, see [Running Tournaments](tournaments.md).

## `ladder_rules` doesn't apply here

`ladder_rules` (`min_round_wins`, `win_last_k`, `early_clinch`, `fast_forward`) is only read by `codeclash ladder run`.
`codeclash run` rejects any config that includes it, so those settings can't silently do nothing in a PvP run.
See [Ladder Tournament](ladder.md).

--8<-- "docs/_footer.md"
