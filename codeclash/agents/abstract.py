from abc import ABC, abstractmethod

from codeclash.games.abstract import CodeGame


class Agent(ABC):
    def __init__(self, config: dict, game: CodeGame):
        self.config = config
        self.name = f"{game.game_id}_{config['name']}"
        self.container = game.get_container()

    @abstractmethod
    def step(self):
        """Given the observation / recap, update the codebase"""
