import subprocess
from abc import ABC, abstractmethod
from collections import Counter
from pathlib import Path
from uuid import uuid4

from minisweagent.environments.docker import DockerEnvironment

from codeclash.constants import DIR_LOGS, DIR_WORK
from codeclash.games.utils import copy_between_containers


class CodeGame(ABC):
    name: str

    def __init__(self, config: dict):
        self.artifacts: list[Path] = []
        self.scoreboard: list[tuple[int, str]] = []
        self.config = config
        self.rounds = self.config.get("rounds", 1)
        self.round = 0
        self.game_id = f"{self.name}{uuid4().hex[:6]}"
        self.log_path = (DIR_WORK / DIR_LOGS / self.game_id).resolve()
        self.container = self.get_container()

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

    def get_container(self) -> DockerEnvironment:
        """Get docker container ID with the game code installed."""
        self.build_image()
        container = DockerEnvironment(
            image=self.image_name,
            cwd=str(DIR_WORK),
        )
        return container

    def _pre_round_setup(self, agents: list[any]):
        """Copy agent codebases into game's container and make round log file"""
        self.round += 1
        print(f"▶️ Running {self.name} round {self.round}...")

        # Copy agent codebases into game's container
        for agent in agents:
            copy_between_containers(
                src_container=agent.container,
                dest_container=self.container,
                src_path=DIR_WORK,
                dest_path=f"/{agent.name}",
            )

        # Ensure the log path + file exists
        self.container.execute(f"mkdir -p {self.log_path}")
        self.container.execute(f"touch {self.round_log_path}")

    @abstractmethod
    def determine_winner(self, agents: list[any]) -> any:
        """Determine the winner of the game based on the round results, updates scoreboard"""
        pass

    @abstractmethod
    def execute_round(self, agents: list[any]):
        """Subclasses implement their game-specific logic here, must write results to round_log_path"""
        pass

    def _post_round_setup(self, agents: list[any]):
        for agent in agents:
            copy_between_containers(
                self.container,
                agent.container,
                self.round_log_path,
                f"{agent.container.config.cwd}/logs/round_{self.round}.log",
            )
            print(f"Copied round log to {agent.name}'s container.")
        print(f"Round {self.round} completed.")

    def run_round(self, agents: list[any]):
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
