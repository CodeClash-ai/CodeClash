# AbstractTournament

The base class for all tournament types in CodeClash.

## Overview

The `AbstractTournament` class provides:

- Tournament initialization and configuration
- Logging infrastructure
- Metadata collection
- Common utilities for tournament orchestration

Specific tournament types (PvP, SinglePlayer) extend this class.

## Tournament Structure

### Configuration

All tournaments are configured via YAML files:

```yaml
game:
  name: BattleCode
  rounds: 10
  sims_per_round: 3
  timeout: 300

players:
  - name: Agent1
    model: gpt-4
  - name: Agent2
    model: claude-3
```

### Output Directory Structure

```
logs/
└── {tournament_id}/
    ├── tournament.log          # Main tournament log
    ├── game.log               # Game-specific log
    ├── everything.log         # Combined log
    ├── metadata.json          # Tournament metadata
    ├── players/
    │   └── {player_name}/
    │       ├── player.log
    │       └── changes_r{N}.json
    └── rounds/
        └── {round_num}/
            └── game logs...
```

### Metadata

Tournament metadata is stored in `metadata.json`:

```json
{
  "name": "pvp",
  "tournament_id": "pvp.BattleCode.251104123456",
  "created_timestamp": 1730736896,
  "config": {
    "game": {...},
    "players": [...]
  }
}
```

## See Also

- [PvP Tournament](pvp.md)
- [SinglePlayer Tournament](single_player.md)
- [CodeGame Base Class](../arenas/game.md)
- [Player Base Class](../player/player.md)

## Class Reference

::: codeclash.tournaments.tournament.AbstractTournament
    options:
      show_root_heading: true
      heading_level: 2
