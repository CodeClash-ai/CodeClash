"""
Shared fixtures and mocks for arena unit tests.

These fixtures allow testing arena logic (validation, result parsing)
without requiring Docker containers or actual game execution.
"""

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest


class MockEnvironment:
    """Mock environment that simulates container file system and command execution."""

    def __init__(self, files: dict[str, str] | None = None, command_outputs: dict[str, dict] | None = None):
        """
        Args:
            files: Dict mapping file paths to their contents
            command_outputs: Dict mapping command prefixes to their outputs
                             Format: {"ls": {"output": "file1.py\nfile2.py", "returncode": 0}}
        """
        self.files = files or {}
        self.command_outputs = command_outputs or {}
        self.config = MagicMock()
        self.config.cwd = "/workspace"
        self._executed_commands: list[str] = []

    def execute(self, cmd: str, cwd: str | None = None, timeout: int | None = None) -> dict[str, Any]:
        """Simulate command execution based on configured outputs."""
        self._executed_commands.append(cmd)

        # Check for exact matches first
        if cmd in self.command_outputs:
            return self.command_outputs[cmd]

        # Check for prefix matches
        for prefix, output in self.command_outputs.items():
            if cmd.startswith(prefix):
                return output

        # Default behavior for common commands
        if cmd.startswith("ls"):
            # Extract path from command
            parts = cmd.split()
            path = parts[1] if len(parts) > 1 else "."
            matching_files = [Path(f).name for f in self.files.keys() if f.startswith(path) or path == "."]
            return {"output": "\n".join(matching_files), "returncode": 0}

        if cmd.startswith("cat "):
            file_path = cmd.split("cat ", 1)[1].strip()
            if file_path in self.files:
                return {"output": self.files[file_path], "returncode": 0}
            return {"output": f"cat: {file_path}: No such file or directory", "returncode": 1}

        if cmd.startswith("test -f ") and "echo" in cmd:
            file_path = cmd.split("test -f ")[1].split(" &&")[0].strip()
            exists = file_path in self.files
            return {"output": "exists" if exists else "", "returncode": 0 if exists else 1}

        if cmd.startswith("test -d ") and "echo" in cmd:
            dir_path = cmd.split("test -d ")[1].split(" &&")[0].strip()
            # Check if any file path starts with this directory
            exists = any(f.startswith(dir_path + "/") or f == dir_path for f in self.files.keys())
            return {"output": "exists" if exists else "", "returncode": 0 if exists else 1}

        # Default: command succeeded with no output
        return {"output": "", "returncode": 0}


class MockPlayer:
    """Mock player for testing arena validation and result parsing."""

    def __init__(self, name: str, environment: MockEnvironment | None = None):
        self.name = name
        self.environment = environment or MockEnvironment()


def create_mock_player(name: str, files: dict[str, str] | None = None, **kwargs) -> MockPlayer:
    """Create a mock player with specified file system contents."""
    env = MockEnvironment(files=files, **kwargs)
    return MockPlayer(name=name, environment=env)


@pytest.fixture
def mock_player_factory():
    """Factory fixture for creating mock players."""
    return create_mock_player


@pytest.fixture
def minimal_config():
    """Minimal config dict for arena initialization."""
    return {
        "game": {
            "name": "Test",
            "sims_per_round": 10,
        },
        "tournament": {
            "rounds": 3,
        },
        "players": [
            {"name": "p1", "agent": "dummy"},
            {"name": "p2", "agent": "dummy"},
        ],
    }


@pytest.fixture
def tmp_log_dir(tmp_path):
    """Create a temporary log directory structure."""
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    rounds_dir = log_dir / "rounds"
    rounds_dir.mkdir()
    return log_dir
