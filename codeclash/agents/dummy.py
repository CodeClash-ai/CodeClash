from pathlib import Path

from codeclash.agents.abstract import Agent


class DummyAgent(Agent):
    """A dummy agent that does nothing. Mainly for testing purposes."""

    def __init__(self, config: dict, game):
        super().__init__(config, game)

    def step(self, round_log: Path):
        return
