import os
import subprocess
from abc import ABC, abstractmethod
from collections import Counter
from pathlib import Path
from typing import Any
from uuid import uuid4

from minisweagent.environments.docker import DockerEnvironment

from codeclash.constants import DIR_LOGS, DIR_WORK, GH_ORG
from codeclash.games.utils import copy_between_containers
from codeclash.utils.environment import assert_zero_exit_code


class CodeGame(ABC):
    name: str

    def __init__(self, config: dict):
        self.url_gh: str = f"git@github.com:{GH_ORG}/{self.name}.git"
        self.artifacts: list[Path] = []
        self.scoreboard: list[tuple[int, str]] = []
        self.config: dict = config["game"]
        self.rounds: int = self.config.get("rounds", 1)
        self.round: int = 0
        self.game_id: str = f"{self.name}{uuid4().hex[:6]}"
        self.log_path: Path = (DIR_WORK / DIR_LOGS / self.game_id).resolve()
        self.environment: DockerEnvironment = self.get_environment()
        assert len(config["players"]) >= 2, "At least two players are required"

    @property
    def image_name(self) -> str:
        return f"codeclash/{self.name.lower()}"

    def build_image(self):
        """
        Build a Docker image for the game using the Dockerfile in the codebase.
        """

        # Check if container exists using subprocess
        result = subprocess.run(
            f"docker images -q {self.image_name}",
            shell=True,
            capture_output=True,
            text=True,
        )
        if result.stdout.strip():
            return

        # Build the Docker image
        result = subprocess.run(
            f"docker build -t {self.image_name} -f docker/{self.name}.Dockerfile .",
            shell=True,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            print(f"✅ Built Docker image {self.image_name}")
        else:
            print(f"❌ Failed to build Docker image: {result.stderr}")
            raise

    def end(self, cleanup: bool = False):
        print(Counter([x[1] for x in self.scoreboard]))
        if cleanup:
            for artifact in self.artifacts:
                if artifact.exists():
                    subprocess.run(f"rm -rf {artifact}", shell=True)
            print(f"🧼 Cleaned up {self.name} game")

    def get_environment(self) -> DockerEnvironment:
        """Get docker container ID with the game code installed."""
        self.build_image()
        environment = DockerEnvironment(
            image=self.image_name,
            cwd=str(DIR_WORK),
            env={"GITHUB_TOKEN": os.getenv("GITHUB_TOKEN", "")},
        )
        # Reinitialize git
        for cmd in [
            "rm -rf .git/",
            "git init",
            "git branch -m main",
            'git config --global user.email "player@codeclash.com"',
            'git config --global user.name "Player"',
            "git config --global commit.gpgsign false",
            "git add -A",
            "git commit -m 'init'",
        ]:
            assert_zero_exit_code(environment.execute(cmd))
        return environment

    def _pre_round_setup(self, agents: list[Any]):
        """Copy agent codebases into game's container and make round log file"""
        self.round += 1
        print(f"▶️ Running {self.name} round {self.round}...")

        # Copy agent codebases into game's container
        for agent in agents:
            copy_between_containers(
                src_container=agent.environment,
                dest_container=self.environment,
                src_path=DIR_WORK,
                dest_path=f"/{agent.name}",
            )

        # Ensure the log path + file exists
        assert_zero_exit_code(self.environment.execute(f"mkdir -p {self.log_path}"))
        assert_zero_exit_code(self.environment.execute(f"touch {self.round_log_path}"))

    @abstractmethod
    def determine_winner(self, agents: list[Any]) -> Any:
        """Determine the winner of the game based on the round results, updates scoreboard"""
        pass

    @abstractmethod
    def execute_round(self, agents: list[Any]):
        """Subclasses implement their game-specific logic here, must write results to round_log_path"""
        pass

    def _post_round_setup(self, agents: list[Any]):
        for agent in agents:
            copy_between_containers(
                self.environment,
                agent.environment,
                self.round_log_path,
                f"{agent.environment.config.cwd}/logs/round_{self.round}.log",
            )
            print(f"Copied round log to {agent.name}'s container.")
        print(f"Round {self.round} completed.")

    def run_round(self, agents: list[Any]):
        """
        Run a single round of the game with the given agents.

        Returns a directory containing logs and results of the round(s).
        """
        self._pre_round_setup(agents)
        self.execute_round(agents)
        self.determine_winner(agents)
        self._post_round_setup(agents)

    @property
    def round_log_path(self) -> Path:
        """
        Get the path to the current round's log file.
        """
        return self.log_path / f"round_{self.round}.log"
