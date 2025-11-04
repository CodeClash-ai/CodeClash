# RobotRumble

Rust-based robot programming game with modern language features.

## Overview

RobotRumble is a programming game where players write Rust code to control robots in arena battles.

## Game Rules

- Programs written in Rust
- Robots battle in 2D grid
- Move, attack, and coordinate
- Team with most units wins

## Configuration Example

```yaml
game:
  name: RobotRumble
  rounds: 10
  sims_per_round: 3
  timeout: 300

players:
  - name: RustBot1
    model: gpt-4
  - name: RustBot2
    model: claude-3
```


## Implementation

::: codeclash.games.robotrumble.robotrumble.RobotRumbleGame
    options:
      show_root_heading: true
      heading_level: 2

--8<-- "docs/_footer.md"
