from codeclash.agents.abstract import Player


class Dummy(Player):
    """A dummy player that does nothing. Mainly for testing purposes."""

    def __init__(self, config: dict, game):
        super().__init__(config, game)

    def run(self):
        return
