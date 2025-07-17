from abc import ABC, abstractmethod
from codegames.games.abstract import CodeGame
from pathlib import Path


class Agent(ABC):
    def __init__(
        self,
        config: dict,
        game: CodeGame
    ):
        self.config = config
        self.name = f"{game.game_id}.{config['name']}"
        self.codebase = game.setup_codebase(self.name)

    @abstractmethod
    def step(self, game_state: Path):
        """Given the observation / recap, upgrade the codebase"""