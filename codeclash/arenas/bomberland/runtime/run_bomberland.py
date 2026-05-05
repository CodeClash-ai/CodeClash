import argparse
import copy
import importlib.util
import json
import multiprocessing
import queue
import random
import sys
from collections import defaultdict
from pathlib import Path

ACTIONS = {"up", "down", "left", "right", "bomb", "stay"}
DELTAS = {
    "up": (0, -1),
    "down": (0, 1),
    "left": (-1, 0),
    "right": (1, 0),
}
START_HP = 3
START_BOMBS = 1
BLAST_RADIUS = 3
BOMB_TIMER = 6


def load_agent(name, path):
    agent_dir = str(Path(path).resolve().parent)
    if agent_dir not in sys.path:
        sys.path.insert(0, agent_dir)
    spec = importlib.util.spec_from_file_location(f"bomberland_agent_{name}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not hasattr(module, "next_actions") or not callable(module.next_actions):
        raise ValueError(f"{path} must define a callable next_actions(game_state)")
    return module.next_actions


def _agent_worker(path, state, result_queue):
    try:
        callback = load_agent("runtime", path)
        result = callback(copy.deepcopy(state))
        result_queue.put({"actions": result if isinstance(result, dict) else {}})
    except BaseException as exc:
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        result_queue.put({"error": type(exc).__name__})


def call_agent(agent_path, state, timeout):
    timeout = max(float(timeout), 0.01)
    start_method = "fork" if "fork" in multiprocessing.get_all_start_methods() else "spawn"
    context = multiprocessing.get_context(start_method)
    result_queue = context.Queue(maxsize=1)
    process = context.Process(target=_agent_worker, args=(agent_path, copy.deepcopy(state), result_queue))
    process.start()
    process.join(timeout)
    if process.is_alive():
        process.terminate()
        process.join(0.1)
        if process.is_alive() and hasattr(process, "kill"):
            process.kill()
            process.join()
        return {"__error__": "Timeout"}
    if process.exitcode not in (0, None):
        return {"__error__": f"ExitCode{process.exitcode}"}
    try:
        message = result_queue.get_nowait()
    except queue.Empty:
        return {"__error__": "NoResult"}
    if "error" in message:
        return {"__error__": message["error"]}
    return message.get("actions", {})


def mirror(pos, width, height):
    x, y = pos
    return width - 1 - x, height - 1 - y


def player_starts(width, height, unit_count):
    if not 1 <= unit_count <= 4:
        raise ValueError("unit_count must be between 1 and 4")
    left = [(1, 1), (1, height - 2), (2, height // 2), (3, 1)]
    right = [mirror(pos, width, height) for pos in left]
    return left[:unit_count], right[:unit_count]


def build_map(width, height, unit_count, rng):
    if width < 7 or height < 7:
        raise ValueError("Bomberland maps must be at least 7x7")

    metal = set()
    for x in range(width):
        metal.add((x, 0))
        metal.add((x, height - 1))
    for y in range(height):
        metal.add((0, y))
        metal.add((width - 1, y))
    for x in range(2, width - 2, 2):
        for y in range(2, height - 2, 2):
            metal.add((x, y))

    starts_left, starts_right = player_starts(width, height, unit_count)
    safe = set()
    for pos in [*starts_left, *starts_right]:
        safe.add(pos)
        for dx, dy in DELTAS.values():
            safe.add((pos[0] + dx, pos[1] + dy))

    wood = set()
    for y in range(1, height - 1):
        for x in range(1, width - 1):
            pos = (x, y)
            mirrored = mirror(pos, width, height)
            if pos in metal or pos in safe or mirrored in metal or mirrored in safe:
                continue
            if pos in wood or mirrored in wood:
                continue
            if rng.random() < 0.28:
                wood.add(pos)
                wood.add(mirrored)
    return metal, wood


def make_units(players, width, height, unit_count):
    left_starts, right_starts = player_starts(width, height, unit_count)
    if len(players) != 2:
        raise ValueError("Bomberland currently expects exactly two players")

    starts_by_player = {players[0]: left_starts, players[1]: right_starts}
    units = {}
    agents = {}
    for player in players:
        unit_ids = []
        for index, pos in enumerate(starts_by_player[player]):
            unit_id = f"{player}_unit_{index}"
            unit_ids.append(unit_id)
            units[unit_id] = {
                "unit_id": unit_id,
                "agent_id": player,
                "coordinates": list(pos),
                "hp": START_HP,
                "inventory": {"bombs": START_BOMBS, "blast_diameter": BLAST_RADIUS * 2 - 1},
            }
        agents[player] = {"agent_id": player, "unit_ids": unit_ids}
    return units, agents


def pos_of(unit):
    return tuple(unit["coordinates"])


def entities_for_state(metal, wood, bombs, blasts):
    entities = []
    for x, y in sorted(metal):
        entities.append({"type": "m", "coordinates": [x, y]})
    for x, y in sorted(wood):
        entities.append({"type": "w", "coordinates": [x, y]})
    for bomb in bombs:
        entities.append(
            {
                "type": "b",
                "coordinates": list(bomb["pos"]),
                "owner": bomb["owner"],
                "timer": bomb["timer"],
                "blast_diameter": bomb["radius"] * 2 - 1,
            }
        )
    for (x, y), ttl in sorted(blasts.items()):
        entities.append({"type": "x", "coordinates": [x, y], "ttl": ttl})
    return entities


def make_state(player, agents, units, metal, wood, bombs, blasts, width, height, tick):
    return {
        "connection": {"agent_id": player},
        "agents": copy.deepcopy(agents),
        "unit_state": copy.deepcopy(units),
        "entities": entities_for_state(metal, wood, bombs, blasts),
        "world": {"width": width, "height": height},
        "tick": tick,
        "config": {
            "bomb_timer": BOMB_TIMER,
            "start_hp": START_HP,
            "start_bombs": START_BOMBS,
            "blast_radius": BLAST_RADIUS,
        },
    }


def normalize_action(raw_action):
    if isinstance(raw_action, str):
        action = raw_action.lower().strip()
        if action in ACTIONS:
            return action, None
        if action.startswith("detonate:"):
            try:
                x_raw, y_raw = action.split(":", 1)[1].split(",", 1)
                return "detonate", (int(x_raw), int(y_raw))
            except ValueError:
                return "invalid", None
    if isinstance(raw_action, dict):
        action_type = str(raw_action.get("type", raw_action.get("action", ""))).lower()
        if action_type == "move":
            move = str(raw_action.get("move", raw_action.get("direction", ""))).lower()
            return (move, None) if move in DELTAS else ("invalid", None)
        if action_type in {"bomb", "stay"}:
            return action_type, None
        if action_type == "detonate":
            coordinates = raw_action.get("coordinates", raw_action.get("coordinate"))
            if isinstance(coordinates, (list, tuple)) and len(coordinates) == 2:
                try:
                    return "detonate", (int(coordinates[0]), int(coordinates[1]))
                except (TypeError, ValueError):
                    return "invalid", None
    return "invalid", None


def blast_cells(origin, radius, metal, wood):
    cells = [origin]
    ox, oy = origin
    for dx, dy in DELTAS.values():
        for distance in range(1, radius + 1):
            pos = (ox + dx * distance, oy + dy * distance)
            if pos in metal:
                break
            cells.append(pos)
            if pos in wood:
                break
    return cells


def explode_bomb(index, bombs, metal, wood, units, stats, blasts):
    if index >= len(bombs):
        return
    bomb = bombs[index]
    cells = blast_cells(bomb["pos"], bomb["radius"], metal, wood)
    owner = bomb["owner"]
    stats[owner]["bombs_returned"] += 1
    unit_id = bomb.get("unit_id")
    if unit_id in units:
        units[unit_id]["inventory"]["bombs"] += 1

    for cell in cells:
        blasts[cell] = 1
        if cell in wood:
            wood.remove(cell)
            stats[owner]["wood_destroyed"] += 1

    for unit in units.values():
        if unit["hp"] <= 0 or pos_of(unit) not in cells:
            continue
        unit["hp"] -= 1
        if unit["agent_id"] != owner:
            stats[owner]["damage_dealt"] += 1
            if unit["hp"] <= 0:
                stats[owner]["kills"] += 1

    bombs.pop(index)
    chained = True
    while chained:
        chained = False
        for chained_index, chained_bomb in enumerate(list(bombs)):
            if chained_bomb["pos"] in cells:
                explode_bomb(chained_index, bombs, metal, wood, units, stats, blasts)
                chained = True
                break


def live_players(players, units):
    alive = set()
    for unit in units.values():
        if unit["hp"] > 0:
            alive.add(unit["agent_id"])
    return [player for player in players if player in alive]


def apply_actions(players, callbacks, agents, units, metal, wood, bombs, blasts, stats, width, height, tick, timeout):
    bomb_positions = {bomb["pos"] for bomb in bombs}
    actions_by_unit = {}

    for player in players:
        state = make_state(player, agents, units, metal, wood, bombs, blasts, width, height, tick)
        result = call_agent(callbacks[player], state, timeout)
        if "__error__" in result:
            stats[player]["agent_errors"] += 1
            result = {}
        for unit_id in agents[player]["unit_ids"]:
            unit = units[unit_id]
            if unit["hp"] <= 0:
                continue
            action, target = normalize_action(result.get(unit_id, "stay"))
            if action == "invalid":
                stats[player]["invalid_actions"] += 1
                action = "stay"
            actions_by_unit[unit_id] = (action, target)

    for unit_id, (action, target) in actions_by_unit.items():
        unit = units[unit_id]
        player = unit["agent_id"]
        if action == "bomb":
            position = pos_of(unit)
            if unit["inventory"]["bombs"] > 0 and position not in bomb_positions:
                unit["inventory"]["bombs"] -= 1
                bomb_positions.add(position)
                bombs.append(
                    {"owner": player, "unit_id": unit_id, "pos": position, "timer": BOMB_TIMER, "radius": BLAST_RADIUS}
                )
            else:
                stats[player]["invalid_actions"] += 1
        elif action == "detonate":
            for index, bomb in enumerate(list(bombs)):
                if bomb["owner"] == player and (target is None or bomb["pos"] == target):
                    explode_bomb(index, bombs, metal, wood, units, stats, blasts)
                    break

    proposals = {}
    for unit_id, (action, _target) in actions_by_unit.items():
        unit = units[unit_id]
        if unit["hp"] <= 0 or action not in DELTAS:
            continue
        dx, dy = DELTAS[action]
        current = pos_of(unit)
        proposed = (current[0] + dx, current[1] + dy)
        player = unit["agent_id"]
        if proposed in metal or proposed in wood or proposed in bomb_positions:
            stats[player]["invalid_actions"] += 1
            continue
        if not (0 <= proposed[0] < width and 0 <= proposed[1] < height):
            stats[player]["invalid_actions"] += 1
            continue
        proposals[unit_id] = proposed

    target_counts = defaultdict(int)
    for target in proposals.values():
        target_counts[target] += 1

    occupied = {pos_of(unit): unit_id for unit_id, unit in units.items() if unit["hp"] > 0}
    for unit_id, target in proposals.items():
        player = units[unit_id]["agent_id"]
        if target_counts[target] > 1:
            stats[player]["invalid_actions"] += 1
            continue
        occupant = occupied.get(target)
        if occupant is not None:
            stats[player]["invalid_actions"] += 1
            continue
        units[unit_id]["coordinates"] = list(target)


def tick_bombs(bombs, metal, wood, units, stats, blasts):
    index = 0
    while index < len(bombs):
        bombs[index]["timer"] -= 1
        if bombs[index]["timer"] <= 0:
            explode_bomb(index, bombs, metal, wood, units, stats, blasts)
        else:
            index += 1


def player_score(player, agents, units, stats):
    alive_units = [units[unit_id] for unit_id in agents[player]["unit_ids"] if units[unit_id]["hp"] > 0]
    alive_hp = sum(unit["hp"] for unit in alive_units)
    return (
        alive_hp * 30
        + len(alive_units) * 20
        + stats[player]["damage_dealt"] * 120
        + stats[player]["kills"] * 300
        + stats[player]["wood_destroyed"] * 40
        - stats[player]["invalid_actions"]
        - stats[player]["agent_errors"] * 10
    )


def run_game(players, callbacks, seed, ticks, width, height, unit_count, agent_timeout):
    rng = random.Random(seed)
    metal, wood = build_map(width, height, unit_count, rng)
    units, agents = make_units(players, width, height, unit_count)
    bombs = []
    blasts = {}
    stats = {
        player: {
            "damage_dealt": 0,
            "kills": 0,
            "wood_destroyed": 0,
            "invalid_actions": 0,
            "agent_errors": 0,
            "bombs_returned": 0,
        }
        for player in players
    }

    final_tick = 0
    for tick in range(ticks):
        final_tick = tick
        blasts = {pos: ttl - 1 for pos, ttl in blasts.items() if ttl > 1}
        apply_actions(
            players, callbacks, agents, units, metal, wood, bombs, blasts, stats, width, height, tick, agent_timeout
        )
        tick_bombs(bombs, metal, wood, units, stats, blasts)
        if len(live_players(players, units)) <= 1:
            break

    scores = {player: float(player_score(player, agents, units, stats)) for player in players}
    best_score = max(scores.values())
    winners = [player for player, score in scores.items() if score == best_score]
    winner = winners[0] if len(winners) == 1 else "TIE"
    detail = {
        "seed": seed,
        "ticks": final_tick + 1,
        "winner": winner,
        "scores": scores,
        "alive_units": {
            player: sum(1 for unit_id in agents[player]["unit_ids"] if units[unit_id]["hp"] > 0) for player in players
        },
        "alive_hp": {
            player: sum(max(units[unit_id]["hp"], 0) for unit_id in agents[player]["unit_ids"]) for player in players
        },
        "stats": stats,
    }
    return scores, detail


def parse_agent_arg(raw):
    if "=" not in raw:
        raise argparse.ArgumentTypeError("--agent must use NAME=/path/to/bomberland_agent.py")
    name, path = raw.split("=", 1)
    if not name or not path:
        raise argparse.ArgumentTypeError("--agent must include both NAME and path")
    return name, path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sims", type=int, required=True)
    parser.add_argument("--ticks", type=int, required=True)
    parser.add_argument("--width", type=int, required=True)
    parser.add_argument("--height", type=int, required=True)
    parser.add_argument("--unit-count", type=int, required=True)
    parser.add_argument("--agent-timeout", type=float, default=0.25)
    parser.add_argument("--output", required=True)
    parser.add_argument("--agent", action="append", type=parse_agent_arg, required=True)
    args = parser.parse_args()

    if len(args.agent) != 2:
        raise ValueError("Bomberland currently expects exactly two --agent entries")
    if args.sims % 2 != 0:
        raise ValueError("--sims must be even so both players get paired starting sides")

    players = [name for name, _path in args.agent]
    callbacks = {name: path for name, path in args.agent}
    totals = {player: 0.0 for player in players}
    details = []
    for sim in range(args.sims):
        sim_players = players if sim % 2 == 0 else list(reversed(players))
        scores, detail = run_game(
            sim_players,
            callbacks,
            seed=100_000 + sim,
            ticks=args.ticks,
            width=args.width,
            height=args.height,
            unit_count=args.unit_count,
            agent_timeout=args.agent_timeout,
        )
        for player, score in scores.items():
            totals[player] += score
        detail["sim"] = sim
        detail["player_order"] = sim_players
        details.append(json.dumps(detail, sort_keys=True))

    result = {
        "average_scores": {player: totals[player] / args.sims for player in players},
        "total_scores": totals,
        "sims": args.sims,
        "details": details,
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
