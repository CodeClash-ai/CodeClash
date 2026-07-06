"""Pilot port of SCML's GreedyOneShotAgent to the CodeClash `decide()` contract.

Source: scml/oneshot/agents/greedy.py (GreedyOneShotAgent) in yasserfarouk/scml.
The upstream agent is an ``OneShotAgent`` subclass with methods ``propose`` /
``respond`` / ``best_offer`` and persistent per-step price memory. This arena instead
calls a stateless ``decide(observation)`` and hands plain dicts, so the port:

  * maps the two entry points via ``observation["event"]`` ("propose" / "respond");
  * reads world state from ``observation["awi"]`` (uses ``needed_sales`` /
    ``needed_supplies`` directly, which the upstream ``_needed`` only approximated
    via ``exogenous_contract_summary`` — cleaner and exposed here);
  * derives the linear concession threshold from ``state["relative_time"]``
    (upstream used ``state.step / nmi.n_steps``; nmi.n_steps is not exposed here);
  * DROPS the best-price-slack opponent memory (``_best_opp_*``), because we get no
    ``on_negotiation_success`` callback in ``decide``. This keeps the faithful greedy
    conceision-over-time behavior; the slack refinement is the one intentional loss.

Returns {} anywhere the inputs are missing so the trusted greedy fallback takes over
rather than erroring (an unhandled exception floors the score).
"""

QUANTITY, TIME, UNIT_PRICE = 0, 1, 2
_CONCESSION_EXPONENT = 0.4  # fixed (upstream randomizes in [0.2, 1.0]); deterministic here


def _issue_bounds(issues, idx):
    issue = issues[idx]
    return int(issue["min"]), int(issue["max"])


def _is_selling(awi, nmi):
    """A negotiation is a sale iff its product is my output product."""
    product = nmi.get("annotation", {}).get("product")
    return product == awi.get("my_output_product")


def _threshold(state):
    """Linear concession: 1.0 (hold best price) at the start -> 0.0 (concede) at the end."""
    rt = state.get("relative_time")
    if rt is None:
        return 1.0
    return (1.0 - float(rt)) ** _CONCESSION_EXPONENT


def _good_price(awi, nmi, state):
    """The price to offer/accept, conceding from best toward worst over time."""
    up_min, up_max = _issue_bounds(nmi["issues"], UNIT_PRICE)
    th = _threshold(state)
    if _is_selling(awi, nmi):
        return int(round(up_min + th * (up_max - up_min)))  # seller: high early, concede down
    return int(round(up_max - th * (up_max - up_min)))  # buyer:  low early, concede up


def _my_needs(awi, nmi):
    return awi.get("needed_sales", 0) if _is_selling(awi, nmi) else awi.get("needed_supplies", 0)


def _best_offer(awi, nmi, state):
    """Quantity sized to remaining need (clamped to the issue range); price = good price."""
    needs = _my_needs(awi, nmi)
    if not needs or needs <= 0:
        return None
    q_min, q_max = _issue_bounds(nmi["issues"], QUANTITY)
    quantity = max(q_min, min(int(needs), q_max))
    t_min, t_max = _issue_bounds(nmi["issues"], TIME)
    time = max(t_min, min(int(awi.get("current_step", t_min)), t_max))
    return [quantity, time, _good_price(awi, nmi, state)]


def _is_good_price(awi, nmi, state, price):
    up_min, up_max = _issue_bounds(nmi["issues"], UNIT_PRICE)
    span = up_max - up_min
    if span <= 0:
        return True
    th = _threshold(state)
    if _is_selling(awi, nmi):
        return (price - up_min) >= th * span
    return (up_max - price) >= th * span


def decide(observation):
    try:
        event = observation.get("event")
        awi = observation.get("awi") or {}
        nmi = observation.get("nmi") or {}
        issues = nmi.get("issues") or []
        if len(issues) < 3:
            return {}  # no valid negotiation ranges -> defer to fallback

        if event == "propose":
            offer = _best_offer(awi, nmi, observation.get("state") or {})
            return {"offer": offer} if offer else {}

        if event == "respond":
            state = observation.get("state") or {}
            current = observation.get("current_offer") or state.get("current_offer")
            if not current or len(current) < 3:
                return {}

            needs = _my_needs(awi, nmi)
            if not needs or needs <= 0:
                return {"response": "end"}  # nothing more to trade

            if current[QUANTITY] > needs:  # too much -> reject, counter with my best
                counter = _best_offer(awi, nmi, state)
                return {"response": "reject", "offer": counter} if counter else {"response": "reject"}

            if _is_good_price(awi, nmi, state, current[UNIT_PRICE]):
                return {"response": "accept"}
            counter = _best_offer(awi, nmi, state)
            return {"response": "reject", "offer": counter} if counter else {"response": "reject"}

        return {}
    except Exception:
        return {}  # never crash the world; fall back to greedy
