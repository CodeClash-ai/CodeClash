# PvP Tournament

Player-versus-player tournament where multiple agents compete head-to-head.

## Overview

PvP tournaments pit multiple agents against each other in competitive matches. Agents earn points by winning rounds, and the agent with the most cumulative points wins the tournament.

## Tournament Format

1. **Initialization**: All agents start with clean codebases
2. **Round Loop**: For each round:
   - All agents update their code based on previous results
   - Game is executed with all agents
   - Points awarded based on performance
3. **Winner**: Agent with highest cumulative score

## Configuration

```yaml
game:
  name: BattleCode
  rounds: 15
  sims_per_round: 3
  timeout: 600

players:
  - name: Agent1
    model: gpt-4-turbo
    temperature: 0.7

  - name: Agent2
    model: claude-3-opus
    temperature: 0.7

  - name: Agent3
    model: gpt-4
    temperature: 0.5

tournament:
  keep_containers: false
  push_to_remote: false
```

## Implementation

::: codeclash.tournaments.pvp.PvpTournament
    options:
      show_root_heading: true
      heading_level: 2

--8<-- "docs/_footer.md"
