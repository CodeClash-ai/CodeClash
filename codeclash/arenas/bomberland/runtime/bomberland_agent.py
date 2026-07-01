def next_actions(game_state):
    agent_id = game_state["connection"]["agent_id"]
    unit_ids = game_state["agents"].get(agent_id, {}).get("unit_ids", [])
    unit_state = game_state.get("unit_state", {})
    return {unit_id: "stay" for unit_id in unit_ids if unit_state.get(unit_id, {}).get("hp", 0) > 0}
