"""
Unit tests for DummyArena.

Tests validate_code() and get_results() methods without requiring Docker.
"""

import pytest

from codeclash.arenas.arena import RoundStats
from codeclash.arenas.dummy.dummy import DummyArena

from .conftest import MockPlayer


class TestDummyValidation:
    """Tests for DummyArena.validate_code()"""

    @pytest.fixture
    def arena(self, tmp_log_dir, minimal_config):
        """Create DummyArena instance with mocked environment."""
        config = minimal_config.copy()
        config["game"]["name"] = "Dummy"
        arena = DummyArena.__new__(DummyArena)
        arena.submission = "main.py"
        arena.log_local = tmp_log_dir
        return arena

    def test_valid_submission(self, arena, mock_player_factory):
        """Test that a valid Python submission passes validation."""
        player = mock_player_factory(
            name="test_player",
            files={"main.py": "print('hello world')"},
            command_outputs={
                "python -m py_compile main.py": {"output": "", "returncode": 0},
            },
        )
        is_valid, error = arena.validate_code(player)
        assert is_valid is True
        assert error is None

    def test_missing_submission_file(self, arena, mock_player_factory):
        """Test validation with missing main.py - DummyArena accepts all submissions."""
        player = mock_player_factory(
            name="test_player",
            files={},  # No files
        )
        is_valid, error = arena.validate_code(player)
        # DummyArena is for testing infrastructure, so it accepts all submissions
        assert is_valid is True
        assert error is None

    def test_empty_submission_file(self, arena, mock_player_factory):
        """Test validation with empty main.py - DummyArena accepts all submissions."""
        player = mock_player_factory(
            name="test_player",
            files={"main.py": ""},  # Empty file
        )
        is_valid, error = arena.validate_code(player)
        # DummyArena is for testing infrastructure, so it accepts all submissions
        assert is_valid is True
        assert error is None

    def test_syntax_error_in_submission(self, arena, mock_player_factory):
        """Test validation with syntax errors - DummyArena accepts all submissions."""
        player = mock_player_factory(
            name="test_player",
            files={"main.py": "def broken(:\n  pass"},
        )
        is_valid, error = arena.validate_code(player)
        # DummyArena is for testing infrastructure, so it accepts all submissions
        assert is_valid is True
        assert error is None


class TestDummyResults:
    """Tests for DummyArena.get_results()"""

    @pytest.fixture
    def arena(self, tmp_log_dir, minimal_config):
        """Create DummyArena instance."""
        config = minimal_config.copy()
        config["game"]["name"] = "Dummy"
        arena = DummyArena.__new__(DummyArena)
        arena.submission = "main.py"
        arena.log_local = tmp_log_dir
        return arena

    def test_parse_results_player1_wins(self, arena, tmp_log_dir):
        """Test parsing results when player 1 wins."""
        # Create round log directory and result file
        round_dir = tmp_log_dir / "rounds" / "1"
        round_dir.mkdir(parents=True)
        result_file = round_dir / "result.log"
        result_file.write_text(
            """
Running simulation...
FINAL_RESULTS
Bot_1_main: 7 rounds won
Bot_2_main: 3 rounds won
"""
        )

        agents = [MockPlayer("Alice"), MockPlayer("Bob")]
        stats = RoundStats(round_num=1, agents=agents)

        arena.get_results(agents, round_num=1, stats=stats)

        assert stats.winner == "Alice"
        assert stats.scores["Alice"] == 7
        assert stats.scores["Bob"] == 3
        assert stats.player_stats["Alice"].score == 7
        assert stats.player_stats["Bob"].score == 3

    def test_parse_results_player2_wins(self, arena, tmp_log_dir):
        """Test parsing results when player 2 wins."""
        round_dir = tmp_log_dir / "rounds" / "1"
        round_dir.mkdir(parents=True)
        result_file = round_dir / "result.log"
        result_file.write_text(
            """
FINAL_RESULTS
Bot_1_main: 2 rounds won
Bot_2_main: 8 rounds won
"""
        )

        agents = [MockPlayer("Alice"), MockPlayer("Bob")]
        stats = RoundStats(round_num=1, agents=agents)

        arena.get_results(agents, round_num=1, stats=stats)

        assert stats.winner == "Bob"
        assert stats.scores["Alice"] == 2
        assert stats.scores["Bob"] == 8

    def test_parse_results_tie(self, arena, tmp_log_dir):
        """Test parsing results when scores are equal."""
        round_dir = tmp_log_dir / "rounds" / "1"
        round_dir.mkdir(parents=True)
        result_file = round_dir / "result.log"
        result_file.write_text(
            """
FINAL_RESULTS
Bot_1_main: 5 rounds won
Bot_2_main: 5 rounds won
"""
        )

        agents = [MockPlayer("Alice"), MockPlayer("Bob")]
        stats = RoundStats(round_num=1, agents=agents)

        arena.get_results(agents, round_num=1, stats=stats)

        # With equal scores, max() returns the first one found
        # The current implementation doesn't explicitly handle ties
        assert stats.scores["Alice"] == 5
        assert stats.scores["Bob"] == 5


class TestDummyConfig:
    """Tests for DummyArena configuration and properties."""

    def test_arena_name(self):
        """Test that arena has correct name."""
        assert DummyArena.name == "Dummy"

    def test_submission_file(self):
        """Test that submission file is main.py."""
        assert DummyArena.submission == "main.py"
