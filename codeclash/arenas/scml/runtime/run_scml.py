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
from typing import Any

import numpy as np
from negmas import ResponseType, SAOResponse
from scml.oneshot import SCML2024OneShotWorld
from scml.oneshot.agents import GreedySyncAgent

CRASH_SCORE = -1_000_000.0
QUANTITY = 0
TIME = 1
UNIT_PRICE = 2


def safe_class_name(player_name: str) -> str:
    safe = re.sub(r"\W+", "_", player_name)
    if not safe or safe[0].isdigit():
        safe = f"player_{safe}"
    return f"CodeClash_{safe}"


def safe_module_name(player_name: str) -> str:
    return f"codeclash_scml_{safe_class_name(player_name).lower()}"


def load_policy_module(player_name: str, path: str):
    agent_dir = str(Path(path).resolve().parent)
    inserted_agent_dir = agent_dir not in sys.path
    if inserted_agent_dir:
        sys.path.insert(0, agent_dir)
    module_name = f"codeclash_scml_{safe_class_name(player_name).lower()}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load module spec from {path}")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    finally:
        if inserted_agent_dir:
            sys.path.remove(agent_dir)
    if not hasattr(module, "decide") or not callable(module.decide):
        raise RuntimeError(f"{path} must define a callable decide(observation)")
    return module


def to_plain(value):
    if isinstance(value, np.generic):
        return value.item()
    if hasattr(value, "tolist"):
        return value.tolist()
    if isinstance(value, dict):
        return {str(key): to_plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_plain(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return repr(value)


def issue_to_plain(issue) -> dict[str, Any]:
    return {
        "name": str(getattr(issue, "name", "")),
        "min": to_plain(getattr(issue, "min_value", None)),
        "max": to_plain(getattr(issue, "max_value", None)),
        "values": to_plain(getattr(issue, "values", None)),
    }


def state_to_plain(state) -> dict[str, Any]:
    return {
        "step": to_plain(getattr(state, "step", None)),
        "relative_time": to_plain(getattr(state, "relative_time", None)),
        "current_offer": offer_to_plain(getattr(state, "current_offer", None)),
    }


def offer_to_plain(offer):
    if offer is None:
        return None
    return [to_plain(item) for item in offer]


def response_to_name(response) -> str:
    if response == ResponseType.ACCEPT_OFFER:
        return "accept"
    if response == ResponseType.REJECT_OFFER:
        return "reject"
    if response == ResponseType.END_NEGOTIATION:
        return "end"
    return str(response).lower()


def awi_to_plain(agent) -> dict[str, Any]:
    awi = agent.awi
    fields = [
        "current_step",
        "n_steps",
        "n_lines",
        "max_n_lines",
        "current_score",
        "current_balance",
        "current_inventory",
        "current_exogenous_input_quantity",
        "current_exogenous_input_price",
        "current_exogenous_output_quantity",
        "current_exogenous_output_price",
        "current_disposal_cost",
        "current_shortfall_penalty",
        "my_input_product",
        "my_output_product",
        "is_first_level",
        "is_middle_level",
        "is_last_level",
        "needed_sales",
        "needed_supplies",
        "my_suppliers",
        "my_consumers",
    ]
    return {field: to_plain(getattr(awi, field, None)) for field in fields}


def nmi_to_plain(nmi) -> dict[str, Any]:
    if nmi is None:
        return {}
    return {
        "annotation": to_plain(getattr(nmi, "annotation", {})),
        "issues": [issue_to_plain(issue) for issue in getattr(nmi, "issues", [])],
    }


def normalize_offer(offer, nmi) -> tuple[tuple[int, int, int] | None, str | None]:
    if offer is None:
        return None, None
    if not isinstance(offer, (list, tuple)) or len(offer) != 3:
        return None, "offer must be a 3-item list: [quantity, time, unit_price]"
    issues = getattr(nmi, "issues", None)
    if issues is None or len(issues) < 3:
        return None, "missing SCML issue ranges"
    normalized = []
    for idx, raw_value in enumerate(offer):
        if isinstance(raw_value, np.generic):
            raw_value = raw_value.item()
        if isinstance(raw_value, bool):
            return None, f"offer item {idx} must be an integer"
        if isinstance(raw_value, float) and raw_value.is_integer():
            raw_value = int(raw_value)
        if not isinstance(raw_value, int):
            return None, f"offer item {idx} must be an integer"
        issue = issues[idx]
        min_value = getattr(issue, "min_value", None)
        max_value = getattr(issue, "max_value", None)
        if min_value is not None and raw_value < int(min_value):
            return None, f"offer item {idx} below minimum {int(min_value)}"
        if max_value is not None and raw_value > int(max_value):
            return None, f"offer item {idx} above maximum {int(max_value)}"
        normalized.append(int(raw_value))
    return (normalized[QUANTITY], normalized[TIME], normalized[UNIT_PRICE]), None


def normalize_response(response) -> tuple[ResponseType | None, str | None]:
    if response is None:
        return None, None
    if isinstance(response, ResponseType):
        return response, None
    if not isinstance(response, str):
        return None, "response must be one of: accept, reject, end"
    normalized = response.strip().lower().replace("_", " ")
    if normalized in {"accept", "accept offer", "accept_offer"}:
        return ResponseType.ACCEPT_OFFER, None
    if normalized in {"reject", "reject offer", "reject_offer"}:
        return ResponseType.REJECT_OFFER, None
    if normalized in {"end", "end negotiation", "end_negotiation"}:
        return ResponseType.END_NEGOTIATION, None
    return None, f"unknown response: {response}"


def policy_worker(
    command_queue: mp.Queue, result_queue: mp.Queue, startup_queue: mp.Queue, player_name: str, path: str
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
            decision = module.decide(request["observation"])
            result_queue.put({"request_id": request_id, "decision": decision})
        except BaseException as exc:
            result_queue.put(
                {
                    "request_id": request_id,
                    "error": f"{type(exc).__name__}: {exc}",
                    "traceback": traceback.format_exc(limit=5),
                }
            )


class PolicyController:
    def __init__(self, player_name: str, path: str, *, timeout: float, max_errors: int):
        self.player_name = player_name
        self.path = path
        self.timeout = max(float(timeout), 0.01)
        self.max_errors = max(int(max_errors), 1)
        self.disabled = False
        self.decisions = 0
        self.policy_errors = 0
        self.invalid_decisions = 0
        self.error_samples: list[dict[str, str]] = []
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
            args=(self.command_queue, self.result_queue, self.startup_queue, self.player_name, self.path),
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

    def _record_error(self, event: str, error: str, *, invalid: bool = False) -> None:
        self.policy_errors += 1
        if invalid:
            self.invalid_decisions += 1
        if len(self.error_samples) < 5:
            self.error_samples.append({"event": event, "error": error})
        if self.policy_errors >= self.max_errors:
            self.disabled = True
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

    def decide(self, observation: dict[str, Any]) -> dict[str, Any]:
        if self.disabled:
            return {}
        event = str(observation.get("event", "unknown"))
        if self.startup_error is not None:
            self._record_error(event, self.startup_error)
            if not self.disabled:
                self.restart()
            return {}
        request_id = self._next_request_id
        self._next_request_id += 1
        self.command_queue.put({"request_id": request_id, "observation": observation})
        try:
            result = self.result_queue.get(timeout=self.timeout)
        except queue.Empty:
            self._record_error(event, f"decide exceeded {self.timeout}s timeout")
            if not self.disabled:
                self.restart()
            return {}

        if result.get("request_id") not in {request_id, None}:
            self._record_error(event, "received stale policy result")
            return {}
        if "error" in result:
            self._record_error(event, result["error"])
            if result.get("request_id") is None and not self.disabled:
                self.restart()
            return {}
        decision = result.get("decision")
        if decision is None:
            self.decisions += 1
            return {}
        if not isinstance(decision, dict):
            self._record_error(event, "decide must return a dictionary or None", invalid=True)
            return {}
        self.decisions += 1
        return decision


def build_agent_class(player_name: str, path: str, *, decision_timeout: float, max_policy_errors: int):
    class CodeClashSCMLAgent(GreedySyncAgent):
        _policy_controllers: list[PolicyController] = []

        def init(self):
            super().init()
            self._codeclash_policy = PolicyController(
                player_name, path, timeout=decision_timeout, max_errors=max_policy_errors
            )
            self.__class__._policy_controllers.append(self._codeclash_policy)

        def _base_observation(self, event: str, negotiator_id: str | None = None, state=None) -> dict[str, Any]:
            nmi = self.get_nmi(negotiator_id) if negotiator_id else None
            return {
                "event": event,
                "player": player_name,
                "awi": awi_to_plain(self),
                "negotiator_id": negotiator_id,
                "nmi": nmi_to_plain(nmi),
                "state": state_to_plain(state) if state is not None else {},
            }

        def propose(self, negotiator_id, state):
            fallback = super().propose(negotiator_id, state)
            observation = self._base_observation("propose", negotiator_id, state)
            observation["fallback_offer"] = offer_to_plain(fallback)
            decision = self._codeclash_policy.decide(observation)
            if "offer" not in decision:
                return fallback
            offer, error = normalize_offer(decision.get("offer"), self.get_nmi(negotiator_id))
            if error is not None:
                self._codeclash_policy._record_error("propose", error, invalid=True)
                return fallback
            return offer

        def respond(self, negotiator_id, state, source=""):
            fallback = super().respond(negotiator_id, state, source)
            observation = self._base_observation("respond", negotiator_id, state)
            observation["fallback_response"] = response_to_name(fallback)
            decision = self._codeclash_policy.decide(observation)
            if "response" not in decision:
                return fallback
            response, error = normalize_response(decision.get("response"))
            if error is not None:
                self._codeclash_policy._record_error("respond", error, invalid=True)
                return fallback
            return response

        def first_proposals(self):
            fallback_proposals = super().first_proposals()
            proposals = {}
            for negotiator_id, fallback in fallback_proposals.items():
                observation = self._base_observation("propose", negotiator_id)
                observation["fallback_offer"] = offer_to_plain(fallback)
                decision = self._codeclash_policy.decide(observation)
                if "offer" not in decision:
                    proposals[negotiator_id] = fallback
                    continue
                offer, error = normalize_offer(decision.get("offer"), self.get_nmi(negotiator_id))
                if error is not None:
                    self._codeclash_policy._record_error("propose", error, invalid=True)
                    proposals[negotiator_id] = fallback
                    continue
                proposals[negotiator_id] = offer
            return proposals

        def counter_all(self, offers, states) -> dict:
            fallback_responses = super().counter_all(offers, states)
            responses = {}
            for negotiator_id, raw_fallback in fallback_responses.items():
                fallback = raw_fallback or SAOResponse(ResponseType.END_NEGOTIATION, None)
                state = states.get(negotiator_id)
                observation = self._base_observation("respond", negotiator_id, state)
                observation["current_offer"] = offer_to_plain(offers.get(negotiator_id))
                observation["fallback_response"] = response_to_name(fallback.response)
                observation["fallback_offer"] = offer_to_plain(fallback.outcome)
                decision = self._codeclash_policy.decide(observation)
                if not decision:
                    responses[negotiator_id] = fallback
                    continue

                response, response_error = normalize_response(decision.get("response"))
                if response_error is not None:
                    self._codeclash_policy._record_error("respond", response_error, invalid=True)
                    responses[negotiator_id] = fallback
                    continue
                if response is None:
                    responses[negotiator_id] = fallback
                    continue
                if response in {ResponseType.ACCEPT_OFFER, ResponseType.END_NEGOTIATION}:
                    responses[negotiator_id] = SAOResponse(response, None)
                    continue

                offer = decision.get("offer", fallback.outcome)
                normalized_offer, offer_error = normalize_offer(offer, self.get_nmi(negotiator_id))
                if offer_error is not None:
                    self._codeclash_policy._record_error("respond", offer_error, invalid=True)
                    responses[negotiator_id] = fallback
                    continue
                responses[negotiator_id] = SAOResponse(ResponseType.REJECT_OFFER, normalized_offer)
            return responses

    CodeClashSCMLAgent.__name__ = safe_class_name(player_name)
    CodeClashSCMLAgent.__qualname__ = safe_class_name(player_name)
    return CodeClashSCMLAgent


def policy_stats(agent_class: type) -> dict[str, Any]:
    controllers = getattr(agent_class, "_policy_controllers", [])
    return {
        "decisions": sum(controller.decisions for controller in controllers),
        "policy_errors": sum(controller.policy_errors for controller in controllers),
        "invalid_decisions": sum(controller.invalid_decisions for controller in controllers),
        "disabled_policies": sum(1 for controller in controllers if controller.disabled),
        "policy_error_samples": [sample for controller in controllers for sample in controller.error_samples[:2]][:5],
    }


def close_policies(agent_classes: dict[str, type]) -> None:
    for agent_class in agent_classes.values():
        for controller in getattr(agent_class, "_policy_controllers", []):
            controller.close()
        agent_class._policy_controllers = []


def run_world(agent_classes: dict[str, type], *, sim_idx: int, steps: int, lines: int) -> dict:
    seed = 1729 + sim_idx
    random.seed(seed)
    np.random.seed(seed)

    player_names = list(agent_classes.keys())
    offset = sim_idx % len(player_names)
    ordered_names = player_names[offset:] + player_names[:offset]
    wrapped_classes = [agent_classes[name] for name in ordered_names] + [agent_classes[name] for name in ordered_names]
    agent_processes = [0 for _ in ordered_names] + [1 for _ in ordered_names]
    class_to_player = {cls.__name__: player for player, cls in agent_classes.items()}

    try:
        config = SCML2024OneShotWorld.generate(
            agent_types=wrapped_classes,
            agent_processes=agent_processes,
            n_steps=steps,
            n_processes=2,
            n_agents_per_process=[len(ordered_names), len(ordered_names)],
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
        player_score_lists = {player: [] for player in player_names}
        details = []
        for agent_id, score in raw_scores.items():
            world_agent = world.agents[agent_id]
            player = class_to_player.get(world_agent.short_type_name)
            if player is None:
                continue
            numeric_score = float(score)
            player_score_lists[player].append(numeric_score)
            details.append(
                {
                    "sim": sim_idx,
                    "player": player,
                    "world_agent_id": agent_id,
                    "score": numeric_score,
                    **policy_stats(agent_classes[player]),
                }
            )
        player_scores = {
            player: float(sum(scores) / len(scores)) if scores else 0.0 for player, scores in player_score_lists.items()
        }
    except Exception as exc:
        player_scores = {player: CRASH_SCORE for player in player_names}
        details = [
            {
                "sim": sim_idx,
                "player": player,
                "score": CRASH_SCORE,
                "status": "error",
                "error": f"{type(exc).__name__}: {exc}",
                "traceback": traceback.format_exc(limit=5),
                **policy_stats(agent_classes[player]),
            }
            for player in player_names
        ]
    finally:
        close_policies(agent_classes)

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
    parser.add_argument("--decision-timeout", type=float, default=3.0)
    parser.add_argument("--max-policy-errors", type=int, default=8)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    if args.sims < 1:
        parser.error("--sims must be at least 1")
    if args.steps < 1:
        parser.error("--steps must be at least 1")
    if args.lines < 1:
        parser.error("--lines must be at least 1")
    if args.decision_timeout <= 0:
        parser.error("--decision-timeout must be positive")
    if args.max_policy_errors < 1:
        parser.error("--max-policy-errors must be at least 1")

    agent_classes = {
        name: build_agent_class(
            name, path, decision_timeout=args.decision_timeout, max_policy_errors=args.max_policy_errors
        )
        for name, path in args.agent
    }
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
