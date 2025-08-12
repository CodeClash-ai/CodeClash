import os
from abc import ABC, abstractmethod

from dotenv import load_dotenv
from minisweagent import Environment

from codeclash.constants import GH_ORG

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
        self.round = format_vars["round"]
        self.format_vars = format_vars

    def commit(self):
        """Commit changes to the agent's codebase."""
        rounds = self.format_vars["rounds"]
        for cmd in [
            "git add -A",
            f"git commit --allow-empty -m 'Round {self.round}/{rounds} Update'",
        ]:
            self.environment.execute(cmd)
        print(f"Committed changes for {self.name} for round {self.round}/{rounds}")

    def push(self):
        """Push codebase to a branch on the game's remote repository."""
        token = os.getenv("GITHUB_TOKEN")
        if not token:
            raise ValueError("GITHUB_TOKEN environment variable is required")

        for cmd in [
            f"git remote add origin https://x-access-token:{token}@github.com/{GH_ORG}/{self.name}.git",
            "git push -u origin main",
        ]:
            self.environment.execute(cmd)

    @abstractmethod
    def run(self):
        """Given the observation / recap, update the codebase"""
