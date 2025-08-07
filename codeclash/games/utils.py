import subprocess
import tempfile
from pathlib import Path

from minisweagent.environments.docker import DockerEnvironment


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
        result_src = subprocess.run(cmd_src, check=True)
        if result_src.returncode != 0:
            raise RuntimeError(
                f"Failed to copy from {src_container.container_id} to local temp"
            )

        # Ensure destination folder exists
        dest_container.execute(f"mkdir -p {Path(dest_path).parent}")

        # Copy from temporary local directory to destination container
        cmd_dest = [
            "docker",
            "cp",
            str(temp_path),
            f"{dest_container.container_id}:{dest_path}",
        ]
        result_dest = subprocess.run(cmd_dest, check=True)
        if result_dest.returncode != 0:
            raise RuntimeError(
                f"Failed to copy from local temp to {dest_container.container_id}"
            )
