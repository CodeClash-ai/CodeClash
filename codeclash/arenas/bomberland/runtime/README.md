# Bomberland CodeClash Runtime

This runtime adapts the Coder One Bomberland competition format into a compact,
deterministic CodeClash arena. The Docker image keeps a pinned checkout of
`CoderOneHQ/bomberland` at `/opt/bomberland` for provenance and starter-kit
reference, while `run_bomberland.py` provides the runtime used by CodeClash.

Submissions must provide `bomberland_agent.py` with:

```python
def next_actions(game_state):
    return {"unit_0": "up"}
```

Valid string actions are `up`, `down`, `left`, `right`, `bomb`, and `stay`.
The game-state dictionary follows the upstream starter-kit shape where possible:
`connection.agent_id` identifies the player, `agents[player].unit_ids` lists the
controlled units, `unit_state` contains unit coordinates and health, and
`entities` contains walls, destructible blocks, bombs, and blast tiles.

Round simulation counts must be even so each player receives both starting sides.

Smoke command from the repository root:

```bash
uv run python main.py configs/examples/Bomberland__dummy__r1__s2.yaml -o /tmp/codeclash-bomberland-smoke
```

Expected result shape:

```json
{
  "average_scores": {"player_a": 330.0, "player_b": 330.0},
  "total_scores": {"player_a": 660.0, "player_b": 660.0},
  "sims": 2,
  "details": ["... per-simulation JSON strings ..."]
}
```
