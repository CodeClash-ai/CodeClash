# ABIDES CodeClash Workspace

Edit `abides_agent.py`.

Your file must define `decide(observation)`. The arena calls this function with a plain dictionary
and expects declarative limit-order intents:

```python
def decide(observation):
    last_trade = observation["last_trade"] or 100_000
    if observation["position"] < 20:
        return [{"side": "buy", "quantity": 5, "limit_price": last_trade + 50}]
    return []
```

The trusted CodeClash runtime owns the ABIDES kernel, exchange, ledgers, and order objects. Submitted
code only receives observations and returns intents. The runtime validates and clamps each order
before submitting it to ABIDES.

Observation fields include `symbol`, `cash`, `position`, `best_bid`, `best_ask`, `market_open`, and
`limits`. Supported order fields are `side` (`"buy"` or `"sell"`), `quantity`, and `limit_price`.

The arena runs compact ABIDES market simulations and scores agents by average mark-to-market profit
across identical seeded market worlds.
