import os
from abc import ABC, abstractmethod

from dotenv import load_dotenv
from minisweagent import Environment

from codeclash.agents.utils import GameContext
from codeclash.constants import DIR_LOGS, GH_ORG
from codeclash.utils.environment import assert_zero_exit_code
from codeclash.utils.log import get_logger

load_dotenv()


class Player(ABC):
    def __init__(
        self,
        config: dict,
        environment: Environment,
        game_context: GameContext,
    ):
        self.config = config
        self.name = config["name"]
        self.environment = environment
        self.game_context = game_context
        self.game_context.render_and_set_prompts()
        self.logger = get_logger(
            self.name,
            log_path=DIR_LOGS / game_context.id / f"{self.name}.log",
            emoji="👤",
        )

    @property
    def branch_name(self):
        """Get the branch name for the agent's codebase."""
        return f"{self.game_context.id}.{self.name}"

    def commit(self):
        """Commit changes to the agent's codebase."""
        r, rounds = self.game_context.round, self.game_context.rounds
        for cmd in [
            "git add -A",
            f"git commit --allow-empty -m 'Round {r}/{rounds} Update'",
        ]:
            assert_zero_exit_code(self.environment.execute(cmd), logger=self.logger)
        self.logger.info(f"Committed changes for {self.name} for round {r}/{rounds}")

    def on_round_update(self, new_round: int):
        """Update the agent's round to match the game round."""
        self.game_context.round = new_round
        self.game_context.render_and_set_prompts()

    def push(self):
        """Push codebase to a branch on the game's remote repository."""
        token = os.getenv("GITHUB_TOKEN")
        if not token:
            raise ValueError("GITHUB_TOKEN environment variable is required")

        for cmd in [
            "git remote remove origin",
            f"git remote add origin https://x-access-token:{token}@github.com/{GH_ORG}/{self.game_context.name}.git",
            f"git push origin {self.branch_name}",
        ]:
            assert_zero_exit_code(self.environment.execute(cmd), logger=self.logger)
        self.logger.info(
            f"Pushed {self.name} commit history to remote repository (branch {self.branch_name})"
        )

    @abstractmethod
    def run(self):
        """Given the observation / recap, update the codebase"""
