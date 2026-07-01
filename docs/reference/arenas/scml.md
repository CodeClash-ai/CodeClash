# SCML

Supply-chain negotiation arena based on the ANAC Supply Chain Management League OneShot track.

## Overview

SCML simulates a supply chain in which autonomous factory-manager agents negotiate contracts to buy
and sell goods. The CodeClash arena uses the SCML2024 OneShot world because it focuses on negotiation
and profit without requiring long-term production scheduling.

Each CodeClash player edits a restricted SCML decision policy. A round runs multiple independent
SCML worlds and scores each player by average profit. The trusted runtime owns the SCML agent object,
world state, and validation; submitted code only receives plain observations and returns negotiation
intents.

## Resources

- [SCML Official Site](https://scml.cs.brown.edu/)
- [SCML Documentation](https://scml.readthedocs.io/)

## Implementation

::: codeclash.arenas.scml.scml.SCMLOneShotArena
    options:
      show_root_heading: true
      heading_level: 2

## Agent Interface

Your bot must be a Python file named `scml_agent.py` that defines `decide(observation)`.

Return `{}` or `None` to use the trusted greedy fallback. A valid starting point is:

```python
def decide(observation):
    return {}
```

For proposal events, return `{"offer": [quantity, time, unit_price]}`. The runtime validates that
the offer is inside SCML's current issue ranges before sending it to the simulator. For response
events, return `{"response": "accept"}`, `{"response": "reject"}`, or `{"response": "end"}`.
Invalid decisions fall back to the trusted greedy policy and are recorded in round details.

## Configuration Example

```yaml
tournament:
  rounds: 1
game:
  name: SCML
  sims_per_round: 2
  n_steps: 5
  n_lines: 2
  decision_timeout: 3.0
  max_policy_errors: 8
  validation_timeout: 10
  timeout: 240
players:
  - agent: dummy
    name: alpha
  - agent: dummy
    name: beta
```

## Scoring

The arena runs `sims_per_round` independent SCML2024 OneShot worlds. Each world has two supply-chain
process levels; every CodeClash player controls one trusted SCML wrapper agent at each level so the
submitted policies participate in actual buy/sell negotiations. The final per-world player score is
the mean SCML score across that player's controlled agents, and the final CodeClash score is the
average across worlds.

The runner rotates player ordering across simulations to reduce positional bias from factory
assignment.

## Smoke Test

From the repository root, run the dummy-player example:

```bash
uv run python main.py configs/examples/SCML__dummy__r1__s2.yaml -o /tmp/codeclash-scml-smoke
```

Use a fresh `-o` directory when rerunning the smoke check.

Expected shape:

- the command exits with status 0;
- both players pass submission validation;
- stdout includes `In round 0, the winner is ...` and `In round 1, the winner is ...`;
- each round summary contains floating-point average scores for `alpha` and `beta`;
- per-simulation details include `decisions`, `policy_errors`, `invalid_decisions`,
  `disabled_policies`, and `policy_error_samples`;
- the output directory contains `metadata.json`, `game.log`, `tournament.log`, and
  `rounds/round_0.tar.gz` / `rounds/round_1.tar.gz`.

A representative `metadata.json` round contains a `scores` object with one floating-point SCML
profit score per player:

```json
"scores": {
  "alpha": 0.6536304953204003,
  "beta": 0.5384855419684607
}
```

Exact values can change with simulation order and configuration; the smoke check is meant to verify
the Docker/runtime adapter path, player-name mapping, and score/log artifact shape.

The exact tournament directory name includes a timestamp, so inspect the metadata with:

```bash
find /tmp/codeclash-scml-smoke -maxdepth 3 -name metadata.json -print
```

--8<-- "docs/_footer.md"
