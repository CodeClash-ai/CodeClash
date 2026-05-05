import argparse
import importlib.util
import json
import random
import re
from pathlib import Path

import numpy as np
from scml.oneshot import SCML2024OneShotWorld


def safe_class_name(player_name: str) -> str:
    safe = re.sub(r"\W+", "_", player_name)
    if not safe or safe[0].isdigit():
        safe = f"player_{safe}"
    return f"CodeClash_{safe}"


def load_agent_class(player_name: str, path: str):
    module_name = f"codeclash_scml_{safe_class_name(player_name).lower()}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load module spec from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not hasattr(module, "MyAgent"):
        raise RuntimeError(f"{path} does not define MyAgent")
    base_class = module.MyAgent
    return type(safe_class_name(player_name), (base_class,), {"__module__": module.__name__})


def run_world(agent_classes: dict[str, type], *, sim_idx: int, steps: int, lines: int) -> dict:
    seed = 1729 + sim_idx
    random.seed(seed)
    np.random.seed(seed)

    player_names = list(agent_classes.keys())
    offset = sim_idx % len(player_names)
    ordered_names = player_names[offset:] + player_names[:offset]
    wrapped_classes = [agent_classes[name] for name in ordered_names]
    class_to_player = {cls.__name__: player for player, cls in agent_classes.items()}

    config = SCML2024OneShotWorld.generate(
        agent_types=wrapped_classes,
        agent_processes=[0 for _ in wrapped_classes],
        n_steps=steps,
        n_processes=1,
        n_lines=lines,
        random_agent_types=False,
    )
    world = SCML2024OneShotWorld(
        **config,
        no_logs=True,
        compact=True,
        fast=True,
        agent_name_reveals_type=True,
        agent_name_reveals_position=True,
    )
    world.run()

    raw_scores = world.scores()
    player_scores = {player: 0.0 for player in player_names}
    details = []
    for agent_id, score in raw_scores.items():
        world_agent = world.agents[agent_id]
        player = class_to_player.get(world_agent.short_type_name)
        if player is None:
            continue
        numeric_score = float(score)
        player_scores[player] = numeric_score
        details.append(
            {
                "sim": sim_idx,
                "player": player,
                "world_agent_id": agent_id,
                "score": numeric_score,
            }
        )

    return {"scores": player_scores, "details": details}


def parse_agent_arg(value: str) -> tuple[str, str]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("--agent values must be NAME=/path/to/scml_agent.py")
    name, path = value.split("=", 1)
    if not name:
        raise argparse.ArgumentTypeError("agent name cannot be empty")
    if not Path(path).exists():
        raise argparse.ArgumentTypeError(f"agent path does not exist: {path}")
    return name, path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent", action="append", type=parse_agent_arg, required=True)
    parser.add_argument("--sims", type=int, default=3)
    parser.add_argument("--steps", type=int, default=10)
    parser.add_argument("--lines", type=int, default=2)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    agent_classes = {name: load_agent_class(name, path) for name, path in args.agent}
    totals = {name: 0.0 for name in agent_classes}
    details = []

    for sim_idx in range(args.sims):
        result = run_world(agent_classes, sim_idx=sim_idx, steps=args.steps, lines=args.lines)
        for player, score in result["scores"].items():
            totals[player] += score
        details.extend(result["details"])

    averages = {player: score / args.sims for player, score in totals.items()}
    output = {
        "average_scores": averages,
        "total_scores": totals,
        "sims": args.sims,
        "details": [json.dumps(item, sort_keys=True) for item in details],
    }
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(output, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
