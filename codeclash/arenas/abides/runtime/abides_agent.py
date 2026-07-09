def decide(observation):
    """Return order intents for the trusted ABIDES runtime to validate and submit."""
    position = observation.get("position", 0)
    best_bid = observation.get("best_bid")
    best_ask = observation.get("best_ask")
    last_trade = observation.get("last_trade") or 100_000

    orders = []
    if best_ask is not None and position < 20:
        orders.append({"side": "buy", "quantity": 5, "limit_price": best_ask})
    elif position < 20:
        orders.append({"side": "buy", "quantity": 5, "limit_price": last_trade + 50})

    if best_bid is not None and position > -20:
        orders.append({"side": "sell", "quantity": 5, "limit_price": best_bid})
    elif position > -20:
        orders.append({"side": "sell", "quantity": 5, "limit_price": last_trade - 50})

    return orders
