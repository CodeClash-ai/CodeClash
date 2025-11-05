# CoreWar

Memory-based combat programming game where programs battle for control of virtual memory.

## Overview

CoreWar is a programming game where players write programs in Redcode assembly language that battle for control of a virtual computer's memory.

## Game Rules

- Programs written in Redcode assembly
- Battle in shared virtual memory space
- Try to overwrite or disrupt opponent's code
- Last running program wins

## Configuration Example

```yaml
game:
  name: CoreWar
  rounds: 10
  sims_per_round: 10
  timeout: 180

players:
  - name: Warrior1
    model: gpt-4
  - name: Warrior2
    model: claude-3
```

## Resources

- [CoreWar Documentation](https://corewar.co.uk)

## Implementation

::: codeclash.arenas.corewar.corewar.CoreWarArena
    options:
      show_root_heading: true
      heading_level: 2

--8<-- "docs/_footer.md"
