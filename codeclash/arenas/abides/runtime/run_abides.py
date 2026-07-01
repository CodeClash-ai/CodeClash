import argparse
import contextlib
import importlib.util
import json
import multiprocessing as mp
import os
import queue
import random
import re
import sys
import tempfile
import traceback
from pathlib import Path

import numpy as np
import pandas as pd
from agent.ExchangeAgent import ExchangeAgent
from agent.market_makers.MarketMakerAgent import MarketMakerAgent
from agent.TradingAgent import TradingAgent
from agent.ZeroIntelligenceAgent import ZeroIntelligenceAgent
from Kernel import Kernel
from util import util
from util.oracle.SparseMeanRevertingOracle import SparseMeanRevertingOracle
from util.order import LimitOrder

CRASH_SCORE = -1_000_000.0
SYMBOL = "JPM"
STARTING_CASH = 10_000_000
PLAYER_LAMBDA_A = 7e-11
MAX_ORDERS_PER_WAKEUP = 2
MAX_ORDER_QUANTITY = 20
MAX_ABS_POSITION = 200
MIN_LIMIT_PRICE = 1
MAX_LIMIT_PRICE = 1_000_000
WAKEUP_INTERVAL = "30s"


def safe_module_name(player_name: str, sim_idx: int | None = None) -> str:
    safe = re.sub(r"\W+", "_", player_name)
    if not safe or safe[0].isdigit():
        safe = f"player_{safe}"
    suffix = "" if sim_idx is None else f"_sim_{sim_idx}"
    return f"codeclash_abides_{safe.lower()}{suffix}"


def load_policy_module(player_name: str, path: str, *, sim_idx: int | None = None):
    agent_dir = str(Path(path).resolve().parent)
    sys.path.insert(0, agent_dir)
    spec = importlib.util.spec_from_file_location(safe_module_name(player_name, sim_idx), path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load module spec from {path}")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    finally:
        with contextlib.suppress(ValueError):
            sys.path.remove(agent_dir)
    if not hasattr(module, "decide") or not callable(module.decide):
        raise RuntimeError(f"{path} must define a callable decide(observation)")
    return module


def policy_worker(result_queue: mp.Queue, player: str, path: str, observation: dict, sim_idx: int) -> None:
    try:
        module = load_policy_module(player, path, sim_idx=sim_idx)
        result_queue.put({"orders": module.decide(observation)})
    except BaseException as exc:
        result_queue.put(
            {
                "error": f"{type(exc).__name__}: {exc}",
                "traceback": traceback.format_exc(limit=5),
            }
        )


def call_policy(
    player: str, path: str, observation: dict, *, sim_idx: int, timeout: float
) -> tuple[object, dict | None]:
    ctx = mp.get_context("spawn")
    result_queue = ctx.Queue(maxsize=1)
    process = ctx.Process(target=policy_worker, args=(result_queue, player, path, observation, sim_idx))
    process.start()
    process.join(max(float(timeout), 0.01))
    if process.is_alive():
        process.terminate()
        process.join(0.1)
        if process.is_alive():
            process.kill()
            process.join()
        return None, {"error": f"decide exceeded {timeout}s timeout"}

    try:
        result = result_queue.get_nowait()
    except queue.Empty:
        return None, {"error": f"decide exited with code {process.exitcode} and no result"}

    if "error" in result:
        return None, result
    return result.get("orders"), None


def make_random_state() -> np.random.RandomState:
    return np.random.RandomState(seed=np.random.randint(low=0, high=2**32, dtype="uint64"))


def normalize_int_field(value, field: str) -> int:
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, bool):
        raise ValueError(f"order {field} must be an integer")
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    if not isinstance(value, int):
        raise ValueError(f"order {field} must be an integer")
    return value


def normalize_order_intents(raw_orders) -> list[dict]:
    if raw_orders is None:
        return []
    if isinstance(raw_orders, dict):
        if "orders" in raw_orders:
            raw_orders = raw_orders["orders"]
        else:
            raw_orders = [raw_orders]
    if not isinstance(raw_orders, (list, tuple)):
        raise ValueError("decide must return an order dict, an order list, {'orders': [...]}, or None")

    normalized = []
    for raw_order in raw_orders[:MAX_ORDERS_PER_WAKEUP]:
        if not isinstance(raw_order, dict):
            raise ValueError("each order intent must be a dict")

        side = str(raw_order.get("side", "")).lower().strip()
        if side not in {"buy", "sell"}:
            raise ValueError("order side must be 'buy' or 'sell'")

        quantity = min(max(normalize_int_field(raw_order.get("quantity", 0), "quantity"), 1), MAX_ORDER_QUANTITY)
        limit_price = min(
            max(
                normalize_int_field(raw_order.get("limit_price", raw_order.get("price", 0)), "limit_price"),
                MIN_LIMIT_PRICE,
            ),
            MAX_LIMIT_PRICE,
        )
        normalized.append(
            {
                "side": side,
                "quantity": quantity,
                "limit_price": limit_price,
            }
        )

    return normalized


class ProtocolTradingAgent(TradingAgent):
    def __init__(
        self,
        *,
        policy_path: str,
        decision_timeout: float,
        sim_idx: int,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.policy_path = policy_path
        self.decision_timeout = decision_timeout
        self.sim_idx = sim_idx
        self.policy_errors: list[dict] = []
        self.orders_submitted = 0
        self.lambda_a = PLAYER_LAMBDA_A
        self.codeclash_exchange: ExchangeAgent | None = None

    def getWakeFrequency(self):
        return pd.to_timedelta(WAKEUP_INTERVAL)

    def receiveMessage(self, currentTime, msg):
        try:
            super().receiveMessage(currentTime, msg)
        except Exception as exc:
            self.policy_errors.append({"error": f"{type(exc).__name__} in receiveMessage: {exc}"})

    def wakeup(self, currentTime):
        ready_to_trade = super().wakeup(currentTime)
        if not ready_to_trade:
            return ready_to_trade

        self.getCurrentSpread(SYMBOL)
        observation = self.build_observation(currentTime)
        raw_orders, error = call_policy(
            self.name,
            self.policy_path,
            observation,
            sim_idx=self.sim_idx,
            timeout=self.decision_timeout,
        )
        if error:
            self.policy_errors.append(error)
        else:
            try:
                self.submit_order_intents(normalize_order_intents(raw_orders))
            except Exception as exc:
                self.policy_errors.append(
                    {
                        "error": f"{type(exc).__name__} while validating order intents: {exc}",
                        "traceback": traceback.format_exc(limit=5),
                    }
                )

        next_wakeup = currentTime + pd.to_timedelta(WAKEUP_INTERVAL)
        if self.mkt_close is None or next_wakeup < self.mkt_close:
            self.setWakeup(next_wakeup)
        return ready_to_trade

    def build_observation(self, currentTime) -> dict:
        try:
            bid, bid_volume, ask, ask_volume = self.getKnownBidAsk(SYMBOL)
        except KeyError:
            bid, bid_volume, ask, ask_volume = None, 0, None, 0
        last_trade = None
        if self.codeclash_exchange is not None:
            with contextlib.suppress(Exception):
                last_trade = int(self.codeclash_exchange.order_books[SYMBOL].last_trade)
        return {
            "player": self.name,
            "symbol": SYMBOL,
            "time": str(currentTime),
            "cash": int(self.holdings.get("CASH", STARTING_CASH)),
            "position": int(self.holdings.get(SYMBOL, 0)),
            "starting_cash": STARTING_CASH,
            "best_bid": None if bid is None else int(bid),
            "best_bid_volume": int(bid_volume or 0),
            "best_ask": None if ask is None else int(ask),
            "best_ask_volume": int(ask_volume or 0),
            "last_trade": last_trade,
            "market_open": self.mkt_open is not None and self.mkt_close is not None and currentTime < self.mkt_close,
            "limits": {
                "max_orders": MAX_ORDERS_PER_WAKEUP,
                "max_order_quantity": MAX_ORDER_QUANTITY,
                "max_abs_position": MAX_ABS_POSITION,
                "min_limit_price": MIN_LIMIT_PRICE,
                "max_limit_price": MAX_LIMIT_PRICE,
            },
        }

    def submit_order_intents(self, orders: list[dict]) -> None:
        position = int(self.holdings.get(SYMBOL, 0))
        for order in orders:
            signed_quantity = order["quantity"] if order["side"] == "buy" else -order["quantity"]
            if abs(position + signed_quantity) > MAX_ABS_POSITION:
                self.policy_errors.append({"error": "order skipped because it would exceed max_abs_position"})
                continue
            self.placeLimitOrder(
                SYMBOL,
                order["quantity"],
                order["side"] == "buy",
                order["limit_price"],
                ignore_risk=True,
                tag="codeclash-protocol",
            )
            position += signed_quantity
            self.orders_submitted += 1


def is_recorded_execution(exchange: ExchangeAgent, order) -> bool:
    order_book = getattr(exchange, "order_books", {}).get(getattr(order, "symbol", None))
    if order_book is None:
        return False

    order_id = getattr(order, "order_id", None)
    try:
        quantity = int(order.quantity)
    except (TypeError, ValueError, AttributeError):
        return False

    for history_window in getattr(order_book, "history", []):
        order_record = history_window.get(order_id)
        if not order_record:
            continue
        for _timestamp, transaction_quantity in order_record.get("transactions", []):
            try:
                if int(transaction_quantity) == quantity:
                    return True
            except (TypeError, ValueError):
                continue
    return False


def instrument_player_orders(player_agents: dict[str, TradingAgent], exchange: ExchangeAgent) -> dict[str, set]:
    submitted_order_ids = {player: set() for player in player_agents}

    for player, agent in player_agents.items():
        original_send_message = agent.sendMessage

        def tracked_send_message(*args, _agent=agent, _player=player, _original=original_send_message, **kwargs):
            recipient_id = args[0] if args else kwargs.get("recipientID", kwargs.get("recipient_id"))
            msg = args[1] if len(args) > 1 else kwargs.get("msg")
            body = getattr(msg, "body", {})
            order = body.get("order") if body.get("msg") == "LIMIT_ORDER" else None
            if recipient_id == exchange.id and getattr(order, "agent_id", None) == _agent.id:
                submitted_order_ids[_player].add(getattr(order, "order_id", None))
            return _original(*args, **kwargs)

        agent.sendMessage = tracked_send_message

    return submitted_order_ids


def instrument_order_books(exchange: ExchangeAgent) -> dict[str, int]:
    order_book_depth = {"count": 0}

    for order_book in exchange.order_books.values():
        original_handle_limit_order = order_book.handleLimitOrder

        def tracked_handle_limit_order(*args, _original=original_handle_limit_order, **kwargs):
            order_book_depth["count"] += 1
            try:
                return _original(*args, **kwargs)
            finally:
                order_book_depth["count"] -= 1

        order_book.handleLimitOrder = tracked_handle_limit_order

    return order_book_depth


def make_world_agents(
    policy_paths: dict[str, str],
    *,
    sim_idx: int,
    market_minutes: int,
    background_agents: int,
    decision_timeout: float,
):
    historical_date = pd.to_datetime("2019-06-28")
    mkt_open = historical_date + pd.to_timedelta("09:30:00")
    mkt_close = mkt_open + pd.to_timedelta(market_minutes, unit="m")
    symbols = {
        SYMBOL: {
            "r_bar": 100000,
            "kappa": 1.67e-12,
            "agent_kappa": 1.67e-15,
            "sigma_s": 0,
            "fund_vol": 1e-8,
            "megashock_lambda_a": 2.77778e-13,
            "megashock_mean": 1e3,
            "megashock_var": 5e4,
            "random_state": make_random_state(),
        }
    }
    oracle = SparseMeanRevertingOracle(mkt_open, mkt_close, symbols)

    agents = []
    agent_id = 0
    exchange = ExchangeAgent(
        id=agent_id,
        name="EXCHANGE_AGENT",
        type="ExchangeAgent",
        mkt_open=mkt_open,
        mkt_close=mkt_close,
        symbols=[SYMBOL],
        log_orders=False,
        book_freq=None,
        pipeline_delay=0,
        computation_delay=0,
        stream_history=10,
        random_state=make_random_state(),
    )
    agents.append(exchange)
    agent_id += 1

    agents.append(
        MarketMakerAgent(
            id=agent_id,
            name="MARKET_MAKER_AGENT",
            type="MarketMakerAgent",
            symbol=SYMBOL,
            starting_cash=STARTING_CASH,
            min_size=20,
            max_size=50,
            wake_up_freq="30s",
            log_orders=False,
            random_state=make_random_state(),
        )
    )
    agent_id += 1

    symbol_config = symbols[SYMBOL]
    for idx in range(background_agents):
        agents.append(
            ZeroIntelligenceAgent(
                id=agent_id,
                name=f"ZI_AGENT_{idx}",
                type="ZeroIntelligenceAgent",
                symbol=SYMBOL,
                starting_cash=STARTING_CASH,
                sigma_n=10000,
                r_bar=symbol_config["r_bar"],
                kappa=symbol_config["agent_kappa"],
                sigma_s=symbol_config["fund_vol"],
                q_max=10,
                sigma_pv=5e4,
                R_min=0,
                R_max=100,
                eta=1,
                lambda_a=1e-10,
                log_orders=False,
                random_state=make_random_state(),
            )
        )
        agent_id += 1

    player_agents = {}
    player_ids = {}
    player_names = list(policy_paths.keys())
    if player_names:
        offset = sim_idx % len(player_names)
        ordered_names = player_names[offset:] + player_names[:offset]
        for player_name in ordered_names:
            agent = ProtocolTradingAgent(
                id=agent_id,
                name=player_name,
                type=f"PLAYER:{player_name}",
                policy_path=policy_paths[player_name],
                decision_timeout=decision_timeout,
                sim_idx=sim_idx,
                starting_cash=STARTING_CASH,
                log_orders=False,
                random_state=make_random_state(),
            )
            agent.codeclash_exchange = exchange
            agents.append(agent)
            player_agents[player_name] = agent
            player_ids[agent_id] = player_name
            agent_id += 1

    for agent in agents:
        agent.log_to_file = False

    ledgers = {player: {"CASH": STARTING_CASH, SYMBOL: 0} for player in player_agents}
    submitted_order_ids = instrument_player_orders(player_agents, exchange)
    order_book_depth = instrument_order_books(exchange)
    original_exchange_send = exchange.sendMessage

    def scored_exchange_send(*args, **kwargs):
        recipient_id = args[0] if args else kwargs.get("recipientID", kwargs.get("recipient_id"))
        msg = args[1] if len(args) > 1 else kwargs.get("msg")
        player = player_ids.get(recipient_id)
        if player and getattr(msg, "body", {}).get("msg") == "ORDER_EXECUTED":
            order = msg.body["order"]
            order_id = getattr(order, "order_id", None)
            if (
                order_book_depth["count"] > 0
                and order_id in submitted_order_ids[player]
                and is_recorded_execution(exchange, order)
            ):
                quantity = int(order.quantity)
                signed_quantity = quantity if order.is_buy_order else -quantity
                ledgers[player][SYMBOL] += signed_quantity
                ledgers[player]["CASH"] -= signed_quantity * int(order.fill_price)
        return original_exchange_send(*args, **kwargs)

    exchange.sendMessage = scored_exchange_send

    return {
        "agents": agents,
        "player_agents": player_agents,
        "ledgers": ledgers,
        "exchange": exchange,
        "historical_date": historical_date,
        "mkt_close": mkt_close,
        "oracle": oracle,
    }


def score_player(agent: ProtocolTradingAgent, ledger: dict[str, int], final_price: int) -> tuple[float, dict]:
    try:
        cash = int(ledger.get("CASH", 0))
        shares = int(ledger.get(SYMBOL, 0))
        score = float(cash + shares * final_price - STARTING_CASH)
    except Exception as exc:
        return CRASH_SCORE, {
            "status": "error",
            "error": f"{type(exc).__name__} while scoring: {exc}",
            "traceback": traceback.format_exc(limit=5),
        }

    return score, {
        "status": "ok",
        "cash": cash,
        "shares": shares,
        "policy_errors": len(agent.policy_errors),
        "policy_error_samples": agent.policy_errors[:3],
        "orders_submitted": agent.orders_submitted,
    }


def run_player_market(
    player: str,
    path: str,
    *,
    sim_idx: int,
    market_minutes: int,
    background_agents: int,
    decision_timeout: float,
) -> dict:
    seed = 9200 + sim_idx
    random.seed(seed)
    np.random.seed(seed)
    util.silent_mode = True
    LimitOrder.silent_mode = True

    world = make_world_agents(
        {player: path},
        sim_idx=sim_idx,
        market_minutes=market_minutes,
        background_agents=background_agents,
        decision_timeout=decision_timeout,
    )
    kernel = Kernel("CodeClash ABIDES Kernel", random_state=make_random_state())
    with tempfile.TemporaryDirectory() as tmpdir:
        with open(os.devnull, "w") as devnull, contextlib.chdir(tmpdir), contextlib.redirect_stdout(devnull):
            kernel.runner(
                agents=world["agents"],
                startTime=world["historical_date"],
                stopTime=world["mkt_close"] + pd.to_timedelta("00:01:00"),
                defaultComputationDelay=50,
                defaultLatency=1,
                oracle=world["oracle"],
                skip_log=True,
                log_dir=None,
            )

    final_price = int(world["exchange"].order_books[SYMBOL].last_trade)
    agent = world["player_agents"][player]
    ledger = world["ledgers"][player]
    score, score_detail = score_player(agent, ledger, final_price)
    return {
        "score": score,
        "detail": {
            "sim": sim_idx,
            "player": player,
            "score": score,
            "final_price": final_price,
            **score_detail,
        },
    }


def run_player_market_worker(
    result_queue: mp.Queue,
    player: str,
    path: str,
    *,
    sim_idx: int,
    market_minutes: int,
    background_agents: int,
    decision_timeout: float,
) -> None:
    try:
        result_queue.put(
            run_player_market(
                player,
                path,
                sim_idx=sim_idx,
                market_minutes=market_minutes,
                background_agents=background_agents,
                decision_timeout=decision_timeout,
            )
        )
    except BaseException as exc:
        result_queue.put(
            {
                "score": CRASH_SCORE,
                "detail": {
                    "sim": sim_idx,
                    "player": player,
                    "score": CRASH_SCORE,
                    "status": "error",
                    "error": f"{type(exc).__name__}: {exc}",
                    "traceback": traceback.format_exc(limit=5),
                },
            }
        )


def run_player_market_isolated(
    player: str,
    path: str,
    *,
    sim_idx: int,
    market_minutes: int,
    background_agents: int,
    decision_timeout: float,
    player_timeout: int,
) -> dict:
    ctx = mp.get_context("spawn")
    result_queue = ctx.Queue()
    process = ctx.Process(
        target=run_player_market_worker,
        args=(result_queue, player, path),
        kwargs={
            "sim_idx": sim_idx,
            "market_minutes": market_minutes,
            "background_agents": background_agents,
            "decision_timeout": decision_timeout,
        },
    )
    process.start()
    process.join(player_timeout)
    if process.is_alive():
        process.terminate()
        process.join(2)
        if process.is_alive():
            process.kill()
            process.join()
        return {
            "score": CRASH_SCORE,
            "detail": {
                "sim": sim_idx,
                "player": player,
                "score": CRASH_SCORE,
                "status": "error",
                "error": f"player simulation exceeded {player_timeout}s timeout",
            },
        }

    try:
        return result_queue.get_nowait()
    except queue.Empty:
        return {
            "score": CRASH_SCORE,
            "detail": {
                "sim": sim_idx,
                "player": player,
                "score": CRASH_SCORE,
                "status": "error",
                "error": f"player simulation exited with code {process.exitcode} and no result",
            },
        }


def run_market(
    agent_paths: dict[str, str],
    *,
    sim_idx: int,
    market_minutes: int,
    background_agents: int,
    decision_timeout: float,
    player_timeout: int,
) -> dict:
    scores = {}
    details = []
    for player, path in agent_paths.items():
        result = run_player_market_isolated(
            player,
            path,
            sim_idx=sim_idx,
            market_minutes=market_minutes,
            background_agents=background_agents,
            decision_timeout=decision_timeout,
            player_timeout=player_timeout,
        )
        scores[player] = result["score"]
        details.append(result["detail"])

    return {"scores": scores, "details": details}


def parse_agent_arg(value: str) -> tuple[str, str]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("--agent values must be NAME=/path/to/abides_agent.py")
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
    parser.add_argument("--market-minutes", type=int, default=5)
    parser.add_argument("--background-agents", type=int, default=3)
    parser.add_argument("--decision-timeout", type=float, default=3.0)
    parser.add_argument("--player-timeout", type=int, default=60)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    if args.sims < 1:
        parser.error("--sims must be at least 1")
    if args.market_minutes < 1:
        parser.error("--market-minutes must be at least 1")
    if args.background_agents < 0:
        parser.error("--background-agents cannot be negative")
    if args.decision_timeout <= 0:
        parser.error("--decision-timeout must be positive")
    if args.player_timeout < 1:
        parser.error("--player-timeout must be at least 1")

    agent_names = [name for name, _ in args.agent]
    if len(agent_names) != len(set(agent_names)):
        parser.error("--agent names must be unique")

    agent_paths = dict(args.agent)
    totals = {name: 0.0 for name in agent_paths}
    details = []

    for sim_idx in range(args.sims):
        try:
            result = run_market(
                agent_paths,
                sim_idx=sim_idx,
                market_minutes=args.market_minutes,
                background_agents=args.background_agents,
                decision_timeout=args.decision_timeout,
                player_timeout=args.player_timeout,
            )
        except Exception as exc:
            result = {
                "scores": {name: CRASH_SCORE for name in agent_paths},
                "details": [
                    {
                        "sim": sim_idx,
                        "player": name,
                        "score": CRASH_SCORE,
                        "status": "error",
                        "error": f"{type(exc).__name__}: {exc}",
                        "traceback": traceback.format_exc(limit=5),
                    }
                    for name in agent_paths
                ],
            }
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
