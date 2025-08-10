from abc import ABC, abstractmethod

from codeclash.games.abstract import CodeGame


class Player(ABC):
    def __init__(self, config: dict, game: CodeGame):
        self.config = config
        self.name = f"{game.game_id}_{config['name']}"
        self.container = game.get_container()

    @abstractmethod
    def run(self):
        """Given the observation / recap, update the codebase"""
