from abc import ABC, abstractmethod
from pathlib import Path

from codegames.games.abstract import CodeGame


class Agent(ABC):
    def __init__(self, config: dict, game: CodeGame):
        self.config = config
        self.name = f"{game.game_id}.{config['name']}"
        self.codebase = game.setup_codebase(self.name)

    @abstractmethod
    def step(self, game_state: Path):
        """Given the observation / recap, upgrade the codebase"""
