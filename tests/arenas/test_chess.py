"""
Unit tests for ChessArena.

Tests validate_code() and get_results() methods without requiring Docker.
"""

import json
import pytest

from codeclash.arenas.arena import RoundStats
from codeclash.arenas.chess.chess import ChessArena
from codeclash.constants import RESULT_TIE

from .conftest import MockPlayer


class TestChessValidation:
	"""Tests for ChessArena.validate_code()"""

	@pytest.fixture
	def arena(self, tmp_log_dir, minimal_config):
		"""Create ChessArena instance with mocked environment."""
		arena = ChessArena.__new__(ChessArena)
		arena.submission = "src/"
		arena.log_local = tmp_log_dir
		# Minimal attributes used in validate_code
		arena.logger = type("Logger", (), {"debug": lambda self, msg: None, "info": lambda self, msg: None})()
		return arena

	def test_valid_submission(self, arena, mock_player_factory):
		"""Valid C++ engine compiles and produces `src/kojiro` executable."""
		player = mock_player_factory(
			name="test_player",
			files={
				# Not strictly used by validate_code, but helpful if commands fall back to defaults
				"src/kojiro": "",
			},
			command_outputs={
				"ls": {"output": "src\n", "returncode": 0},
				"cd src && make native": {"output": "Compile OK", "returncode": 0},
				"ls src/kojiro": {"output": "kojiro\n", "returncode": 0},
			},
		)

		is_valid, error = arena.validate_code(player)
		assert is_valid is True
		assert error is None

	def test_missing_src_directory(self, arena, mock_player_factory):
		"""Missing `src/` directory fails validation."""
		player = mock_player_factory(
			name="test_player",
			files={},
			command_outputs={
				"ls": {"output": "README.md\n", "returncode": 0},
			},
		)

		is_valid, error = arena.validate_code(player)
		assert is_valid is False
		assert "src/" in error

	def test_compilation_failure(self, arena, mock_player_factory):
		"""Compilation errors are surfaced and fail validation."""
		player = mock_player_factory(
			name="test_player",
			files={},
			command_outputs={
				"ls": {"output": "src\n", "returncode": 0},
				"cd src && make native": {"output": "error: failed to compile", "returncode": 1},
			},
		)

		is_valid, error = arena.validate_code(player)
		assert is_valid is False
		assert "Compilation failed" in error

	def test_missing_executable_after_compilation(self, arena, mock_player_factory):
		"""Compilation succeeds but missing `kojiro` executable fails validation."""
		player = mock_player_factory(
			name="test_player",
			files={},
			command_outputs={
				"ls": {"output": "src\n", "returncode": 0},
				"cd src && make native": {"output": "Compile OK", "returncode": 0},
				"ls src/kojiro": {"output": "", "returncode": 1},
			},
		)

		is_valid, error = arena.validate_code(player)
		assert is_valid is False
		assert "executable 'kojiro' not found" in error


class TestChessResults:
	"""Tests for ChessArena.get_results()"""

	@pytest.fixture
	def arena(self, tmp_log_dir, minimal_config):
		"""Create ChessArena-like instance with local logging directory."""
		config = minimal_config.copy()
		config["game"]["name"] = "Chess"
		config["game"]["sims_per_round"] = 2

		arena = ChessArena.__new__(ChessArena)
		arena.submission = "src/"
		arena.log_local = tmp_log_dir
		arena.config = config
		# Lightweight logger stub
		arena.logger = type(
			"Logger",
			(),
			{
				"debug": lambda self, msg: None,
				"info": lambda self, msg: None,
				"warning": lambda self, msg: None,
				"error": lambda self, msg, **kwargs: None,
			},
		)()
		return arena

	def _write_pairings(self, round_dir, pairings):
		pairings_file = round_dir / "pairings.json"
		pairings_file.write_text(json.dumps(pairings, indent=2))

	def _write_pgn(self, file_path, white: str, black: str, result: str):
		content = (
			"""
[Event "FastChess Match"]
[Site "-"]
[Date "2026.01.07"]
[Round "1"]
""".strip()
			+ f"\n[White \"{white}\"]\n[Black \"{black}\"]\n[Result \"{result}\"]\n\n"
		)
		file_path.write_text(content)

	def test_player1_wins(self, arena, tmp_log_dir):
		"""Alice wins one match; overall winner is Alice."""
		round_dir = tmp_log_dir / "rounds" / "1"
		round_dir.mkdir(parents=True)

		# sims_per_round = 2 but only first match is valid; second missing -> ignored
		pairings = [
			{"match_idx": 0, "agent1": "Alice", "agent2": "Bob"},
			{"match_idx": 1, "agent1": "Alice", "agent2": "Bob"},
		]
		self._write_pairings(round_dir, pairings)

		# Match 0: Alice (White) wins
		self._write_pgn(round_dir / "match_0.pgn", white="Alice", black="Bob", result="1-0")
		# Match 1: no file -> ignored

		agents = [MockPlayer("Alice"), MockPlayer("Bob")]
		stats = RoundStats(round_num=1, agents=agents)

		arena.get_results(agents, round_num=1, stats=stats)

		assert stats.winner == "Alice"
		assert stats.scores["Alice"] == 1
		assert stats.scores["Bob"] == 0

	def test_player2_wins(self, arena, tmp_log_dir):
		"""Bob wins one match; overall winner is Bob."""
		round_dir = tmp_log_dir / "rounds" / "1"
		round_dir.mkdir(parents=True)

		pairings = [
			{"match_idx": 0, "agent1": "Alice", "agent2": "Bob"},
			{"match_idx": 1, "agent1": "Alice", "agent2": "Bob"},
		]
		self._write_pairings(round_dir, pairings)

		# Match 0: Bob (Black) wins
		self._write_pgn(round_dir / "match_0.pgn", white="Alice", black="Bob", result="0-1")

		agents = [MockPlayer("Alice"), MockPlayer("Bob")]
		stats = RoundStats(round_num=1, agents=agents)

		arena.get_results(agents, round_num=1, stats=stats)

		assert stats.winner == "Bob"
		assert stats.scores["Alice"] == 0
		assert stats.scores["Bob"] == 1

	def test_all_draws(self, arena, tmp_log_dir):
		"""All matches draw -> overall tie with zero scores."""
		round_dir = tmp_log_dir / "rounds" / "1"
		round_dir.mkdir(parents=True)

		pairings = [
			{"match_idx": 0, "agent1": "Alice", "agent2": "Bob"},
			{"match_idx": 1, "agent1": "Alice", "agent2": "Bob"},
		]
		self._write_pairings(round_dir, pairings)

		# Two draws
		self._write_pgn(round_dir / "match_0.pgn", white="Alice", black="Bob", result="1/2-1/2")
		self._write_pgn(round_dir / "match_1.pgn", white="Bob", black="Alice", result="1/2-1/2")

		agents = [MockPlayer("Alice"), MockPlayer("Bob")]
		stats = RoundStats(round_num=1, agents=agents)

		arena.get_results(agents, round_num=1, stats=stats)

		assert stats.winner == RESULT_TIE
		assert stats.scores["Alice"] == 0
		assert stats.scores["Bob"] == 0

	def test_split_wins_results_in_tie(self, arena, tmp_log_dir):
		"""Each player wins one match -> tie overall."""
		round_dir = tmp_log_dir / "rounds" / "1"
		round_dir.mkdir(parents=True)

		pairings = [
			{"match_idx": 0, "agent1": "Alice", "agent2": "Bob"},
			{"match_idx": 1, "agent1": "Alice", "agent2": "Bob"},
		]
		self._write_pairings(round_dir, pairings)

		# Alice wins match 0, Bob wins match 1
		self._write_pgn(round_dir / "match_0.pgn", white="Alice", black="Bob", result="1-0")
		self._write_pgn(round_dir / "match_1.pgn", white="Alice", black="Bob", result="0-1")

		agents = [MockPlayer("Alice"), MockPlayer("Bob")]
		stats = RoundStats(round_num=1, agents=agents)

		arena.get_results(agents, round_num=1, stats=stats)

		assert stats.winner == RESULT_TIE
		assert stats.scores["Alice"] == 1
		assert stats.scores["Bob"] == 1


class TestChessConfig:
	"""Tests for ChessArena configuration and properties."""

	def test_arena_name(self):
		assert ChessArena.name == "Chess"

	def test_submission_folder(self):
		assert ChessArena.submission == "src/"

	def test_default_args_contains_time_control(self):
		assert "time_control" in ChessArena.default_args

