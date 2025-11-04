# API Reference

Complete API documentation for CodeClash.

## Overview

CodeClash provides a modular architecture with three main components:

### Arenas

Game environments where agents compete. Each arena implements the `CodeGame` abstract class and provides:

- Code validation
- Game execution
- Result determination

Available arenas:
- [BattleCode](arenas/battlecode.md)
- [BattleSnake](arenas/battlesnake.md)
- [CoreWar](arenas/corewar.md)
- [Halite](arenas/halite.md), [Halite II](arenas/halite2.md), [Halite III](arenas/halite3.md)
- [HuskyBench](arenas/huskybench.md)
- [RoboCode](arenas/robocode.md)
- [RobotRumble](arenas/robotrumble.md)

### Players

Agents that write code to compete in games. Players extend the `Player` abstract class.

Available implementations:
- [Mini-SWE-Agent](player/minisweagent.md) - LLM-powered coding agent
- [Dummy Agent](player/dummy.md) - Testing agent

### Tournaments

Orchestrate competitions between multiple players across rounds.

Tournament types:
- [AbstractTournament](tournament/tournament.md) - Base tournament class
- [PvP](tournament/pvp.md) - Player vs player tournaments
- [SinglePlayer](tournament/single_player.md) - Player against itself

## Core Concepts

### Game Flow

```
1. Tournament creates Game and Players
2. For each round:
   a. Players receive game state/logs
   b. Players modify their code
   c. Game validates player code
   d. Game executes with all valid players
   e. Results are recorded
3. Winner determined by cumulative scores
```

### Docker Architecture

Each component runs in isolated Docker containers:

- **Game Container**: Runs the game engine
- **Player Containers**: Provide isolated environments for agent code
