# Porting an SCML OneShot agent to the CodeClash `decide()` contract

You are porting ONE competition agent from `yasserfarouk/scml-agents` into a single
self-contained `scml_agent.py` that defines **one function**: `decide(observation)`.
A fully-worked, validated reference port lives at
`scripts/ladder/examples/scml_agent.py` (GreedyOneShotAgent) — read it first;
mirror its structure and defensive style.

## The runtime (how your `decide` is called)

The trusted runtime owns a real SCML agent (base class `GreedySyncAgent`) and calls your
`decide(observation)` at each negotiation turn. `observation` is a plain dict:

```
observation = {
  "event":         "propose" | "respond",   # which decision is being asked
  "player":        "<name>",
  "negotiator_id": "<id>" | None,
  "awi": {                                    # agent-world-info (all plain numbers/lists)
     "current_step", "n_steps", "n_lines", "max_n_lines",
     "current_balance", "current_inventory",
     "current_exogenous_input_quantity", "current_exogenous_input_price",
     "current_exogenous_output_quantity", "current_exogenous_output_price",
     "current_disposal_cost", "current_shortfall_penalty",
     "my_input_product", "my_output_product",
     "is_first_level", "is_middle_level", "is_last_level",
     "needed_sales", "needed_supplies",       # <-- USE THESE for "how much do I still need"
     "my_suppliers", "my_consumers",
  },
  "nmi": {                                    # negotiation-mechanism-info
     "annotation": { "product": <int>, "buyer": <id>, "seller": <id>, ... },
     "issues": [ {"name","min","max","values"},  # [0]=QUANTITY, [1]=TIME, [2]=UNIT_PRICE
                 {...}, {...} ],
  },
  "state": { "step": <int>, "relative_time": <float 0..1>, "current_offer": [q,t,up] | None },
  # on "respond": observation["current_offer"] and/or state["current_offer"] holds the opponent offer
  "fallback_offer":    [q,t,up] | None,       # what the greedy fallback would offer
  "fallback_response": "accept"|"reject"|"end",
}
```

### What to return
- On `event == "propose"`: `{"offer": [quantity, time, unit_price]}` — three **ints**, each
  within its issue's `[min, max]`. Out-of-range/non-int → counted as a policy error, fallback used.
- On `event == "respond"`: `{"response": "accept" | "reject" | "end"}`. When rejecting you MAY
  include a counter: `{"response": "reject", "offer": [q,t,up]}`.
- Return `{}` or `None` at any point to defer to the trusted greedy fallback (safe default).

### Hard rules
- **Never import `scml`, `negmas`, `numpy`, or anything outside the stdlib.** The port must be
  pure-Python stdlib only — you only have the observation dict. Re-express the strategy's math
  from scratch.
- **Never raise.** Wrap the body in `try/except` returning `{}` (see reference). An unhandled
  exception floors the score.
- `is_selling` = `nmi["annotation"].get("product") == awi.get("my_output_product")`.
- "How much I still need" = `awi["needed_sales"]` if selling else `awi["needed_supplies"]`.
- Concession over time: use `state["relative_time"]` (0 at start → 1 at deadline) instead of
  `state.step / nmi.n_steps` (n_steps isn't exposed on nmi).
- No cross-call state is guaranteed; if the original kept per-step memory (opponent price models,
  `on_negotiation_success`), you may keep **module-level** dicts keyed by negotiator_id, but you
  get NO success/step callbacks — approximate or drop that refinement and note it in the docstring.

## Mapping the source's methods
- source `propose(negotiator_id, state)` / `first_proposals` → your `event=="propose"` branch.
- source `respond(...)` / `counter_all(offers, states)` → your `event=="respond"` branch.
- source `best_offer` / price helpers (`_find_good_price`, `_price_range`, `_th`) → inline as
  plain functions over the observation (reference port shows the pattern).

## If the bot is RL / learned / infeasible
Some agents (q-learning, PPO, regression on trained weights) can't be reproduced without their
weights/deps. In that case: port the **heuristic core** if one exists (many have a rule-based
path); otherwise DO NOT fake it — return a short note in your report that the bot is
RL-weight-dependent and should be skipped, and still write a best-effort heuristic port only if
faithful. Log the reason.

## Deliverable
Write your port to `scripts/ladder/ports/<YEAR>__<TEAM>.py`
(e.g. `scml2024__team_193.py`). It must `python3 -c "import ast; ast.parse(open(FILE).read())"`
cleanly and define a top-level `decide`. Keep a concise module docstring naming the source and
noting any simplifications/dropped features.
