import argparse
import contextlib
import importlib.util
import json
import multiprocessing as mp
import queue
import random
import re
import sys
import traceback
from pathlib import Path
from statistics import mean

import numpy as np

CRASH_SCORE = -1_000_000.0
DEFAULT_ACTION = 0


def safe_module_name(player_name: str) -> str:
    safe = re.sub(r"\W+", "_", player_name)
    if not safe or safe[0].isdigit():
        safe = f"player_{safe}"
    return f"codeclash_cyborg_{safe.lower()}"


def load_policy_module(player_name: str, path: str):
    agent_dir = str(Path(path).resolve().parent)
    inserted_agent_dir = agent_dir not in sys.path
    if inserted_agent_dir:
        sys.path.insert(0, agent_dir)
    spec = importlib.util.spec_from_file_location(safe_module_name(player_name), path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load module spec from {path}")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    finally:
        if inserted_agent_dir:
            sys.path.remove(agent_dir)
    if not hasattr(module, "decide") or not callable(module.decide):
        raise RuntimeError(f"{path} must define a callable decide(observation, action_space)")
    return module


def observation_to_plain(observation):
    if hasattr(observation, "tolist"):
        return observation.tolist()
    if isinstance(observation, dict):
        return {str(key): observation_to_plain(value) for key, value in observation.items()}
    if isinstance(observation, (list, tuple)):
        return [observation_to_plain(value) for value in observation]
    if isinstance(observation, np.generic):
        return observation.item()
    return observation


def action_space_to_plain(action_space) -> dict:
    n = getattr(action_space, "n", None)
    if n is not None:
        return {"type": "discrete", "n": int(n)}
    return {"type": type(action_space).__name__}


def normalize_action(action, action_space) -> tuple[int, str | None]:
    n = getattr(action_space, "n", None)
    if action is None:
        return DEFAULT_ACTION, None
    if isinstance(action, np.generic):
        action = action.item()
    if isinstance(action, bool):
        return DEFAULT_ACTION, "action must be an integer"
    if isinstance(action, float) and action.is_integer():
        action = int(action)
    if not isinstance(action, int):
        return DEFAULT_ACTION, "action must be an integer"
    if n is not None and not 0 <= action < int(n):
        return DEFAULT_ACTION, f"action {action} outside Discrete({int(n)})"
    return action, None


def policy_worker(
    command_queue: mp.Queue,
    result_queue: mp.Queue,
    startup_queue: mp.Queue,
    player_name: str,
    agent_name: str,
    path: str,
) -> None:
    try:
        module = load_policy_module(player_name, path)
    except BaseException as exc:
        startup_queue.put(
            {
                "error": f"{type(exc).__name__}: {exc}",
                "traceback": traceback.format_exc(limit=5),
            }
        )
        return
    startup_queue.put({"ready": True})

    while True:
        try:
            request = command_queue.get()
        except (EOFError, KeyboardInterrupt):
            return
        if request is None:
            return
        request_id = request["request_id"]
        try:
            action = module.decide(request["observation"], request["action_space"])
            result_queue.put({"request_id": request_id, "action": action})
        except BaseException as exc:
            result_queue.put(
                {
                    "request_id": request_id,
                    "error": f"{type(exc).__name__}: {exc}",
                    "traceback": traceback.format_exc(limit=5),
                }
            )


class PolicyController:
    def __init__(self, player_name: str, agent_name: str, path: str, *, timeout: float):
        self.player_name = player_name
        self.agent_name = agent_name
        self.path = path
        self.timeout = max(float(timeout), 0.01)
        self.errors: list[dict] = []
        self.invalid_actions = 0
        self.decisions = 0
        self.startup_error: str | None = None
        self._next_request_id = 0
        self._start_worker()

    def _start_worker(self) -> None:
        self.startup_error = None
        ctx = mp.get_context("spawn")
        self.command_queue = ctx.Queue()
        self.result_queue = ctx.Queue()
        self.startup_queue = ctx.Queue()
        self.process = ctx.Process(
            target=policy_worker,
            args=(
                self.command_queue,
                self.result_queue,
                self.startup_queue,
                self.player_name,
                self.agent_name,
                self.path,
            ),
        )
        self.process.start()
        startup_timeout = max(self.timeout, 10.0)
        try:
            startup_message = self.startup_queue.get(timeout=startup_timeout)
        except queue.Empty:
            self.startup_error = f"policy import exceeded {startup_timeout}s timeout"
            self.close()
            return
        if "error" in startup_message:
            self.startup_error = startup_message["error"]
            self.close()

    def close(self) -> None:
        with contextlib.suppress(Exception):
            self.command_queue.put_nowait(None)
        self.process.join(0.1)
        if self.process.is_alive():
            self.process.terminate()
            self.process.join(0.1)
        if self.process.is_alive():
            self.process.kill()
            self.process.join()

    def restart(self) -> None:
        self.close()
        self._start_worker()

    def decide(self, observation, action_space) -> int:
        if self.startup_error is not None:
            self.errors.append({"agent": self.agent_name, "error": self.startup_error})
            self.restart()
            return DEFAULT_ACTION
        request_id = self._next_request_id
        self._next_request_id += 1
        self.command_queue.put(
            {
                "request_id": request_id,
                "observation": observation_to_plain(observation),
                "action_space": action_space_to_plain(action_space),
            }
        )
        try:
            result = self.result_queue.get(timeout=self.timeout)
        except queue.Empty:
            self.errors.append({"agent": self.agent_name, "error": f"decide exceeded {self.timeout}s timeout"})
            self.restart()
            return DEFAULT_ACTION

        if result.get("request_id") not in {request_id, None}:
            self.errors.append({"agent": self.agent_name, "error": "received stale policy result"})
            return DEFAULT_ACTION
        if "error" in result:
            self.errors.append(
                {
                    "agent": self.agent_name,
                    "error": result["error"],
                    "traceback": result.get("traceback"),
                }
            )
            if result.get("request_id") is None:
                self.restart()
            return DEFAULT_ACTION

        action, error = normalize_action(result.get("action"), action_space)
        if error is not None:
            self.invalid_actions += 1
            self.errors.append({"agent": self.agent_name, "error": error})
        self.decisions += 1
        return action


def evaluate_player(
    player_name: str,
    policy_path: str,
    *,
    episode_idx: int,
    steps: int,
    drones: int,
    decision_timeout: float,
) -> dict:
    seed = 4100 + episode_idx
    random.seed(seed)
    np.random.seed(seed)
    policies = {}

    try:
        from CybORG import CybORG
        from CybORG.Agents.Wrappers.PettingZooParallelWrapper import PettingZooParallelWrapper
        from CybORG.Simulator.Scenarios import DroneSwarmScenarioGenerator

        scenario = DroneSwarmScenarioGenerator(num_drones=drones)
        env = PettingZooParallelWrapper(CybORG(scenario, "sim"))
        observations = env.reset()
        action_spaces = env.action_spaces
        policies = {
            agent_name: PolicyController(player_name, agent_name, policy_path, timeout=decision_timeout)
            for agent_name in env.possible_agents
        }

        step_rewards = []
        for _ in range(steps):
            actions = {
                agent_name: policies[agent_name].decide(observations[agent_name], action_spaces[agent_name])
                for agent_name in env.agents
            }
            observations, rewards, done, _info = env.step(actions)
            step_rewards.append(mean(rewards.values()))
            if all(done.values()):
                break

        policy_errors = sum(len(policy.errors) for policy in policies.values())
        invalid_actions = sum(policy.invalid_actions for policy in policies.values())
        decisions = sum(policy.decisions for policy in policies.values())
        error_samples = [error for policy in policies.values() for error in policy.errors[:2]][:5]

        return {
            "player": player_name,
            "episode": episode_idx,
            "score": float(sum(step_rewards)),
            "steps_completed": len(step_rewards),
            "decisions": decisions,
            "policy_errors": policy_errors,
            "invalid_actions": invalid_actions,
            "policy_error_samples": error_samples,
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
    finally:
        for policy in policies.values():
            policy.close()


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
    parser.add_argument("--decision-timeout", type=float, default=3.0)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    if args.episodes < 1:
        parser.error("--episodes must be at least 1")
    if args.steps < 1:
        parser.error("--steps must be at least 1")
    if args.drones < 1:
        parser.error("--drones must be at least 1")
    if args.decision_timeout <= 0:
        parser.error("--decision-timeout must be positive")

    agent_paths = dict(args.agent)
    totals = {name: 0.0 for name in agent_paths}
    details = []

    for episode_idx in range(args.episodes):
        for player_name, policy_path in agent_paths.items():
            result = evaluate_player(
                player_name,
                policy_path,
                episode_idx=episode_idx,
                steps=args.steps,
                drones=args.drones,
                decision_timeout=args.decision_timeout,
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
