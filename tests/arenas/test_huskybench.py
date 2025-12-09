"""
Unit tests for HuskyBenchArena.

Tests validate_code() and get_results() methods without requiring Docker.
"""

from unittest.mock import patch

import pytest

from codeclash.arenas.arena import RoundStats
from codeclash.arenas.huskybench.huskybench import (
    HB_LOG_ENGINE,
    HB_PORT,
    HB_REGEX_SCORE,
    HB_SCRIPT,
    HuskyBenchArena,
)

from .conftest import MockPlayer

VALID_PLAYER_PY = """
from client.base_player import BasePlayer

class Player(BasePlayer):
    def get_action(self, game_state):
        return 'fold'
"""


class TestHuskyBenchValidation:
    """Tests for HuskyBenchArena.validate_code()"""

    @pytest.fixture
    def arena(self, tmp_log_dir, minimal_config):
        """Create HuskyBenchArena instance with mocked environment."""
        from pathlib import Path

        config = minimal_config.copy()
        config["game"]["sims_per_round"] = 10
        arena = HuskyBenchArena.__new__(HuskyBenchArena)
        arena.submission = "client/player.py"
        arena.log_local = tmp_log_dir
        arena.log_env = Path("/logs")  # Container log path
        arena.config = config
        arena.num_players = 2
        arena.run_engine = f"python engine/main.py --port {HB_PORT} --players 2 --sim --sim-rounds 10"
        arena.logger = type("Logger", (), {"debug": lambda self, msg: None, "info": lambda self, msg: None})()
        return arena

    @patch("codeclash.arenas.huskybench.huskybench.create_file_in_container")
    def test_valid_submission(self, mock_create_file, arena, mock_player_factory):
        """Test that a valid player.py passes validation."""
        player = mock_player_factory(
            name="test_player",
            files={
                "client/main.py": "# client main",
                "client/player.py": VALID_PLAYER_PY,
            },
            command_outputs={
                "ls client": {"output": "main.py\nplayer.py\n", "returncode": 0},
                f"chmod +x {HB_SCRIPT}; ./{HB_SCRIPT}": {"output": "", "returncode": 0},
            },
        )
        is_valid, error = arena.validate_code(player)
        assert is_valid is True
        assert error is None

    def test_missing_main_file(self, arena, mock_player_factory):
        """Test that missing client/main.py fails validation."""
        player = mock_player_factory(
            name="test_player",
            files={"client/player.py": VALID_PLAYER_PY},
            command_outputs={
                "ls client": {"output": "player.py\n", "returncode": 0},
            },
        )
        is_valid, error = arena.validate_code(player)
        assert is_valid is False
        assert "main.py" in error

    def test_missing_player_file(self, arena, mock_player_factory):
        """Test that missing client/player.py fails validation."""
        player = mock_player_factory(
            name="test_player",
            files={"client/main.py": "# main"},
            command_outputs={
                "ls client": {"output": "main.py\n", "returncode": 0},
            },
        )
        is_valid, error = arena.validate_code(player)
        assert is_valid is False
        assert "player.py" in error


class TestHuskyBenchResults:
    """Tests for HuskyBenchArena.get_results()"""

    @pytest.fixture
    def arena(self, tmp_log_dir, minimal_config):
        """Create HuskyBenchArena instance."""
        config = minimal_config.copy()
        config["game"]["name"] = "HuskyBench"
        config["game"]["sims_per_round"] = 10
        arena = HuskyBenchArena.__new__(HuskyBenchArena)
        arena.submission = "client/player.py"
        arena.log_local = tmp_log_dir
        arena.config = config
        arena.num_players = 2
        arena.logger = type("Logger", (), {"debug": lambda self, msg: None, "info": lambda self, msg: None})()
        return arena

    def _create_player_log(self, round_dir, player_name: str, player_id: str):
        """Create a player log file with connection info."""
        log_file = round_dir / f"{player_name}.log"
        log_file.write_text(f"Starting client...\nConnected with player ID: {player_id}\nGame started.\n")

    def _create_engine_log(self, round_dir, scores: list[tuple[str, int]]):
        """
        Create engine log file with final scores.

        Args:
            scores: List of (player_id, final_money) tuples
        """
        log_file = round_dir / HB_LOG_ENGINE
        lines = ["Engine starting...\n", "Game initialized.\n"]
        for player_id, money in scores:
            lines.append(f"Player {player_id} delta updated: +100 - 50 = 50, money: 1000 -> {money}\n")
        log_file.write_text("".join(lines))

    def test_parse_results_player1_wins(self, arena, tmp_log_dir):
        """Test parsing results when player 1 has more chips."""
        round_dir = tmp_log_dir / "rounds" / "1"
        round_dir.mkdir(parents=True)

        # Create player logs with their IDs
        self._create_player_log(round_dir, "Alice", "1")
        self._create_player_log(round_dir, "Bob", "2")

        # Create engine log with final scores
        self._create_engine_log(round_dir, [("1", 1500), ("2", 500)])

        agents = [MockPlayer("Alice"), MockPlayer("Bob")]
        stats = RoundStats(round_num=1, agents=agents)

        arena.get_results(agents, round_num=1, stats=stats)

        assert stats.winner == "Alice"
        assert stats.scores["Alice"] == 1500
        assert stats.scores["Bob"] == 500

    def test_parse_results_player2_wins(self, arena, tmp_log_dir):
        """Test parsing results when player 2 has more chips."""
        round_dir = tmp_log_dir / "rounds" / "1"
        round_dir.mkdir(parents=True)

        self._create_player_log(round_dir, "Alice", "1")
        self._create_player_log(round_dir, "Bob", "2")
        self._create_engine_log(round_dir, [("1", 300), ("2", 1700)])

        agents = [MockPlayer("Alice"), MockPlayer("Bob")]
        stats = RoundStats(round_num=1, agents=agents)

        arena.get_results(agents, round_num=1, stats=stats)

        assert stats.winner == "Bob"
        assert stats.scores["Alice"] == 300
        assert stats.scores["Bob"] == 1700


class TestHuskyBenchRegex:
    """Tests for the score parsing regex."""

    def test_regex_matches_score_line(self):
        """Test that the score regex correctly parses a score line."""
        line = "Player 1 delta updated: +100 - 50 = 50, money: 1000 -> 1050"
        match = HB_REGEX_SCORE.search(line)
        assert match is not None
        assert match.group(1) == "1"  # Player ID
        assert match.group(2) == "1050"  # Final money

    def test_regex_matches_multiple_digits(self):
        """Test regex with larger numbers."""
        line = "Player 42 delta updated: +500 - 200 = 300, money: 10000 -> 15000"
        match = HB_REGEX_SCORE.search(line)
        assert match is not None
        assert match.group(1) == "42"
        assert match.group(2) == "15000"

    def test_regex_does_not_match_other_lines(self):
        """Test that regex doesn't match non-score lines."""
        lines = [
            "Game started",
            "Player 1 folded",
            "Round complete",
        ]
        for line in lines:
            assert HB_REGEX_SCORE.search(line) is None


class TestHuskyBenchConfig:
    """Tests for HuskyBenchArena configuration and properties."""

    def test_arena_name(self):
        """Test that arena has correct name."""
        assert HuskyBenchArena.name == "HuskyBench"

    def test_submission_path(self):
        """Test that submission path is correct."""
        assert HuskyBenchArena.submission == "client/player.py"

    def test_port_constant(self):
        """Test that port constant is defined."""
        assert HB_PORT == 8000

    def test_description_mentions_poker(self):
        """Test that description mentions poker."""
        assert "poker" in HuskyBenchArena.description.lower()
