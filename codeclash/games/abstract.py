import os
import subprocess
import time
import traceback
from abc import ABC, abstractmethod
from collections import Counter
from pathlib import Path
from typing import Any

from minisweagent.environments.docker import DockerEnvironment

from codeclash.agents.abstract import Player
from codeclash.constants import DIR_LOGS, DIR_WORK, GH_ORG
from codeclash.games.utils import copy_between_containers, copy_file_from_container
from codeclash.utils.environment import assert_zero_exit_code
from codeclash.utils.log import get_logger


class CodeGame(ABC):
    name: str

    def __init__(self, config: dict):
        self.url_gh: str = f"git@github.com:{GH_ORG}/{self.name}.git"
        self.artifacts: list[Path] = []
        self.scoreboard: list[tuple[int, str]] = []
        self.config: dict = config["game"]
        self.rounds: int = self.config.get("rounds", 1)
        self.round: int = 0
        self.game_id: str = f"{self.name}{time.strftime('%y%m%d%H%M')}"
        self.log_path: Path = (DIR_WORK / DIR_LOGS / self.game_id).resolve()
        self.logger = get_logger(
            self.name, log_path=DIR_LOGS / self.game_id / "game.log", emoji="🏓"
        )
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
            self.logger.info(f"✅ Built Docker image {self.image_name}")
        else:
            self.logger.error(
                f"❌ Failed to build Docker image: {result.stderr}\n{result.stdout}{result.stderr}"
            )
            raise

    def end(self, cleanup: bool = False):
        self.logger.info(Counter([x[1] for x in self.scoreboard]))
        if cleanup:
            for artifact in self.artifacts:
                if artifact.exists():
                    subprocess.run(f"rm -rf {artifact}", shell=True)
            self.logger.info(f"🧼 Cleaned up {self.name} game")

    def get_environment(self, branch_name: str | None = None) -> DockerEnvironment:
        """Get docker container ID with the game code installed."""
        self.build_image()
        environment = DockerEnvironment(
            image=self.image_name,
            cwd=str(DIR_WORK),
            env={"GITHUB_TOKEN": os.getenv("GITHUB_TOKEN", "")},
        )
        # Ensure all future branches occur against branch
        branch_name = self.game_id if branch_name is None else branch_name
        for cmd in [
            f"git branch {branch_name}",
            f"git checkout {branch_name}",
            'git config --global user.email "player@codeclash.com"',
            'git config --global user.name "Player"',
            "git config --global commit.gpgsign false",
        ]:
            assert_zero_exit_code(environment.execute(cmd), logger=self.logger)
        return environment

    def _pre_round_setup(self, agents: list[Player]):
        """Copy agent codebases into game's container and make round log file"""
        self.round += 1
        # Notify agents of round update
        for agent in agents:
            if hasattr(agent, "on_round_update"):
                agent.on_round_update(self.round)
        self.logger.info(f"▶️ Running {self.name} round {self.round}...")

        # Copy agent codebases into game's container
        for agent in agents:
            self.logger.debug(f"Copying {agent.name}'s codebase")
            copy_between_containers(
                src_container=agent.environment,
                dest_container=self.environment,
                src_path=DIR_WORK,
                dest_path=f"/{agent.name}",
            )

        # Ensure the log path + file exists
        assert_zero_exit_code(
            self.environment.execute(f"mkdir -p {self.log_path}"), logger=self.logger
        )
        assert_zero_exit_code(
            self.environment.execute(f"touch {self.round_log_path}"), logger=self.logger
        )

    @abstractmethod
    def determine_winner(self, agents: list[Player]) -> Any:
        """Determine the winner of the game based on the round results, updates scoreboard"""
        pass

    @abstractmethod
    def execute_round(self, agents: list[Player]):
        """Subclasses implement their game-specific logic here, must write results to round_log_path"""
        pass

    def _post_round_setup(self, agents: list[Player]):
        for agent in agents:
            try:
                copy_between_containers(
                    self.environment,
                    agent.environment,
                    self.round_log_path,
                    f"{agent.environment.config.cwd}/logs/round_{self.round}.log",
                )
            except Exception:
                self.logger.error(
                    f"Error copying round log to {agent.name}'s container: {traceback.format_exc()}"
                )
            else:
                self.logger.info(f"Copied round log to {agent.name}'s container.")

            try:
                copy_file_from_container(
                    self.environment,
                    self.round_log_path,
                    DIR_LOGS / f"{self.game_id}/round_{self.round}.log",
                )
            except Exception:
                self.logger.error(
                    f"Error copying round log to {agent.name}'s container: {traceback.format_exc()}"
                )
            else:
                self.logger.info(
                    f"Copied round log from {agent.name}'s container to local log dir."
                )
        self.logger.info(f"Round {self.round} completed.")

    def run_round(self, agents: list[Player]):
        """
        Run a single round of the game with the given agents.

        Returns a directory containing logs and results of the round(s).
        """
        self._pre_round_setup(agents)
        self.execute_round(agents)
        self.determine_winner(agents)
        last_winner = self.scoreboard[-1][1]
        self.logger.info(f"Round {self.round} winner: {last_winner}")
        self._post_round_setup(agents)

    @property
    def round_log_path(self) -> Path:
        """
        Get the path to the current round's log file.
        """
        return self.log_path / f"round_{self.round}.log"
