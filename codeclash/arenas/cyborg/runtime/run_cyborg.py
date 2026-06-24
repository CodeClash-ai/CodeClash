import argparse
import importlib.util
import json
import random
import re
import traceback
from pathlib import Path
from statistics import mean

import numpy as np
from CybORG import CybORG
from CybORG.Agents import BaseAgent
from CybORG.Agents.Wrappers.PettingZooParallelWrapper import PettingZooParallelWrapper
from CybORG.Simulator.Scenarios import DroneSwarmScenarioGenerator

CRASH_SCORE = -1_000_000.0


def safe_module_name(player_name: str) -> str:
    safe = re.sub(r"\W+", "_", player_name)
    if not safe or safe[0].isdigit():
        safe = f"player_{safe}"
    return f"codeclash_cyborg_{safe.lower()}"


def load_agent_class(player_name: str, path: str):
    spec = importlib.util.spec_from_file_location(safe_module_name(player_name), path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load module spec from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not hasattr(module, "MyAgent"):
        raise RuntimeError(f"{path} does not define MyAgent")
    agent_class = module.MyAgent
    if not issubclass(agent_class, BaseAgent):
        raise RuntimeError(f"{path} MyAgent must inherit from CybORG BaseAgent")
    return agent_class


def make_agent(agent_class: type, agent_name: str):
    try:
        return agent_class(name=agent_name)
    except TypeError:
        try:
            return agent_class(agent_name)
        except TypeError:
            return agent_class()


def evaluate_player(
    player_name: str,
    agent_class: type,
    *,
    episode_idx: int,
    steps: int,
    drones: int,
) -> dict:
    seed = 4100 + episode_idx
    random.seed(seed)
    np.random.seed(seed)

    try:
        scenario = DroneSwarmScenarioGenerator(num_drones=drones)
        env = PettingZooParallelWrapper(CybORG(scenario, "sim"))
        observations = env.reset()
        action_spaces = env.action_spaces
        agents = {agent_name: make_agent(agent_class, agent_name) for agent_name in env.possible_agents}

        for agent_name, agent in agents.items():
            if hasattr(agent, "set_initial_values"):
                agent.set_initial_values(action_spaces[agent_name], observations[agent_name])

        step_rewards = []
        for _ in range(steps):
            actions = {
                agent_name: agents[agent_name].get_action(observations[agent_name], action_spaces[agent_name])
                for agent_name in env.agents
            }
            observations, rewards, done, _info = env.step(actions)
            step_rewards.append(mean(rewards.values()))
            if all(done.values()):
                break

        for agent in agents.values():
            if hasattr(agent, "end_episode"):
                agent.end_episode()

        return {
            "player": player_name,
            "episode": episode_idx,
            "score": float(sum(step_rewards)),
            "steps_completed": len(step_rewards),
            "status": "ok",
        }
    except Exception as exc:
        return {
            "player": player_name,
            "episode": episode_idx,
            "score": CRASH_SCORE,
            "steps_completed": 0,
            "status": "error",
            "error": f"{type(exc).__name__}: {exc}",
            "traceback": traceback.format_exc(limit=5),
        }


def parse_agent_arg(value: str) -> tuple[str, str]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("--agent values must be NAME=/path/to/cyborg_agent.py")
    name, path = value.split("=", 1)
    if not name:
        raise argparse.ArgumentTypeError("agent name cannot be empty")
    if not Path(path).exists():
        raise argparse.ArgumentTypeError(f"agent path does not exist: {path}")
    return name, path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent", action="append", type=parse_agent_arg, required=True)
    parser.add_argument("--episodes", type=int, default=3)
    parser.add_argument("--steps", type=int, default=30)
    parser.add_argument("--drones", type=int, default=18)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    agent_classes = {name: load_agent_class(name, path) for name, path in args.agent}
    totals = {name: 0.0 for name in agent_classes}
    details = []

    for episode_idx in range(args.episodes):
        for player_name, agent_class in agent_classes.items():
            result = evaluate_player(
                player_name,
                agent_class,
                episode_idx=episode_idx,
                steps=args.steps,
                drones=args.drones,
            )
            totals[player_name] += result["score"]
            details.append(result)

    averages = {player: score / args.episodes for player, score in totals.items()}
    output = {
        "average_scores": averages,
        "total_scores": totals,
        "episodes": args.episodes,
        "details": [json.dumps(item, sort_keys=True) for item in details],
    }
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(output, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
