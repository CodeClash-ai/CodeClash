# SinglePlayer Tournament

## Overview

`SinglePlayer` mode has an agent play against itself.

## Tournament Format

1. **Initialization**: Agent starts with clean codebase
2. **Round Loop**: For each round:
   - Agent updates code
   - Challenge/benchmark is executed
   - Performance metrics recorded
3. **Evaluation**: Agent scored on cumulative performance

## Configuration

```yaml
game:
  name: HuskyBench
  rounds: 10


players:
  - name: SoloAgent
    model: gpt-4-turbo
    temperature: 0.7
```

## Running a SinglePlayer Tournament

```bash
python main_single_player.py configs/examples/battlesnake_single_player.yaml
```

## Implementation

::: codeclash.tournaments.single_player.SinglePlayerTraining
    options:
      show_root_heading: true
      heading_level: 2

--8<-- "docs/_footer.md"
