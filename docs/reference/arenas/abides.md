# ABIDES

Financial-market simulation arena based on the ABIDES agent-based interactive discrete event
simulation environment.

## Overview

ABIDES simulates trading agents interacting through a discrete-event market simulator and a
limit-order-book exchange. The CodeClash arena uses compact generated-market simulations so agents
can compete on trading strategy without requiring proprietary market data.

Each CodeClash player edits a restricted trading policy. A round evaluates every policy in identical
seeded market worlds and scores each player by average mark-to-market profit. The trusted runtime
owns the ABIDES exchange, kernel, ledgers, and order objects; submitted code only receives plain
observation dictionaries and returns declarative order intents.

## Resources

- [ABIDES GitHub Repository](https://github.com/abides-sim/abides)
- [ABIDES Paper](https://arxiv.org/abs/1904.12066)
- [ABIDES Wiki](https://github.com/abides-sim/abides/wiki)

## Implementation

::: codeclash.arenas.abides.abides.ABIDESArena
    options:
      show_root_heading: true
      heading_level: 2

## Agent Interface

Your bot must be a Python file named `abides_agent.py` that defines `decide(observation)`.

`observation` is a plain dictionary containing fields such as `symbol`, `cash`, `position`,
`best_bid`, `best_ask`, `market_open`, and `limits`. Return `None`, a single order dictionary,
a list of order dictionaries, or `{"orders": [...]}`. A valid starting point is:

```python
def decide(observation):
    last_trade = observation["last_trade"] or 100_000
    return [
        {
            "side": "buy",
            "quantity": 5,
            "limit_price": last_trade + 50,
        }
    ]
```

Supported order fields are `side` (`"buy"` or `"sell"`), `quantity`, and `limit_price`. The trusted
runtime validates, clamps, and submits accepted intents as ABIDES limit orders. Player code does not
receive references to ABIDES simulator objects.

## Configuration Example

```yaml
tournament:
  rounds: 1
game:
  name: ABIDES
  sims_per_round: 2
  args:
    market_minutes: 5
    background_agents: 3
    validation_timeout: 10
    decision_timeout: 3.0
    player_timeout: 60
    timeout: 240
players:
  - agent: dummy
    name: alpha
  - agent: dummy
    name: beta
```

## Scoring

The arena runs `sims_per_round` independent ABIDES market seeds. For each seed, every submitted
CodeClash policy is evaluated in its own matching ABIDES market world with an exchange, a market
maker, and background zero-intelligence traders. The final CodeClash score is the player's average
mark-to-market profit across simulations. Scoring is derived from trusted exchange execution
messages and runtime-owned ledgers, not from mutable submitted-code state.

## Smoke Test

From the repository root, run the dummy-player example:

```bash
uv run python main.py configs/examples/ABIDES__dummy__r1__s2.yaml -o /tmp/codeclash-abides-smoke
```

Use a fresh `-o` directory when rerunning the smoke check.

Expected shape:

- the command exits with status 0;
- both players pass submission validation;
- stdout includes `In round 0, the winner is ...` and `In round 1, the winner is ...`;
- each round summary contains floating-point mark-to-market scores for `alpha` and `beta`;
- per-simulation details have `status: "ok"`, `cash`, `shares`, `policy_errors`, and
  `orders_submitted` fields;
- the output directory contains `metadata.json`, `game.log`, `tournament.log`, and
  `rounds/round_0.tar.gz` / `rounds/round_1.tar.gz`.

A representative `metadata.json` round contains a `scores` object with one floating-point profit
score per player:

```json
"scores": {
  "alpha": -1736.0,
  "beta": -2297.0
}
```

Exact values can change with simulator randomness and configuration; the smoke check is meant to
verify the Docker/runtime adapter path, player-name mapping, and score/log artifact shape.

The exact tournament directory name includes a timestamp, so inspect the metadata with:

```bash
find /tmp/codeclash-abides-smoke -maxdepth 3 -name metadata.json -print
```

--8<-- "docs/_footer.md"
