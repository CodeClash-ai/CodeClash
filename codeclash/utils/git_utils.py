import subprocess


def get_current_git_branch() -> str:
    result = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True, check=True)
    return result.stdout.strip()


def is_git_repo_dirty() -> bool:
    result = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, check=True)
    return bool(result.stdout.strip())


def has_unpushed_commits() -> bool:
    try:
        result = subprocess.run(
            ["git", "rev-list", "--count", "@{u}..HEAD"], capture_output=True, text=True, check=True
        )
        return int(result.stdout.strip()) > 0
    except subprocess.CalledProcessError:
        return False
