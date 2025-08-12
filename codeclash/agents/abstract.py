import os
from abc import ABC, abstractmethod

from dotenv import load_dotenv
from minisweagent import Environment

from codeclash.constants import GH_ORG
from codeclash.utils.environment import assert_zero_exit_code

load_dotenv()


class Player(ABC):
    def __init__(
        self,
        config: dict,
        environment: Environment,
        format_vars: dict,
    ):
        self.config = config
        self.name = f"{format_vars['game_id']}_{config['name']}"
        self.environment = environment
        self.format_vars = format_vars
        self.round = 1  # TODO: This is disconnected from game.round right now

    def commit(self):
        """Commit changes to the agent's codebase."""
        rounds = self.format_vars["rounds"]
        for cmd in [
            "git add -A",
            f"git commit --allow-empty -m 'Round {self.round}/{rounds} Update'",
        ]:
            assert_zero_exit_code(self.environment.execute(cmd))
        print(f"Committed changes for {self.name} for round {self.round}/{rounds}")
        self.round += 1  # TODO: This is disconnected from game.round right now

    def push(self):
        """Push codebase to a branch on the game's remote repository."""
        token = os.getenv("GITHUB_TOKEN")
        if not token:
            raise ValueError("GITHUB_TOKEN environment variable is required")

        for cmd in [
            f"git remote remove origin",
            f"git remote add origin https://x-access-token:{token}@github.com/{GH_ORG}/{self.format_vars['game_name']}.git",
            f"git push origin {self.name}",
        ]:
            assert_zero_exit_code(self.environment.execute(cmd))
        print(
            f"Pushed {self.name} commit history to remote repository (branch {self.name})"
        )

    @abstractmethod
    def run(self):
        """Given the observation / recap, update the codebase"""
