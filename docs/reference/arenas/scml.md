# SCML

Supply-chain negotiation arena based on the ANAC Supply Chain Management League OneShot track.

## Overview

SCML simulates a supply chain in which autonomous factory-manager agents negotiate contracts to buy
and sell goods. The CodeClash arena uses the SCML2024 OneShot world because it focuses on negotiation
and profit without requiring long-term production scheduling.

Each CodeClash player edits an SCML OneShot agent. A round runs multiple independent SCML worlds and
scores each player by average profit.

## Resources

- [SCML Official Site](https://scml.cs.brown.edu/)
- [SCML Documentation](https://scml.readthedocs.io/)

## Implementation

::: codeclash.arenas.scml.scml.SCMLOneShotArena
    options:
      show_root_heading: true
      heading_level: 2

## Agent Interface

Your bot must be a Python file named `scml_agent.py` that defines `MyAgent`.

`MyAgent` must inherit from an SCML OneShot agent class. A valid starting point is:

```python
from scml.oneshot.agents import GreedySyncAgent


class MyAgent(GreedySyncAgent):
    pass
```

Agents can use the normal SCML OneShot APIs exposed by the upstream `scml` package. The package is
installed in the SCML arena Docker image, not in CodeClash's core Python environment.

## Configuration Example

```yaml
tournament:
  rounds: 1
game:
  name: SCML
  sims_per_round: 2
  n_steps: 5
  n_lines: 2
players:
  - agent: dummy
    name: alpha
  - agent: dummy
    name: beta
```

## Scoring

The arena runs `sims_per_round` independent SCML2024 OneShot worlds. For each world, it maps SCML
agent scores back to CodeClash player names. The final CodeClash score is the average SCML score
across those worlds.

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
- the output directory contains `metadata.json`, `game.log`, `tournament.log`, and
  `rounds/round_0.tar.gz` / `rounds/round_1.tar.gz`.

A representative `metadata.json` round contains a `scores` object with one floating-point SCML
profit score per player:

```json
"scores": {
  "alpha": 1.0447501220885806,
  "beta": 0.9783875910335903
}
```

Exact values can change with simulation order and configuration; the smoke check is meant to verify
the Docker/runtime adapter path, player-name mapping, and score/log artifact shape.

The exact tournament directory name includes a timestamp, so inspect the metadata with:

```bash
find /tmp/codeclash-scml-smoke -maxdepth 3 -name metadata.json -print
```

--8<-- "docs/_footer.md"
