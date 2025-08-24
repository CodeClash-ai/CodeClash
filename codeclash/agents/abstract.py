import os
import uuid
from abc import ABC, abstractmethod

from dotenv import load_dotenv
from minisweagent.environments.docker import DockerEnvironment

from codeclash.agents.utils import GameContext
from codeclash.constants import GH_ORG
from codeclash.tournaments.utils.git_utils import filter_git_diff
from codeclash.utils.environment import assert_zero_exit_code, create_file_on_container
from codeclash.utils.log import get_logger

load_dotenv()


class Player(ABC):
    def __init__(
        self,
        config: dict,
        environment: DockerEnvironment,
        game_context: GameContext,
    ) -> None:
        self.config = config
        self.name = config["name"]
        self._player_unique_id = uuid.uuid4()
        """Unique ID that doesn't clash even accross multiple games. Used for git tags."""
        self.environment = environment
        self.game_context = game_context
        self.game_context.render_and_set_prompts()
        self.logger = get_logger(
            self.name,
            log_path=self.game_context.log_local / f"{self.name}.log",
            emoji="👤",
        )
        self._metadata = {
            "name": self.name,
            "player_unique_id": self._player_unique_id,
            "diff": {},  # mapping round -> diff
            "incremental_diff": {},  # mapping round -> diff
        }

    # --- Main methods ---

    def pre_run_hook(self, *, new_round: int) -> None:
        """Should be called before we call the run method."""
        if new_round == 1:
            self._tag_round(0)
        self.game_context.round = new_round
        self.game_context.render_and_set_prompts()

    def post_run_hook(self, *, round: int) -> None:
        """Should be called after we called the run method."""
        self._commit()
        self._metadata["diff"][round] = self._get_round_diff(round)
        self._metadata["incremental_diff"][round] = self._get_round_diff(
            round, incremental=True
        )

    @abstractmethod
    def run(self) -> None:
        """Given the observation / recap, update the codebase"""

    def get_metadata(self) -> dict:
        """Get metadata for the agent."""
        return self._metadata

    def push(self) -> None:
        """Push codebase to a branch on the game's remote repository."""
        token = os.getenv("GITHUB_TOKEN")
        if not token:
            raise ValueError("GITHUB_TOKEN environment variable is required")

        for cmd in [
            "git remote remove origin",
            f"git remote add origin https://x-access-token:{token}@github.com/{GH_ORG}/{self.game_context.name}.git",
            f"git push origin {self._branch_name}",
            "git push origin --tags",
        ]:
            assert_zero_exit_code(self.environment.execute(cmd), logger=self.logger)
        self.logger.info(
            f"Pushed {self.name} commit history to remote repository (branch {self._branch_name})"
        )

    def reset_and_apply_patch(
        self, patch: str, *, base_commit: str = "", filter_patch: bool = True
    ) -> None:
        """Clean all uncommited changes. If base_commit is provided, reset to that commit.
        Then apply the patch to the codebase.
        """
        # Need to clean before we copy over the patch (else it's gonna be removed by git clean)
        self.logger.debug(
            assert_zero_exit_code(
                self.environment.execute(
                    f"git reset --hard {base_commit} && git clean -fd"
                )
            )
        )

        patch = filter_git_diff(patch) if filter_patch else patch

        if not patch.strip():
            self.logger.debug("No patch to apply, skipping")
            return

        create_file_on_container(
            container=self.environment,  # type: ignore
            content=patch,
            dest_path="tmp_patch.txt",
        )

        self.logger.debug(f"Applying patch to agent's codebase: {patch}")

        commands = ["git status", "git apply tmp_patch.txt", "rm -f tmp_patch.txt"]
        for cmd in commands:
            self.logger.debug(f"Executing command: {cmd}")
            out = assert_zero_exit_code(
                self.environment.execute(cmd), logger=self.logger
            )
            self.logger.debug(out)

    # --- Helper methods ---

    def _tag_round(self, round: int) -> None:
        """Git tag the codebase at the given round."""
        assert_zero_exit_code(
            self.environment.execute(
                f"git tag -a {self._get_round_tag_name(round)} -m 'Round {round} Update'"
            ),
            logger=self.logger,
        )

    @property
    def _branch_name(self) -> str:
        """Get the branch name for the agent's codebase."""
        return f"{self.game_context.id}.{self.name}"

    def _get_round_tag_name(self, round: int) -> str:
        """Get git tag name for the version of the codebase at the given round."""
        return f"{self._player_unique_id}-round-{round}"

    def _commit(self) -> None:
        """Commit changes to the agent's codebase."""
        r = self.game_context.round
        for cmd in [
            "git add -A",
            f"git commit --allow-empty -m 'Round {r} Update'",
        ]:
            assert_zero_exit_code(self.environment.execute(cmd), logger=self.logger)
        self._tag_round(r)
        self.logger.info(f"Committed changes for {self.name} for round {r}")

    def _get_round_diff(self, round: int, *, incremental: bool = False) -> str:
        """Get the diff between the round and initial version (round 0).
        If incremental is True, get the diff between the round and the previous round.
        Returns empty string if round is 0.
        """
        if round == 0:
            return ""
        if incremental:
            previous_round_tag = self._get_round_tag_name(round - 1)
        else:
            previous_round_tag = self._get_round_tag_name(0)
        current_round_tag = self._get_round_tag_name(round)
        out = assert_zero_exit_code(
            self.environment.execute(
                f"git diff {previous_round_tag}..{current_round_tag}"
            ),
            logger=self.logger,
        )
        return out["output"]
