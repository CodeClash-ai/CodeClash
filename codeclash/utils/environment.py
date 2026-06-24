import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from minisweagent.environments.docker import DockerEnvironment

# Patterns to exclude when copying between containers
COPY_EXCLUDE_PATTERNS = [".git", "__pycache__"]


def _scratch_dir() -> str | None:
    """Local scratch dir for staging `docker cp` transfers. Defaults to the system temp dir.
    Override with CODECLASH_TMPDIR (e.g. on AWS Batch, where the default temp dir misbehaves)."""
    override = os.getenv("CODECLASH_TMPDIR")
    if override:
        Path(override).mkdir(parents=True, exist_ok=True)
    return override


class ClashDockerEnvironment(DockerEnvironment):
    """DockerEnvironment that also accepts a plain command string.

    mini-swe-agent v2's `execute` takes an action dict (`{"command": ...}`), but CodeClash's
    arena code calls `execute("some shell command")` directly. Normalize so both work.
    """

    def execute(self, action: str | dict, cwd: str = "", *, timeout: int | None = None) -> dict:
        if isinstance(action, str):
            action = {"command": action}
        return super().execute(action, cwd, timeout=timeout)


def assert_zero_exit_code(result: dict, *, logger: logging.Logger | None = None) -> dict:
    if result.get("returncode", 0) != 0:
        msg = f"Command failed with exit code {result.get('returncode')}:\n{result.get('output')}"
        if logger is not None:
            logger.error(msg)
        raise RuntimeError(msg)
    return result


def copy_between_containers(
    src_container: DockerEnvironment,
    dest_container: DockerEnvironment,
    src_path: str | Path,
    dest_path: str | Path,
):
    """
    Copy files from one Docker container to another via a temporary local directory.

    Be extremely careful with trailing slashes in src_path and dest_path, the behavior
    of docker cp is also different depending on whether the destination exists.
    """
    print(
        f"Copy between containers: {src_container.container_id}:{src_path} -> {dest_container.container_id}:{dest_path}"
    )
    with tempfile.TemporaryDirectory(dir=_scratch_dir()) as temp_dir:
        temp_path = Path(temp_dir) / Path(src_path).name

        # Copy from source container to temporary local directory
        cmd_src = [
            "docker",
            "cp",
            f"{src_container.container_id}:{src_path}",
            str(temp_path),
        ]
        result_src = subprocess.run(cmd_src, check=False, capture_output=True, text=True)
        if result_src.returncode != 0:
            raise RuntimeError(
                f"Failed to copy from {src_container.container_id} to local temp: {result_src.stdout}{result_src.stderr}"
            )

        # Remove excluded patterns
        for pattern in COPY_EXCLUDE_PATTERNS:
            excluded_path = temp_path / pattern
            if excluded_path.exists():
                if excluded_path.is_dir():
                    shutil.rmtree(excluded_path)
                else:
                    excluded_path.unlink()

        # Ensure destination folder exists
        assert_zero_exit_code(dest_container.execute(f"mkdir -p {Path(dest_path).parent}"))

        # Copy from temporary local directory to destination container
        cmd_dest = [
            "docker",
            "cp",
            str(temp_path),
            f"{dest_container.container_id}:{dest_path}",
        ]
        result_dest = subprocess.run(cmd_dest, check=False, capture_output=True, text=True)
        if result_dest.returncode != 0:
            raise RuntimeError(
                f"Failed to copy from local temp to {dest_container.container_id}: {result_dest.stdout}{result_dest.stderr}"
            )


def copy_to_container(
    container: DockerEnvironment,
    src_path: str | Path,
    dest_path: str | Path,
):
    """
    Copy a file or directory from the local filesystem to a Docker container.

    The copy operation is recursive for directories.

    Be extremely careful with trailing slashes in src_path and dest_path, the behavior
    of docker cp is also different depending on whether the destination exists.
    """
    if not str(dest_path).startswith("/"):
        # If not an absolute path, assume relative to container's cwd
        dest_path = f"{container.config.cwd}/{dest_path}"
    cmd = [
        "docker",
        "cp",
        str(src_path),
        f"{container.container_id}:{dest_path}",
    ]
    print(f"Copy to container: cmd={cmd}")
    # Ensure destination folder exists
    assert_zero_exit_code(container.execute(f"mkdir -p {Path(dest_path).parent}"))
    result = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"Failed to copy {src_path} to {container.container_id}:{dest_path}: {result.stdout}{result.stderr}"
        )
    return result


def copy_from_container(
    container: DockerEnvironment,
    src_path: str | Path,
    dest_path: str | Path,
):
    """
    Copy a file or directory from a Docker container to the local filesystem.

    The copy operation is recursive for directories.

    Be extremely careful with trailing slashes in src_path and dest_path, the behavior
    of docker cp is also different depending on whether the destination exists.
    """
    cmd = [
        "docker",
        "cp",
        f"{container.container_id}:{src_path}",
        str(dest_path),
    ]
    print(f"Copy from container: cmd={cmd}")
    Path(dest_path).parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"Failed to copy {container.container_id}:{src_path} to {dest_path}: {result.stdout}{result.stderr}"
        )
    return result


def create_file_in_container(
    container: DockerEnvironment,
    *,
    content: str,
    dest_path: str | Path,
):
    """
    Create a file with given content on a Docker container.
    Uses a temporary file on the local filesystem for the transfer.
    """
    with tempfile.NamedTemporaryFile(mode="w", delete=True, suffix=".tmp", dir=_scratch_dir()) as tmp_file:
        tmp_file.write(content)
        tmp_file.flush()  # Ensure content is written to disk
        tmp_file_path = Path(tmp_file.name)
        copy_to_container(container, tmp_file_path, dest_path)
