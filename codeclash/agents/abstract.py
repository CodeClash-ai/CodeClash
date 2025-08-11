import os
from abc import ABC, abstractmethod

from dotenv import load_dotenv
from ghapi.all import GhApi

from codeclash.constants import GH_ORG
from codeclash.games.abstract import CodeGame

load_dotenv()


class Player(ABC):
    def __init__(self, config: dict, game: CodeGame):
        self.config = config
        self.name = f"{game.game_id}_{config['name']}"
        self.container = game.get_container()
        self.game = game

    def commit(self):
        """Commit changes to the agent's codebase."""
        for cmd in [
            "git add -A",
            f"git commit --allow-empty -m 'Round {self.game.round}/{self.game.rounds} Update'",
        ]:
            self.container.execute(cmd)
        print(
            f"Committed changes for {self.name} for round {self.game.round}/{self.game.rounds}"
        )

    def push(self):
        """Push codebase to a new repository."""
        token = os.getenv("GITHUB_TOKEN")
        if not token:
            raise ValueError("GITHUB_TOKEN environment variable is required")

        # Use HTTPS URL with token embedded for simple authentication
        GhApi(token=token).repos.create_in_org(GH_ORG, self.name)

        for cmd in [
            f"git remote add origin https://x-access-token:{token}@github.com/{GH_ORG}/{self.name}.git",
            "git push -u origin main",
        ]:
            self.container.execute(cmd)

    @abstractmethod
    def run(self):
        """Given the observation / recap, update the codebase"""
