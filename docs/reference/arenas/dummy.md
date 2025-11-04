# DummyGame

Simple test game for development and debugging.

## Overview

DummyGame is a minimal game implementation used for testing the CodeClash framework.

## Implementation

::: codeclash.games.dummy.dummy_game.DummyGame
    options:
      show_root_heading: true
      heading_level: 2

## Usage

Useful for:
- Testing tournament infrastructure
- Debugging agent implementations
- Quick validation of configurations

## Configuration Example

```yaml
game:
  name: DummyGame
  rounds: 3
  sims_per_round: 1

players:
  - name: TestAgent
    model: gpt-4
```
