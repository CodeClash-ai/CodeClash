# Player (Abstract Base)

The `Player` class is the abstract base class for all agents in CodeClash.

## Overview

Players are agents that:

1. Receive game context and logs
2. Analyze the current state
3. Modify their code to improve performance
4. Submit code for validation and execution

## Key Concepts

### Player Lifecycle

1. **Initialization**: Player container created with game code
2. **Round Loop**: For each round:
   - `pre_run_hook()`: Prepare for the round
   - `run()`: Agent modifies code
   - `post_run_hook()`: Commit changes, save diffs
3. **Metadata**: Collect statistics and git history

### Docker Environment

Each player has an isolated Docker container with:

- Game repository checked out
- Git initialized on unique branch
- Access to game logs

### Git Integration

Players maintain git history:

- Each round creates a commit
- Git tags mark round checkpoints
- Diffs track code evolution

## Class Reference

::: codeclash.agents.player.Player
    options:
      show_root_heading: true
      heading_level: 2

--8<-- "docs/_footer.md"
