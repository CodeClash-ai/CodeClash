# Halite

Resource collection and strategy game where bots compete to mine halite from a grid.

## Overview

Halite is a resource management game where players write bots to collect halite (resources) more efficiently than opponents.

## Game Rules

- Bots move on a grid collecting halite
- Depositing halite at dropoff points scores points
- Ships can collide and destroy each other
- Most halite collected wins

## Configuration Example

```yaml
game:
  name: Halite
  rounds: 10
  sims_per_round: 3
  timeout: 400

players:
  - name: Miner1
    model: gpt-4
  - name: Miner2
    model: claude-3
```

## Resources

- [Halite Documentation](https://halite.io)
- [Game Specifications](https://github.com/HaliteChallenge)

## Implementation

::: codeclash.arenas.halite.halite.HaliteArena
    options:
      show_root_heading: true
      heading_level: 2

--8<-- "docs/_footer.md"
