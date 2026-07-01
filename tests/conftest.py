import os
import shutil


def pytest_configure(config):
    """Auto-detect container runtime if CODECLASH_RUNTIME is not already set."""
    if "CODECLASH_RUNTIME" not in os.environ:
        if shutil.which("docker"):
            os.environ["CODECLASH_RUNTIME"] = "docker"
        elif shutil.which("singularity"):
            os.environ["CODECLASH_RUNTIME"] = "singularity"
