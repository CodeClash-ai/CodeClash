# CodeArena (Abstract Base)

The `CodeArena` class is the abstract base class for all game arenas in CodeClash.

## Overview

Every game in CodeClash extends `CodeArena` and implements three key methods:

1. `validate_code()`: Verify that player submissions are valid
2. `execute_round()`: Run the actual game
3. `get_results()`: Determine winners and scores

## Key Concepts

### Game Lifecycle

1. **Initialization**: Game container is created with Docker
2. **Round Execution**: For each round:
   - Pre-round setup (copy player code)
   - Validation (check all submissions)
   - Execution (run the game)
   - Results (determine winner)
   - Post-round (save logs)
3. **Cleanup**: Remove containers and artifacts

### Docker Integration

Each game runs in its own Docker container with:

- Game engine installed
- Git repository initialized
- Player code copied in

## Class Reference

::: codeclash.arenas.arena.CodeArena
    options:
      show_root_heading: true
      heading_level: 2

## Supporting Classes

### PlayerStats

::: codeclash.arenas.arena.PlayerStats
    options:
      show_root_heading: true
      heading_level: 3

### RoundStats

::: codeclash.arenas.arena.RoundStats
    options:
      show_root_heading: true
      heading_level: 3

--8<-- "docs/_footer.md"
