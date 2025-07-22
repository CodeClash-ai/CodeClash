import logging
from abc import ABC, abstractmethod
from pathlib import Path
from uuid import uuid4

from codegames.constants import LOGS_DIR


class CodeGame(ABC):
    def __init__(self, config: dict):
        self.config = config
        self.rounds = self.config["game"].get("rounds", 1)
        self.round = 0
        self.game_id = f"{self.name}-{uuid4().hex[:6]}"
        self.logger = logging.getLogger(self.game_id)
        self.log_path = (LOGS_DIR / self.game_id).resolve()
        self.log_path.mkdir(parents=True, exist_ok=True)

        # Configure logger to write to file and console
        if not self.logger.handlers:
            # Create file handler
            log_file = self.log_path / "main.log"
            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(logging.INFO)

            # Create console handler
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)

            # Create formatter
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            file_handler.setFormatter(formatter)
            console_handler.setFormatter(formatter)

            # Add handlers to logger
            self.logger.addHandler(file_handler)
            self.logger.addHandler(console_handler)
            self.logger.setLevel(logging.INFO)

    @abstractmethod
    def cleanup(self):
        """Cleanup any artifacts created by the game."""

    @abstractmethod
    def setup(self, config: dict):
        """Setup the logic necessary for running a game."""

    @abstractmethod
    def setup_codebase(self, dest: str) -> Path:
        """Setup the codebase for a player. Returns the path to the codebase."""

    @abstractmethod
    def run_round(self, agents: list[any]) -> Path:
        """
        Run a single round of the game with the given agents.

        Returns a directory containing logs and results of the round(s).
        """

    @property
    def round_log_path(self) -> Path:
        """
        Get the path to the current round's log file.
        """
        return self.log_path / f"round_{self.round}.log"
