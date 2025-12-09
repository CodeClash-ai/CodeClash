"""
Unit tests for HaliteArena.

Tests validate_code() and get_results() methods without requiring Docker.
"""

import pytest

from codeclash.arenas.arena import RoundStats
from codeclash.arenas.halite.halite import (
    HALITE_HIDDEN_EXEC,
    HALITE_LOG,
    MAP_FILE_TYPE_TO_COMPILE,
    MAP_FILE_TYPE_TO_RUN,
    HaliteArena,
)
from codeclash.constants import RESULT_TIE

from .conftest import MockPlayer

VALID_C_BOT = """
#include <stdio.h>
int main() {
    printf("MyBot ready\\n");
    return 0;
}
"""

VALID_PY_BOT = """
import sys
print("MyBot ready")
"""


class TestHaliteValidation:
    """Tests for HaliteArena.validate_code()"""

    @pytest.fixture
    def arena(self, tmp_log_dir, minimal_config):
        """Create HaliteArena instance with mocked environment."""
        arena = HaliteArena.__new__(HaliteArena)
        arena.submission = "submission"
        arena.log_local = tmp_log_dir
        arena.run_cmd_round = "./environment/halite"
        arena.logger = type("Logger", (), {"debug": lambda self, msg: None, "info": lambda self, msg: None})()
        return arena

    def test_valid_py_submission(self, arena, mock_player_factory):
        """Test that a valid Python submission passes validation."""
        player = mock_player_factory(
            name="test_player",
            files={
                "submission/main.py": VALID_PY_BOT,
            },
            command_outputs={
                "test -d submission && echo 'exists'": {"output": "exists", "returncode": 0},
                "ls": {"output": "main.py\n", "returncode": 0},
                "./environment/halite": {"output": "Player #1 won", "returncode": 0},
                f'echo "python submission/main.py" > {HALITE_HIDDEN_EXEC}': {"output": "", "returncode": 0},
            },
        )
        player.environment.config.cwd = "/workspace"
        is_valid, error = arena.validate_code(player)
        assert is_valid is True
        assert error is None

    def test_missing_submission_folder(self, arena, mock_player_factory):
        """Test that missing submission folder fails validation."""
        player = mock_player_factory(
            name="test_player",
            files={},
            command_outputs={
                "test -d submission && echo 'exists'": {"output": "", "returncode": 1},
            },
        )
        is_valid, error = arena.validate_code(player)
        assert is_valid is False
        assert "submission" in error.lower()

    def test_missing_main_file(self, arena, mock_player_factory):
        """Test that missing main file fails validation."""
        player = mock_player_factory(
            name="test_player",
            files={"submission/other.py": "pass"},
            command_outputs={
                "test -d submission && echo 'exists'": {"output": "exists", "returncode": 0},
                "ls": {"output": "other.py\n", "returncode": 0},
            },
        )
        player.environment.config.cwd = "/workspace"
        is_valid, error = arena.validate_code(player)
        assert is_valid is False
        assert "main" in error.lower()

    def test_multiple_main_files(self, arena, mock_player_factory):
        """Test that multiple main files fail validation."""
        player = mock_player_factory(
            name="test_player",
            files={
                "submission/main.py": VALID_PY_BOT,
                "submission/main.cpp": VALID_C_BOT,
            },
            command_outputs={
                "test -d submission && echo 'exists'": {"output": "exists", "returncode": 0},
                "ls": {"output": "main.py\nmain.cpp\n", "returncode": 0},
            },
        )
        player.environment.config.cwd = "/workspace"
        is_valid, error = arena.validate_code(player)
        assert is_valid is False
        assert "one" in error.lower() or "exactly" in error.lower()

    def test_compilation_failure(self, arena, mock_player_factory):
        """Test that compilation failure fails validation."""
        player = mock_player_factory(
            name="test_player",
            files={"submission/main.cpp": "invalid c++ code"},
            command_outputs={
                "test -d submission && echo 'exists'": {"output": "exists", "returncode": 0},
                "ls": {"output": "main.cpp\n", "returncode": 0},
                "g++ -std=c++11 main.cpp -o main.o": {
                    "output": "error: invalid syntax",
                    "returncode": 1,
                },
            },
        )
        player.environment.config.cwd = "/workspace"
        is_valid, error = arena.validate_code(player)
        assert is_valid is False
        assert "compilation" in error.lower() or "failed" in error.lower()


class TestHaliteResults:
    """Tests for HaliteArena.get_results()"""

    @pytest.fixture
    def arena(self, tmp_log_dir, minimal_config):
        """Create HaliteArena instance."""
        config = minimal_config.copy()
        config["game"]["name"] = "Halite"
        config["game"]["sims_per_round"] = 3
        arena = HaliteArena.__new__(HaliteArena)
        arena.submission = "submission"
        arena.log_local = tmp_log_dir
        arena.config = config
        arena.logger = type("Logger", (), {"debug": lambda self, msg: None, "info": lambda self, msg: None})()
        return arena

    def _create_sim_log(self, round_dir, idx: int, results: list[tuple[int, str, int]]):
        """
        Create a simulation log file.

        Args:
            results: List of (player_num, name, rank) tuples
        """
        log_file = round_dir / HALITE_LOG.format(idx=idx)
        lines = ["Starting simulation...\n"]
        for player_num, name, rank in results:
            lines.append(f"Player #{player_num}, {name}, came in rank #{rank}\n")
        log_file.write_text("".join(lines))

    def test_parse_results_player1_wins(self, arena, tmp_log_dir):
        """Test parsing results when player 1 wins most games."""
        round_dir = tmp_log_dir / "rounds" / "1"
        round_dir.mkdir(parents=True)

        # Alice wins 2 games, Bob wins 1
        self._create_sim_log(round_dir, 0, [(1, "Alice", 1), (2, "Bob", 2)])
        self._create_sim_log(round_dir, 1, [(1, "Alice", 1), (2, "Bob", 2)])
        self._create_sim_log(round_dir, 2, [(1, "Alice", 2), (2, "Bob", 1)])

        agents = [MockPlayer("Alice"), MockPlayer("Bob")]
        stats = RoundStats(round_num=1, agents=agents)

        arena.get_results(agents, round_num=1, stats=stats)

        assert stats.winner == "Alice"
        assert stats.scores["Alice"] == 2
        assert stats.scores["Bob"] == 1

    def test_parse_results_player2_wins(self, arena, tmp_log_dir):
        """Test parsing results when player 2 wins most games."""
        round_dir = tmp_log_dir / "rounds" / "1"
        round_dir.mkdir(parents=True)

        # Alice wins 1 game, Bob wins 2
        self._create_sim_log(round_dir, 0, [(1, "Alice", 2), (2, "Bob", 1)])
        self._create_sim_log(round_dir, 1, [(1, "Alice", 2), (2, "Bob", 1)])
        self._create_sim_log(round_dir, 2, [(1, "Alice", 1), (2, "Bob", 2)])

        agents = [MockPlayer("Alice"), MockPlayer("Bob")]
        stats = RoundStats(round_num=1, agents=agents)

        arena.get_results(agents, round_num=1, stats=stats)

        assert stats.winner == "Bob"
        assert stats.scores["Alice"] == 1
        assert stats.scores["Bob"] == 2

    def test_parse_results_tie(self, arena, tmp_log_dir):
        """Test parsing results when players have equal wins."""
        arena.config["game"]["sims_per_round"] = 4
        round_dir = tmp_log_dir / "rounds" / "1"
        round_dir.mkdir(parents=True)

        # Each player wins 2 games
        self._create_sim_log(round_dir, 0, [(1, "Alice", 1), (2, "Bob", 2)])
        self._create_sim_log(round_dir, 1, [(1, "Alice", 1), (2, "Bob", 2)])
        self._create_sim_log(round_dir, 2, [(1, "Alice", 2), (2, "Bob", 1)])
        self._create_sim_log(round_dir, 3, [(1, "Alice", 2), (2, "Bob", 1)])

        agents = [MockPlayer("Alice"), MockPlayer("Bob")]
        stats = RoundStats(round_num=1, agents=agents)

        arena.get_results(agents, round_num=1, stats=stats)

        assert stats.winner == RESULT_TIE
        assert stats.scores["Alice"] == 2
        assert stats.scores["Bob"] == 2


class TestHaliteConfig:
    """Tests for HaliteArena configuration and properties."""

    def test_arena_name(self):
        """Test that arena has correct name."""
        assert HaliteArena.name == "Halite"

    def test_submission_folder(self):
        """Test that submission folder is correct."""
        assert HaliteArena.submission == "submission"

    def test_supported_file_types(self):
        """Test that expected file types are supported."""
        supported = set(MAP_FILE_TYPE_TO_RUN.keys())
        assert ".py" in supported
        assert ".cpp" in supported
        assert ".c" in supported

    def test_compilable_languages(self):
        """Test that compilable languages have compile commands."""
        assert ".cpp" in MAP_FILE_TYPE_TO_COMPILE
        assert ".c" in MAP_FILE_TYPE_TO_COMPILE
        # Python shouldn't need compilation
        assert ".py" not in MAP_FILE_TYPE_TO_COMPILE
