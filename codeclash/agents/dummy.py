from codeclash.agents.abstract import Player


class Dummy(Player):
    """A dummy player that does nothing. Mainly for testing purposes."""

    def run(self):
        self.commit()
