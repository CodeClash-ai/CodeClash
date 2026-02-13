"""
Tests that Singularity copy operations in environment.py match docker cp semantics.

docker cp rules (from Docker docs):
1. SRC is a file:
   - DEST doesn't exist -> create file at DEST
   - DEST exists as file -> overwrite
   - DEST exists as dir -> copy file INTO dir as DEST/basename(SRC)

2. SRC is a directory (no /. suffix):
   - DEST doesn't exist -> create DEST, copy CONTENTS into it
   - DEST exists as dir -> copy SRC dir INTO DEST as DEST/basename(SRC)/...

3. SRC is a directory with /. suffix:
   - DEST doesn't exist -> create DEST, copy CONTENTS into it
   - DEST exists as dir -> merge CONTENTS into DEST (no subdirectory created)
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from minisweagent.environments.singularity import SingularityEnvironment, SingularityEnvironmentConfig

from codeclash.utils.environment import (
    copy_between_containers,
    copy_from_container,
    copy_to_container,
    create_file_in_container,
)


@pytest.fixture
def mock_env(tmp_path):
    """Create a SingularityEnvironment with a fake sandbox_dir (no actual build)."""

    def _make(cwd="/workspace"):
        _make.counter = getattr(_make, "counter", 0) + 1
        sandbox = tmp_path / f"sandbox-{_make.counter}"
        sandbox.mkdir()
        (sandbox / cwd.lstrip("/")).mkdir(parents=True, exist_ok=True)
        env = object.__new__(SingularityEnvironment)
        env.config = SingularityEnvironmentConfig(image="dummy", cwd=cwd)
        env.sandbox_dir = sandbox
        env.logger = MagicMock()
        return env

    return _make


def populate_dir(d: Path, files: dict[str, str]):
    for relpath, content in files.items():
        p = d / relpath
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)


def dir_contents(d: Path) -> dict[str, str]:
    result = {}
    if d.exists() and d.is_dir():
        for p in sorted(d.rglob("*")):
            if p.is_file():
                result[str(p.relative_to(d))] = p.read_text()
    return result


# ============================================================
# copy_to_container
# ============================================================


class TestCopyToContainer:
    def test_file_to_nonexistent_dest(self, mock_env, tmp_path):
        env = mock_env()
        src = tmp_path / "src_file.txt"
        src.write_text("hello")

        copy_to_container(env, src, "/dest/file.txt")
        assert (env.sandbox_dir / "dest/file.txt").read_text() == "hello"

    def test_file_overwrites_existing_file(self, mock_env, tmp_path):
        env = mock_env()
        (env.sandbox_dir / "dest").mkdir(parents=True)
        (env.sandbox_dir / "dest/file.txt").write_text("old")

        src = tmp_path / "src_file.txt"
        src.write_text("new")

        copy_to_container(env, src, "/dest/file.txt")
        assert (env.sandbox_dir / "dest/file.txt").read_text() == "new"

    def test_file_to_existing_directory(self, mock_env, tmp_path):
        """docker cp copies file INTO the directory."""
        env = mock_env()
        (env.sandbox_dir / "dest_dir").mkdir(parents=True)
        (env.sandbox_dir / "dest_dir/existing.txt").write_text("keep")

        src = tmp_path / "myfile.txt"
        src.write_text("new_content")

        copy_to_container(env, src, "/dest_dir")
        assert (env.sandbox_dir / "dest_dir/myfile.txt").read_text() == "new_content"
        assert (env.sandbox_dir / "dest_dir/existing.txt").read_text() == "keep"

    def test_dir_to_nonexistent_dest(self, mock_env, tmp_path):
        env = mock_env()
        src_dir = tmp_path / "src_dir"
        populate_dir(src_dir, {"a.txt": "aaa", "sub/b.txt": "bbb"})

        copy_to_container(env, src_dir, "/newdest")
        assert dir_contents(env.sandbox_dir / "newdest") == {"a.txt": "aaa", "sub/b.txt": "bbb"}

    def test_dir_to_existing_directory(self, mock_env, tmp_path):
        """docker cp copies src dir INTO existing dest as dest/basename(src)/..."""
        env = mock_env()
        (env.sandbox_dir / "existing_dest").mkdir(parents=True)
        (env.sandbox_dir / "existing_dest/old.txt").write_text("old")

        src_dir = tmp_path / "mydir"
        populate_dir(src_dir, {"a.txt": "aaa", "sub/b.txt": "bbb"})

        copy_to_container(env, src_dir, "/existing_dest")
        assert dir_contents(env.sandbox_dir / "existing_dest") == {
            "old.txt": "old",
            "mydir/a.txt": "aaa",
            "mydir/sub/b.txt": "bbb",
        }

    def test_dir_to_dest_with_trailing_slash(self, mock_env, tmp_path):
        env = mock_env()
        src_dir = tmp_path / "mydir"
        populate_dir(src_dir, {"a.txt": "aaa"})

        copy_to_container(env, src_dir, "/newdest/")
        assert dir_contents(env.sandbox_dir / "newdest") == {"a.txt": "aaa"}

    def test_file_with_relative_dest_path(self, mock_env, tmp_path):
        env = mock_env(cwd="/workspace")
        src = tmp_path / "file.txt"
        src.write_text("relative")

        copy_to_container(env, src, "subdir/file.txt")
        assert (env.sandbox_dir / "workspace/subdir/file.txt").read_text() == "relative"


# ============================================================
# copy_from_container
# ============================================================


class TestCopyFromContainer:
    def test_file_to_nonexistent_dest(self, mock_env, tmp_path):
        env = mock_env()
        populate_dir(env.sandbox_dir / "data", {"file.txt": "from_container"})

        dest = tmp_path / "output/file.txt"
        copy_from_container(env, "/data/file.txt", dest)
        assert dest.read_text() == "from_container"

    def test_file_to_existing_directory(self, mock_env, tmp_path):
        """shutil.copy2(file, dir) copies file INTO dir."""
        env = mock_env()
        populate_dir(env.sandbox_dir / "data", {"file.txt": "from_container"})

        dest_dir = tmp_path / "output"
        dest_dir.mkdir()

        copy_from_container(env, "/data/file.txt", dest_dir)
        assert (dest_dir / "file.txt").read_text() == "from_container"

    def test_dir_to_nonexistent_dest(self, mock_env, tmp_path):
        env = mock_env()
        populate_dir(env.sandbox_dir / "data/mydir", {"a.txt": "aaa", "sub/b.txt": "bbb"})

        dest = tmp_path / "output"
        copy_from_container(env, "/data/mydir", dest)
        assert dir_contents(dest) == {"a.txt": "aaa", "sub/b.txt": "bbb"}

    def test_dir_to_existing_directory(self, mock_env, tmp_path):
        """docker cp copies src dir INTO existing dest as dest/basename(src)/..."""
        env = mock_env()
        populate_dir(env.sandbox_dir / "data/mydir", {"a.txt": "aaa", "sub/b.txt": "bbb"})

        dest = tmp_path / "output"
        dest.mkdir()
        (dest / "old.txt").write_text("old")

        copy_from_container(env, "/data/mydir", dest)
        assert dir_contents(dest) == {
            "old.txt": "old",
            "mydir/a.txt": "aaa",
            "mydir/sub/b.txt": "bbb",
        }

    def test_dir_dot_to_nonexistent_dest(self, mock_env, tmp_path):
        """/.  on non-existent dest creates dest with contents."""
        env = mock_env()
        populate_dir(env.sandbox_dir / "data/mydir", {"a.txt": "aaa", "sub/b.txt": "bbb"})

        dest = tmp_path / "output"
        copy_from_container(env, "/data/mydir/.", dest)
        assert dir_contents(dest) == {"a.txt": "aaa", "sub/b.txt": "bbb"}

    def test_dir_dot_to_existing_directory(self, mock_env, tmp_path):
        """/. merges contents into existing dest."""
        env = mock_env()
        populate_dir(env.sandbox_dir / "data/mydir", {"a.txt": "aaa", "sub/b.txt": "bbb"})

        dest = tmp_path / "output"
        dest.mkdir()
        (dest / "old.txt").write_text("old")

        copy_from_container(env, "/data/mydir/.", dest)
        assert dir_contents(dest) == {"old.txt": "old", "a.txt": "aaa", "sub/b.txt": "bbb"}

    def test_removesuffix_with_dotted_dir_name(self, mock_env, tmp_path):
        """Ensure /. suffix stripping doesn't eat dots in directory names."""
        env = mock_env()
        populate_dir(env.sandbox_dir / "data/v1.0.0", {"release.txt": "v1"})

        dest = tmp_path / "output"
        copy_from_container(env, "/data/v1.0.0/.", dest)
        assert dir_contents(dest) == {"release.txt": "v1"}

    def test_removesuffix_with_trailing_dots_in_name(self, mock_env, tmp_path):
        """Directory name ending with dots must not be corrupted by /. stripping."""
        env = mock_env()
        populate_dir(env.sandbox_dir / "data/logs...", {"out.txt": "log data"})

        dest = tmp_path / "output"
        copy_from_container(env, "/data/logs.../.", dest)
        assert dir_contents(dest) == {"out.txt": "log data"}

    def test_trailing_slash_on_src(self, mock_env, tmp_path):
        """Trailing / on src (not /.) should not change behavior."""
        env = mock_env()
        populate_dir(env.sandbox_dir / "data/mydir", {"a.txt": "aaa"})

        dest = tmp_path / "output"
        copy_from_container(env, "/data/mydir/", dest)
        assert dir_contents(dest) == {"a.txt": "aaa"}


# ============================================================
# copy_between_containers
# ============================================================


class TestCopyBetweenContainers:
    def test_dir_to_nonexistent_dest(self, mock_env):
        env1 = mock_env()
        env2 = mock_env()
        populate_dir(
            env1.sandbox_dir / "workspace",
            {"a.txt": "aaa", "sub/b.txt": "bbb", ".git/config": "gitdata", "__pycache__/cache.pyc": "cache"},
        )

        copy_between_containers(env1, env2, "/workspace", "/player1")
        assert dir_contents(env2.sandbox_dir / "player1") == {"a.txt": "aaa", "sub/b.txt": "bbb"}

    def test_dir_to_existing_dest(self, mock_env):
        """docker cp copies src dir INTO existing dest."""
        env1 = mock_env()
        env2 = mock_env()
        populate_dir(env1.sandbox_dir / "workspace", {"a.txt": "aaa"})
        populate_dir(env2.sandbox_dir / "player1", {"old.txt": "old"})

        copy_between_containers(env1, env2, "/workspace", "/player1")
        assert dir_contents(env2.sandbox_dir / "player1") == {
            "old.txt": "old",
            "workspace/a.txt": "aaa",
        }

    def test_trailing_slash_on_nonexistent_dest(self, mock_env):
        env1 = mock_env()
        env2 = mock_env()
        populate_dir(env1.sandbox_dir / "workspace", {"a.txt": "aaa"})

        copy_between_containers(env1, env2, "/workspace", "/opponent_codebases/agent1/")
        assert dir_contents(env2.sandbox_dir / "opponent_codebases/agent1") == {"a.txt": "aaa"}

    def test_excludes_git_and_pycache(self, mock_env):
        env1 = mock_env()
        env2 = mock_env()
        populate_dir(
            env1.sandbox_dir / "workspace",
            {"code.py": "x", ".git/HEAD": "ref", "__pycache__/mod.pyc": "bytecode"},
        )

        copy_between_containers(env1, env2, "/workspace", "/dest")
        assert dir_contents(env2.sandbox_dir / "dest") == {"code.py": "x"}


# ============================================================
# create_file_in_container
# ============================================================


class TestCreateFileInContainer:
    def test_absolute_path(self, mock_env):
        env = mock_env()
        create_file_in_container(env, content="hello world", dest_path="/data/test.txt")
        assert (env.sandbox_dir / "data/test.txt").read_text() == "hello world"

    def test_relative_path(self, mock_env):
        env = mock_env(cwd="/workspace")
        create_file_in_container(env, content="relative content", dest_path="sub/test.txt")
        assert (env.sandbox_dir / "workspace/sub/test.txt").read_text() == "relative content"

    def test_overwrite_existing(self, mock_env):
        env = mock_env()
        (env.sandbox_dir / "data").mkdir()
        (env.sandbox_dir / "data/test.txt").write_text("old")

        create_file_in_container(env, content="new", dest_path="/data/test.txt")
        assert (env.sandbox_dir / "data/test.txt").read_text() == "new"
