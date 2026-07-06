"""Dummy opponent: always defer to the trusted greedy fallback.

Returning {} at every turn means the runtime's built-in GreedySyncAgent drives this
player. Used as the baseline opponent in the pilot smoke test.
"""


def decide(observation):
    return {}
