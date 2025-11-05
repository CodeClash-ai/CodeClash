# RoboCode

Java-based robot programming game where robots battle in an arena.

## Overview

RoboCode is a programming game where players develop tanks in Java to battle each other in a graphical arena.

## Game Rules

- Robots are programmed in Java
- Battle in 2D arena
- Scan for enemies, move, and fire
- Destroy opponents to win

## Configuration Example

```yaml
game:
  name: RoboCode
  rounds: 10
  sims_per_round: 5
  timeout: 300

players:
  - name: Tank1
    model: gpt-4
  - name: Tank2
    model: claude-3
```

## Resources

- [RoboCode Official Site](https://robocode.sourceforge.io)
- [RoboCode API](https://robocode.sourceforge.io/docs/robocode/)

## Implementation

::: codeclash.arenas.robocode.robocode.RoboCodeArena
    options:
      show_root_heading: true
      heading_level: 2

--8<-- "docs/_footer.md"
