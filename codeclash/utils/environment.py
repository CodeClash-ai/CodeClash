import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

from minisweagent.environments.docker import DockerEnvironment
from minisweagent.environments.singularity import SingularityEnvironment

ContainerEnvironment = DockerEnvironment | SingularityEnvironment

# Patterns to exclude when copying between containers
COPY_EXCLUDE_PATTERNS = [".git", "__pycache__"]


def assert_zero_exit_code(result: dict, *, logger: logging.Logger | None = None) -> dict:
    if result.get("returncode", 0) != 0:
        msg = f"Command failed with exit code {result.get('returncode')}:\n{result.get('output')}"
        if logger is not None:
            logger.error(msg)
        raise RuntimeError(msg)
    return result


def copy_between_containers(
    src_container: ContainerEnvironment,
    dest_container: ContainerEnvironment,
    src_path: str | Path,
    dest_path: str | Path,
):
    """
    Copy files from one container to another.

    For Docker: copies via a temporary local directory using docker cp.
    For Singularity: copies directly between sandbox directories.

    Be extremely careful with trailing slashes in src_path and dest_path, the behavior
    of docker cp is also different depending on whether the destination exists.
    """
    if isinstance(src_container, SingularityEnvironment) and isinstance(dest_container, SingularityEnvironment):
        src_full = src_container.sandbox_dir / str(src_path).lstrip("/")
        dest_full = dest_container.sandbox_dir / str(dest_path).lstrip("/")
        print(f"Copy between containers (singularity): {src_full} -> {dest_full}")

        dest_full.parent.mkdir(parents=True, exist_ok=True)
        if dest_full.exists() and dest_full.is_dir():
            # docker cp copies src dir INTO existing dest as dest/basename(src)/...
            actual_dest = dest_full / src_full.name
            if actual_dest.exists():
                shutil.rmtree(actual_dest)
            shutil.copytree(
                src_full,
                actual_dest,
                ignore=shutil.ignore_patterns(*COPY_EXCLUDE_PATTERNS),
            )
        else:
            shutil.copytree(
                src_full,
                dest_full,
                ignore=shutil.ignore_patterns(*COPY_EXCLUDE_PATTERNS),
            )
        return

    print(
        f"Copy between containers: {src_container.container_id}:{src_path} -> {dest_container.container_id}:{dest_path}"
    )
    # Some weird stuff happening on AWS where /tmp doesn't work properly
    dir = Path.home() / "tmp"
    dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=dir) as temp_dir:
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
    container: ContainerEnvironment,
    src_path: str | Path,
    dest_path: str | Path,
):
    """
    Copy a file or directory from the local filesystem to a container.

    For Docker: uses docker cp.
    For Singularity: copies directly to the sandbox directory.

    The copy operation is recursive for directories.

    Be extremely careful with trailing slashes in src_path and dest_path, the behavior
    of docker cp is also different depending on whether the destination exists.
    """
    if isinstance(container, SingularityEnvironment):
        if not str(dest_path).startswith("/"):
            dest_path = f"{container.config.cwd}/{dest_path}"
        dest_full = container.sandbox_dir / str(dest_path).lstrip("/")
        print(f"Copy to container (singularity): {src_path} -> {dest_full}")
        dest_full.parent.mkdir(parents=True, exist_ok=True)
        src_path = Path(src_path)
        if src_path.is_dir():
            if dest_full.exists() and dest_full.is_dir():
                # docker cp copies src dir INTO existing dest as dest/basename(src)/...
                actual_dest = dest_full / src_path.name
                if actual_dest.exists():
                    shutil.rmtree(actual_dest)
                shutil.copytree(src_path, actual_dest)
            else:
                shutil.copytree(src_path, dest_full)
        else:
            shutil.copy2(src_path, dest_full)
        return

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
    container: ContainerEnvironment,
    src_path: str | Path,
    dest_path: str | Path,
):
    """
    Copy a file or directory from a container to the local filesystem.

    For Docker: uses docker cp.
    For Singularity: copies directly from the sandbox directory.

    The copy operation is recursive for directories.

    Be extremely careful with trailing slashes in src_path and dest_path, the behavior
    of docker cp is also different depending on whether the destination exists.
    """
    if isinstance(container, SingularityEnvironment):
        # Handle trailing "/." which means "contents of directory"
        src_str = str(src_path)
        copy_contents = src_str.endswith("/.")
        if copy_contents:
            src_str = src_str.removesuffix("/.")
        src_full = container.sandbox_dir / src_str.lstrip("/")
        print(f"Copy from container (singularity): {src_full} -> {dest_path}")
        Path(dest_path).parent.mkdir(parents=True, exist_ok=True)
        if src_full.is_dir():
            if copy_contents:
                # Copy contents of directory into dest_path
                dest_path = Path(dest_path)
                dest_path.mkdir(parents=True, exist_ok=True)
                for item in src_full.iterdir():
                    s = src_full / item.name
                    d = dest_path / item.name
                    if s.is_dir():
                        if d.exists():
                            shutil.rmtree(d)
                        shutil.copytree(s, d)
                    else:
                        shutil.copy2(s, d)
            else:
                dest_path = Path(dest_path)
                if dest_path.exists() and dest_path.is_dir():
                    # docker cp copies src dir INTO existing dest as dest/basename(src)/...
                    actual_dest = dest_path / src_full.name
                    if actual_dest.exists():
                        shutil.rmtree(actual_dest)
                    shutil.copytree(src_full, actual_dest)
                else:
                    shutil.copytree(src_full, dest_path)
        else:
            shutil.copy2(src_full, dest_path)
        return

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
    container: ContainerEnvironment,
    *,
    content: str,
    dest_path: str | Path,
):
    """
    Create a file with given content in a container.

    For Docker: uses a temporary file on the local filesystem for the transfer.
    For Singularity: writes directly to the sandbox directory.
    """
    if isinstance(container, SingularityEnvironment):
        if not str(dest_path).startswith("/"):
            dest_path = f"{container.config.cwd}/{dest_path}"
        dest_full = container.sandbox_dir / str(dest_path).lstrip("/")
        print(f"Create file in container (singularity): {dest_full}")
        dest_full.parent.mkdir(parents=True, exist_ok=True)
        dest_full.write_text(content)
        return

    # Some weird stuff happening on AWS where /tmp doesn't work properly
    dir = Path.home() / "tmp"
    dir.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", delete=True, suffix=".tmp", dir=dir) as tmp_file:
        tmp_file.write(content)
        tmp_file.flush()  # Ensure content is written to disk
        tmp_file_path = Path(tmp_file.name)
        copy_to_container(container, tmp_file_path, dest_path)
