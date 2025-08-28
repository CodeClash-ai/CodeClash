import logging
import subprocess
import tempfile
from pathlib import Path

from minisweagent.environments.docker import DockerEnvironment


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
    """
    with tempfile.TemporaryDirectory() as temp_dir:
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
    # Ensure destination folder exists
    assert_zero_exit_code(container.execute(f"mkdir -p {Path(dest_path).parent}"))
    result = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"Failed to copy {src_path} to {container.container_id}:{dest_path}: {result.stdout}{result.stderr}"
        )
    return result


def copy_file_from_container(
    container: DockerEnvironment,
    src_path: str | Path,
    dest_path: str | Path,
):
    """
    Copy a file from a Docker container to the local filesystem.
    """
    cmd = [
        "docker",
        "cp",
        f"{container.container_id}:{src_path}",
        str(dest_path),
    ]
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
    with tempfile.NamedTemporaryFile(mode="w", delete=False) as tmp_file:
        tmp_file.write(content)
        tmp_file_path = Path(tmp_file.name)

    try:
        copy_to_container(container, tmp_file_path, dest_path)
    finally:
        tmp_file_path.unlink()  # Clean up the temporary file
