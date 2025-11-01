import os
import random
import subprocess
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from minisweagent.environments.docker import DockerEnvironment

from codeclash.agents.player import Player
from codeclash.constants import DIR_LOGS, DIR_WORK, GH_ORG, RESULT_TIE
from codeclash.utils.aws import is_running_in_aws_batch, pull_game_container_aws_ecr
from codeclash.utils.environment import assert_zero_exit_code, copy_between_containers, copy_from_container
from codeclash.utils.log import get_logger


class PlayerStats:
    def __init__(self, name: str):
        self.name = name
        self.invalid_reason: str = ""
        self.score: float = 0.0
        self.valid_submit = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "invalid_reason": self.invalid_reason,
            "score": self.score,
            "valid_submit": self.valid_submit,
        }


class RoundStats:
    def __init__(self, round_num: int, agents: list[Player]):
        self.winner = None
        self.round_num = round_num
        # Map of player to game metric (e.g. # of wins, assets accumulated)
        self.scores: dict[str, float] = {a.name: 0.0 for a in agents}
        self.player_stats: dict[str, PlayerStats] = {agent.name: PlayerStats(name=agent.name) for agent in agents}
        self.details: list[str] = []

    def __str__(self) -> str:
        rv = [f"In round {self.round_num}, the winner is {self.winner}.", "\nSummary of player performance:"]
        for player, stats in self.player_stats.items():
            if stats.valid_submit:
                rv.append(f"- {player}: submission compiled successfully, score={stats.score}")
            else:
                rv.append(f"- {player}: submission failed with error: {stats.invalid_reason}")
        if self.details:
            rv.extend(["Details:"] + [f"- {line}" for line in self.details])
        return "\n".join(rv)

    def to_dict(self) -> dict[str, Any]:
        # Going through some pain to ensure that the scores dict is always complete
        player_names = set(self.player_stats.keys()) | set(self.scores.keys())
        return {
            "round_num": self.round_num,
            "winner": self.winner,
            "details": self.details,
            "scores": {name: self.scores.get(name, 0.0) for name in player_names},
            "player_stats": {name: stats.to_dict() for name, stats in self.player_stats.items()},
        }


class CodeGame(ABC):
    name: str
    description: str
    default_args: dict = {}
    submission: str

    def __init__(self, config: dict, *, tournament_id: str, local_output_dir: Path, keep_containers: bool = False):
        """The CodeGame class is responsible for running games, i.e., taking a list of code
        from different agents/players and running them against each other.
        It also provides the environments for the game and agents to run in.

        The central method is `run_round`, which takes a list of agents and returns the winner of the round.

        At the end of the the tournament, run the `end` method to clean up the game and agents and write the metadata.

        Args:
            config: The overall config for the tournament.
            tournament_id: The id of the tournament.
            local_output_dir: The host/local directory to write logs to.
            keep_containers: Do not remove containers after games/agent finish.
        """
        self.url_gh: str = f"git@github.com:{GH_ORG}/{self.name}.git"
        self.artifacts: list[Path] = []
        """Artifact objects that we might want to clean up after the game."""
        self.config: dict = config
        self._keep_containers: bool = keep_containers
        self._metadata: dict = {
            "name": self.name,
            "config": self.config["game"],
            "game_id": tournament_id,
            "created_timestamp": int(time.time()),
        }
        self.log_env: Path = DIR_LOGS
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
        If running in AWS, pull the image from the AWS Docker registry instead.
        """
        if is_running_in_aws_batch():
            pull_game_container_aws_ecr(game_name=self.name, image_name=self.image_name, logger=self.logger)

        # Check if container exists using subprocess
        self.logger.debug(f"Checking if container {self.image_name} exists")
        result = subprocess.run(
            f"docker images -q {self.image_name}",
            shell=True,
            capture_output=True,
            text=True,
        )
        if result.stdout.strip():
            self.logger.debug(f"Container {self.image_name} exists")
            return

        self.logger.info(
            f"Building Docker image {self.image_name}. This may take 1-5 minutes and only work on Linux for some games."
        )
        result = subprocess.run(
            (
                "export $(cat .env | xargs);"
                f"docker build --no-cache --build-arg GITHUB_TOKEN=$GITHUB_TOKEN -t {self.image_name} -f docker/{self.name}.Dockerfile ."
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

    def copy_logs_from_env(self, round_num: int) -> None:
        """Copy logs from the game's environment to the local machine."""
        (self.log_local / "rounds" / str(round_num)).mkdir(parents=True, exist_ok=True)
        copy_from_container(
            container=self.environment,
            src_path=str(self.log_env) + "/.",
            dest_path=self.log_round(round_num),
        )

        # Remove logs from container to save space
        assert_zero_exit_code(
            self.environment.execute(f"rm -rf {self.log_env}"),
            logger=self.logger,
        )

    def end(self, cleanup: bool = False):
        if cleanup:
            for artifact in self.artifacts:
                if artifact.exists():
                    subprocess.run(f"rm -rf {artifact}", shell=True)
            self.logger.info(f"🧼 Cleaned up {self.name} game")

    def log_round(self, round_num: int) -> Path:
        return self.log_local / "rounds" / str(round_num)

    def get_environment(self, branch_name: str | None = None) -> DockerEnvironment:
        """Get docker container ID with the game code installed."""
        self.build_image()
        if not self._keep_containers:
            run_args = ["--rm"]
        else:
            run_args = []
        environment = DockerEnvironment(
            image=self.image_name,
            cwd=str(DIR_WORK),
            env={
                "GITHUB_TOKEN": os.getenv("GITHUB_TOKEN", ""),
                "PAGER": "cat",
                "MANPAGER": "cat",
                "LESS": "-R",
                "PIP_PROGRESS_BAR": "off",
                "TQDM_DISABLE": "1",
            },
            container_timeout="10h",
            logger=self.logger,
            run_args=run_args,
        )

        # Manually set URL with github token and git pull
        if github_token := os.getenv("GITHUB_TOKEN"):
            result = assert_zero_exit_code(environment.execute("git remote get-url origin"))
            current_url = result["output"].strip()
            if current_url.startswith("https://") and "@" not in current_url:
                new_url = current_url.replace("https://", f"https://{github_token}@")
                assert_zero_exit_code(environment.execute(f"git remote set-url origin {new_url} && git fetch origin"))
            else:
                self.logger.warning("Remote origin URL is not https://, won't be able to set token and pull.")
        else:
            self.logger.warning("GITHUB_TOKEN environment variable is not set, won't be able to pull.")

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

    def get_metadata(self) -> dict:
        """This is what we write to metadata.json.
        You can subclass extend this to add more details for specific games.
        """
        return self._metadata

    def _pre_round_setup(self, agents: list[Player]):
        """Copy agent codebases into game's container"""
        for agent in agents:
            # First make sure that the folder in the game container is removed
            # This is important for 2 reasons:
            # 1. Subtle differences in docker cp behavior regarding to trailing slashes
            #    depending on whether the destination exists
            # 2. If files are removed from the agent container, they should also be removed
            #    from the game container
            self.logger.debug(f"Copying {agent.name}'s codebase")
            assert_zero_exit_code(self.environment.execute(f"rm -rf /{agent.name}"), logger=self.logger)
            copy_between_containers(
                src_container=agent.environment,
                dest_container=self.environment,
                src_path=DIR_WORK,
                dest_path=f"/{agent.name}",
            )

        assert_zero_exit_code(
            self.environment.execute(f"mkdir -p {self.log_env}"),
            logger=self.logger,
        )

    def run_round(self, agents: list[Player], round_num: int, *, copy_logs: bool = True) -> RoundStats:
        """
        Run a single round of the game with the given agents.

        Returns the log output, result output, and winner name. All bookkeeping should be
        handled by the tournament class.
        """
        all_names = {agent.name for agent in agents}
        assert len(all_names) == len(agents), "All agents must have unique names"

        random.shuffle(agents)  # Shuffle to ensure fairness in case of positional advantages
        stats = RoundStats(round_num, agents)
        validated: list[Player] = []
        for a in agents:
            is_valid, error = self.validate_code(a)
            if not is_valid:
                self.logger.warning(f"Agent {a.name} failed submission validation: {error}")
                stats.player_stats[a.name].invalid_reason = error
                continue
            self.logger.info(f"Agent {a.name} passed submission validation")
            stats.player_stats[a.name].valid_submit = True
            validated.append(a)

        sims = self.config["game"]["sims_per_round"]
        if len(validated) > 1:
            self._pre_round_setup(validated)
            self.execute_round(validated)
            if copy_logs:
                self.copy_logs_from_env(round_num)
            self.get_results(validated, round_num, stats)
        elif len(validated) == 1:
            self.logger.info(f"Only one valid agent ({validated[0].name}), automatic win")
            stats.winner = validated[0].name
            stats.scores[validated[0].name] = sims
            stats.player_stats[validated[0].name].score = sims
        else:
            self.logger.info("No valid agents, no winner this round (Default tie)")
            stats.winner = RESULT_TIE
            # Split points evenly
            points = sims * 1.0 / len(agents)
            for a in agents:
                stats.scores[a.name] = points
                stats.player_stats[a.name].score = points
        return stats

    @abstractmethod
    def get_results(self, agents: list[Player], round_num: int, stats: RoundStats):
        """Determine the winner of the game based on the result output.
        Modifies the stats object in place.

        Args:
            agents: List of agents participating in the round
        """
        pass

    @abstractmethod
    def execute_round(self, agents: list[Player]):
        """Subclasses implement their game-specific logic here.
        This is the low level implementation, you probably want to use run_round instead, which
        includes the pre-round setup, post-round setup, and winner determination.
        """
        pass

    @abstractmethod
    def validate_code(self, agent: Player) -> tuple[bool, str | None]:
        """Verify that the given agent can be run by the game.

        Args:
            agent: The agent to verify

        Returns:
            Boolean indicating whether the agent passed verification
            Optional string indicating reason for failure
        """
        pass
