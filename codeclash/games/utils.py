import os
import subprocess
from pathlib import Path


def clone(url: str, dest: str | Path | None = None) -> Path:
    """
    Clone a git repository if it does not already exist.

    Returns True if the repository was cloned, False if it already existed.
    """
    dest = dest if dest else url.split("/")[-1].replace(".git", "")
    command = ["git", "clone", url, dest]
    if not os.path.exists(dest):
        subprocess.run(
            command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
    return Path(dest).resolve()
