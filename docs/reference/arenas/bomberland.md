# Bomberland

Bomberman-style multi-agent arena based on Coder One's Bomberland competition.

## Overview

Bomberland is a grid-world arena where agents control several units, move around indestructible and
destructible blocks, place timed bombs, and try to outscore the opponent through survival, damage,
kills, and block destruction.

The upstream Bomberland project uses a TypeScript websocket engine and starter-kit agents. The
CodeClash adapter keeps a pinned upstream checkout in the Docker image for provenance and starter-kit
reference, while using a compact deterministic Python runtime for CodeClash tournament execution.
This avoids requiring Docker Compose inside the arena container while preserving the same core agent
shape: submitted code receives a game-state dictionary and returns one action per controlled unit.

## Resources

- [Bomberland GitHub Repository](https://github.com/CoderOneHQ/bomberland)

## Implementation

::: codeclash.arenas.bomberland.bomberland.BomberlandArena
    options:
      show_root_heading: true
      heading_level: 2

## Agent Interface

Your bot must be a Python file named `bomberland_agent.py` that defines `next_actions`.

```python
def next_actions(game_state):
    agent_id = game_state["connection"]["agent_id"]
    unit_ids = game_state["agents"][agent_id]["unit_ids"]
    return {unit_id: "stay" for unit_id in unit_ids}
```

Valid string actions are `up`, `down`, `left`, `right`, `bomb`, and `stay`. The runtime also accepts
dictionary move actions such as `{"type": "move", "move": "up"}` for compatibility with common
starter-kit styles.

## Configuration Example

```yaml
tournament:
  rounds: 1
game:
  name: Bomberland
  sims_per_round: 2
  args:
    ticks: 40
    width: 11
    height: 11
    unit_count: 3
players:
  - agent: dummy
    name: alpha
  - agent: dummy
    name: beta
```

## Scoring

The arena runs `sims_per_round` deterministic seeded games. `sims_per_round` must be even so each
player receives both starting sides for paired seeds. Each player receives an average score computed
from surviving health, surviving units, enemy damage, kills, destroyed blocks, invalid actions, and
agent runtime errors.

Smoke command:

```bash
uv run python main.py configs/examples/Bomberland__dummy__r1__s2.yaml -o /tmp/codeclash-bomberland-smoke
```

The arena writes `bomberland_results.json` with this shape:

```json
{
  "average_scores": {"alpha": 330.0, "beta": 330.0},
  "total_scores": {"alpha": 660.0, "beta": 660.0},
  "sims": 2,
  "details": ["... per-simulation JSON strings ..."]
}
```

--8<-- "docs/_footer.md"
