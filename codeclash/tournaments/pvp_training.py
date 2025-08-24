"""
PvP training mode where multiple agents compete against each other.
"""

from codeclash.agents import get_agent
from codeclash.agents.abstract import Player
from codeclash.games import get_game
from codeclash.games.abstract import CodeGame
from codeclash.tournaments.abstract import AbstractTournament
from codeclash.utils.log import get_logger


class PvpTraining(AbstractTournament):
    def __init__(
        self, config: dict, *, cleanup: bool = False, push_agent: bool = False
    ):
        self.config = config
        self.cleanup_on_end = cleanup
        self.push_agent = push_agent
        self.game: CodeGame = get_game(self.config)
        self.agents: list[Player] = []
        for agent_conf in self.config["players"]:
            self.agents.append(get_agent(agent_conf, self.config["prompts"], self.game))
        self.logger = get_logger(self.game.name)

    def run(self) -> None:
        """Main execution function that runs all rounds."""
        try:
            for round_num in range(1, self.game.rounds + 1):
                self.run_training_round(round_num)
        finally:
            self.cleanup()

    def run_training_round(self, round_num: int) -> None:
        """Execute a single training round."""
        self.game.run_round(self.agents)
        for agent in self.agents:
            self.run_agent(agent, round_num)

    def run_agent(self, agent: Player, round_num: int) -> None:
        """Run a single agent for the current round."""
        agent.pre_run_hook(new_round=round_num)
        agent.run()
        agent.post_run_hook(round=round_num)

    def cleanup(self) -> None:
        """Clean up game resources and push agents if requested."""
        self.game.end(self.cleanup_on_end)
        if self.push_agent:
            for agent in self.agents:
                agent.push()
