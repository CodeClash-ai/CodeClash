from codeclash.agents.abstract import Player


class Dummy(Player):
    """A dummy player that does nothing. Mainly for testing purposes."""

    def run(self):
        pass
        # self.commit()  # now called in post_round_hook
