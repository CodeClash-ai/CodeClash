import os
import subprocess
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from minisweagent.environments.docker import DockerEnvironment

from codeclash.agents.abstract import Player
from codeclash.constants import DIR_LOGS, DIR_WORK, GH_ORG
from codeclash.utils.environment import assert_zero_exit_code, copy_between_containers
from codeclash.utils.log import get_logger


@dataclass
class RoundStats:
    winner: str
    scores: dict[str, float]  # Map of player to game metric (e.g. # of wins, assets accumulated)
    details: dict[str, Any] = None  # Optional, for game-specific info

    def __str__(self) -> str:
        return "\n".join([f"- Winner: {self.winner}", f"- Scores: {self.scores}"])


@dataclass
class RoundData:
    logs: list[str]
    results: list[str]


@dataclass
class RoundRecord:
    data: RoundData
    stats: RoundStats


class CodeGame(ABC):
    name: str

    def __init__(self, config: dict, *, tournament_id: str, local_output_dir: Path):
        """The CodeGame class is responsible for running games, i.e., taking a list of code
        from different agents/players and running them against each other.
        It also provides the environments for the game and agents to run in.

        The central method is `run_round`, which takes a list of agents and returns the winner of the round.

        At the end of the the tournament, run the `end` method to clean up the game and agents and write the metadata.

        Args:
            config: The overall config for the tournament.
            tournament_id: The id of the tournament.
            local_output_dir: The host/local directory to write logs to.
        """
        self.url_gh: str = f"git@github.com:{GH_ORG}/{self.name}.git"
        self.artifacts: list[Path] = []
        """Artifact objects that we might want to clean up after the game."""
        self.config: dict = config
        self._metadata: dict = {
            "name": self.name,
            "config": self.config["game"],
            "game_id": tournament_id,
            "created_timestamp": int(time.time()),
        }
        self.log_env: Path = (DIR_WORK / DIR_LOGS / self.game_id).resolve()
        self.log_local: Path = local_output_dir
        self.logger = get_logger(self.name, log_path=self.log_local / "game.log", emoji="🏓")
        self.environment: DockerEnvironment = self.get_environment()
        """The running docker environment for executing the game"""

    @property
    def game_config(self) -> dict:
        return self.config["game"]

    @property
    def game_id(self) -> str:
        return self._metadata["game_id"]

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
            (
                "export $(cat .env | xargs);"
                f"docker build --build-arg GITHUB_TOKEN=$GITHUB_TOKEN -t {self.image_name} -f docker/{self.name}.Dockerfile ."
            ),
            shell=True,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            self.logger.info(f"✅ Built Docker image {self.image_name}")
        else:
            self.logger.error(f"❌ Failed to build Docker image: {result.stderr}\n{result.stdout}{result.stderr}")
            raise RuntimeError(f"Failed to build Docker image: {result.stderr}")

    def get_metadata(self) -> dict:
        """This is what we write to metadata.json.
        You can subclass extend this to add more details for specific games.
        """
        return self._metadata

    def end(self, cleanup: bool = False):
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
        # Logger setting will likely not take effect for initial container creation logs
        environment.logger = get_logger("environment", emoji="🪴")
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
        """Copy agent codebases into game's container"""
        # Copy agent codebases into game's container
        for agent in agents:
            self.logger.debug(f"Copying {agent.name}'s codebase")
            copy_between_containers(
                src_container=agent.environment,
                dest_container=self.environment,
                src_path=DIR_WORK,
                dest_path=f"/{agent.name}",
            )

        # Ensure the log directory exists
        assert_zero_exit_code(
            self.environment.execute(f"mkdir -p {self.log_env}"),
            logger=self.logger,
        )

    @abstractmethod
    def get_stats(self, result_outputs: list[str], agents: list[Player]) -> RoundStats:
        """Determine the winner of the game based on the result output.

        Args:
            result_outputs: The specific output(s) containing winning information
            agents: List of agents participating in the round

        Returns:
            RoundStats object
        """
        pass

    @abstractmethod
    def execute_round(self, agents: list[Player]) -> RoundData:
        """Subclasses implement their game-specific logic here.
        This is the low level implementation, you probably want to use run_round instead, which
        includes the pre-round setup, post-round setup, and winner determination.

        Returns:
            RoundData object
        """
        pass

    def run_round(self, agents: list[Player]) -> RoundRecord:
        """
        Run a single round of the game with the given agents.

        Returns the log output, result output, and winner name. All bookkeeping should be
        handled by the tournament class.
        """
        self._pre_round_setup(agents)
        data = self.execute_round(agents)
        stats = self.get_stats(data.results, agents)
        return RoundRecord(data=data, stats=stats)
