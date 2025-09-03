from codeclash.agents.player import Player


class Dummy(Player):
    """A dummy player that does nothing. Mainly for testing purposes."""

    def run(self):
        pass
