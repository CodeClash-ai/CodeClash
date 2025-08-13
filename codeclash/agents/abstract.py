import os
from abc import ABC, abstractmethod

from dotenv import load_dotenv
from minisweagent import Environment

from codeclash.constants import DIR_LOGS, GH_ORG
from codeclash.utils.environment import assert_zero_exit_code
from codeclash.utils.log import get_logger

load_dotenv()


class Player(ABC):
    def __init__(
        self,
        config: dict,
        environment: Environment,
        template_vars: dict,
    ):
        self.config = config
        self.name = f"{template_vars['game_id']}_{config['name']}"
        self.environment = environment
        self.template_vars = template_vars
        self.logger = get_logger(
            self.name,
            log_path=DIR_LOGS / template_vars["game_id"] / f"{self.name}.log",
            emoji="👤",
        )

    def commit(self):
        """Commit changes to the agent's codebase."""
        rounds = self.template_vars["rounds"]
        for cmd in [
            "git add -A",
            f"git commit --allow-empty -m 'Round {self.round}/{rounds} Update'",
        ]:
            assert_zero_exit_code(self.environment.execute(cmd))
        self.logger.info(
            f"Committed changes for {self.name} for round {self.round}/{rounds}"
        )

    def on_round_update(self, new_round: int):
        """Update the agent's round to match the game round."""
        self.round = new_round
        self.template_vars["round"] = new_round

    def push(self):
        """Push codebase to a branch on the game's remote repository."""
        token = os.getenv("GITHUB_TOKEN")
        if not token:
            raise ValueError("GITHUB_TOKEN environment variable is required")

        for cmd in [
            "git remote remove origin",
            f"git remote add origin https://x-access-token:{token}@github.com/{GH_ORG}/{self.template_vars['game_name']}.git",
            f"git push origin {self.name}",
        ]:
            assert_zero_exit_code(self.environment.execute(cmd))
        print(
            f"Pushed {self.name} commit history to remote repository (branch {self.name})"
        )

    @abstractmethod
    def run(self):
        """Given the observation / recap, update the codebase"""
