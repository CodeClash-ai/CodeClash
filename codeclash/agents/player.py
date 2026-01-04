import json
import os
import time
import uuid
from abc import ABC, abstractmethod

from dotenv import load_dotenv
from minisweagent.environments.docker import DockerEnvironment

from codeclash.agents.utils import GameContext
from codeclash.constants import GH_ORG
from codeclash.tournaments.utils.git_utils import extract_modified_code_file_paths_from_diff, filter_git_diff
from codeclash.utils.environment import assert_zero_exit_code, create_file_in_container
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
        self._player_unique_id = str(uuid.uuid4())
        """Unique ID that doesn't clash even across multiple games. Used for git tags."""
        self.environment = environment
        self.game_context = game_context
        self.push = config.get("push", False)
        self.logger = get_logger(
            self.name,
            log_path=self.game_context.log_local / "players" / self.name / "player.log",
            emoji="👤",
        )
        self._metadata = {
            "name": self.name,
            "player_unique_id": self._player_unique_id,
            "created_timestamp": int(time.time()),
            "config": self.config,
            "initial_commit_hash": self._get_commit_hash(),
            "branch_name": self._branch_name,
            "round_tags": {},  # mapping round -> tag
            "agent_stats": {},  # mapping round -> agent stats
        }

        if branch := config.get("branch_init"):
            self.logger.info(f"Checking out branch {branch}")
            assert_zero_exit_code(self.environment.execute(f"git checkout {branch}"), logger=self.logger)

        if self.push:
            self.logger.info("Will push agent gameplay as branch to remote repository after each round")
            token = os.getenv("GITHUB_TOKEN")
            if not token:
                raise ValueError("GITHUB_TOKEN environment variable is required")
            for cmd in [
                "git remote remove origin",
                f"git remote add origin https://x-access-token:{token}@github.com/{GH_ORG}/{self.game_context.name}.git",
            ]:
                assert_zero_exit_code(self.environment.execute(cmd), logger=self.logger)

    # --- Main methods ---

    def pre_run_hook(self, *, new_round: int) -> None:
        """Should be called before we call the run method."""
        if new_round == 1:
            self._tag_round(0)
        self.game_context.round = new_round

    def _write_changes_to_file(self, *, round: int) -> None:
        """Write all changes to a JSON file in players/{name}/changes_r{round}.json"""
        if round == 0:
            return  # No changes for round 0

        # Generate all diffs and extract modified files
        raw_diff = self._get_round_diff(round)
        filtered_diff = filter_git_diff(raw_diff)
        incremental_diff = self._get_round_diff(round, incremental=True)
        modified_files = self._extract_modified_files_from_diff(filtered_diff)

        player_dir = self.game_context.log_local / "players" / self.name
        player_dir.mkdir(parents=True, exist_ok=True)

        changes_file = player_dir / f"changes_r{round}.json"
        changes_data = {
            "round": round,
            "full_diff": raw_diff,
            "incremental_diff": incremental_diff,
            "modified_files": modified_files,
            "timestamp": int(time.time()),
        }

        changes_file.write_text(json.dumps(changes_data, indent=2))
        self.logger.debug(f"Wrote changes for round {round} to {changes_file}")

    def post_run_hook(self, *, round: int) -> None:
        """Should be called after we called the run method."""
        self._commit()

        # Write all changes to separate JSON file
        self._write_changes_to_file(round=round)

        if self.push:
            for cmd in [
                f"git push origin {self._branch_name}",
                "git push origin --tags",
            ]:
                assert_zero_exit_code(self.environment.execute(cmd), logger=self.logger)
            self.logger.info(f"Pushed {self.name} commit history to remote repository (branch {self._branch_name})")

    @abstractmethod
    def run(self) -> None:
        """Given the observation / recap, update the codebase"""

    def get_metadata(self) -> dict:
        """Get metadata for the agent."""
        return self._metadata

    def reset_and_apply_patch(self, patch: str, *, base_commit: str = "", filter_patch: bool = True) -> None:
        """Clean all uncommitted changes. If base_commit is provided, reset to that commit.
        Then apply the patch to the codebase.
        """
        # Need to clean before we copy over the patch (else it's gonna be removed by git clean)
        self.logger.debug(
            assert_zero_exit_code(self.environment.execute(f"git reset --hard {base_commit} && git clean -fd"))
        )

        patch = filter_git_diff(patch) if filter_patch else patch

        if not patch.strip():
            self.logger.debug("No patch to apply, skipping")
            return

        create_file_in_container(
            container=self.environment,  # type: ignore
            content=patch,
            dest_path="tmp_patch.txt",
        )

        commands = ["git status", "git apply tmp_patch.txt", "rm -f tmp_patch.txt"]
        cmd = " && ".join(commands)
        self.logger.debug(f"Executing command: {cmd}")
        assert_zero_exit_code(self.environment.execute(cmd), logger=self.logger)

    # --- Helper methods ---

    def _tag_round(self, round: int) -> None:
        """Git tag the codebase at the given round."""
        tag = self._get_round_tag_name(round)
        assert_zero_exit_code(
            self.environment.execute(f"git tag -a {tag} -m 'Round {round} Update'"),
            logger=self.logger,
        )
        self._metadata["round_tags"][round] = tag

    @property
    def _branch_name(self) -> str:
        """Get the branch name for the agent's codebase."""
        return f"{self.game_context.id}.{self.name}"

    def _get_round_tag_name(self, round: int) -> str:
        """Get git tag name for the version of the codebase at the given round."""
        return f"{self._player_unique_id}-round-{round}"

    def _get_commit_hash(self) -> str:
        """Get the current commit hash."""
        out = assert_zero_exit_code(
            self.environment.execute("git rev-parse HEAD"),
            logger=self.logger,
        )
        return out["output"].strip()

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

    def _extract_modified_files_from_diff(self, diff: str) -> dict[str, str]:
        """Extract modified file paths from a git diff and get their full content.
        Returns a dict mapping file path to full file content.
        Only includes common code file extensions.
        """
        file_paths = extract_modified_code_file_paths_from_diff(diff)

        file_contents = {}
        for file_path in file_paths:
            # Check whether the file exists in the container before attempting to cat it.
            # We avoid try/except by inspecting the returncode returned by the execute call.
            ls_result = self.environment.execute(f"ls -la '{file_path}'")
            if ls_result.get("returncode", 0) != 0:
                # File was removed or is not present in this tree. Per request, record empty string.
                self.logger.warning(f"File '{file_path}' not found; recording empty content.")
                file_contents[file_path] = ""
                continue

            out = assert_zero_exit_code(
                self.environment.execute(f"cat '{file_path}'"),
                logger=self.logger,
            )
            file_contents[file_path] = out["output"]

        return file_contents

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
            self.environment.execute(f"git diff {previous_round_tag}..{current_round_tag}"),
            logger=self.logger,
        )
        return out["output"]
