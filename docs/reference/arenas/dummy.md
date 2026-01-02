# DummyArena

Simple test game for development and debugging.

## Overview

DummyArena is a minimal game implementation used for testing the CodeClash framework.

## Implementation

::: codeclash.arenas.dummy.dummy.DummyArena
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
  name: DummyArena
  rounds: 3
  sims_per_round: 1

players:
  - name: TestAgent
    model: gpt-4
```

--8<-- "docs/_footer.md"
