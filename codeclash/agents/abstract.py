from abc import ABC, abstractmethod
from pathlib import Path

from codeclash.games.abstract import CodeGame


class Agent(ABC):
    def __init__(self, config: dict, game: CodeGame):
        self.config = config
        self.name = f"{game.game_id}_{config['name']}"
        self.codebase = game.setup_codebase(self.name).resolve()

    @abstractmethod
    def step(self, round_log: Path):
        """Given the observation / recap, update the codebase"""
