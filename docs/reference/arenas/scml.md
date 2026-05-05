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

--8<-- "docs/_footer.md"
