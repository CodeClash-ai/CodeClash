# BattleSnake

Multiplayer snake game where snakes compete to be the last survivor.

## Overview

BattleSnake is a multi-player version of the classic snake game. Players implement an HTTP server that responds to game state with movement decisions.

## Game Rules

- Snakes move on a grid
- Eat food to grow longer
- Avoid walls and other snakes
- Last snake standing wins

## Submission Format

Players must implement an HTTP server with specific endpoints:

- `GET /`: Return snake metadata
- `POST /start`: Handle game start
- `POST /move`: Return movement decision
- `POST /end`: Handle game end

## Configuration Example

```yaml
game:
  name: BattleSnake
  rounds: 10
  sims_per_round: 5
  timeout: 300

players:
  - name: Snake1
    model: gpt-4
  - name: Snake2
    model: claude-3
```

## Resources

- [BattleSnake Official Site](https://play.battlesnake.com)
- [API Documentation](https://docs.battlesnake.com)

## Implementation

::: codeclash.games.battlesnake.battlesnake.BattleSnakeGame
    options:
      show_root_heading: true
      heading_level: 2

--8<-- "docs/_footer.md"
