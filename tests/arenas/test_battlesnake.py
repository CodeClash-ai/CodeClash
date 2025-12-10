"""
Unit tests for BattleSnakeArena.

Tests validate_code() and get_results() methods without requiring Docker.
"""

import json

import pytest

from codeclash.arenas.arena import RoundStats
from codeclash.arenas.battlesnake.battlesnake import BattleSnakeArena
from codeclash.constants import RESULT_TIE

from .conftest import MockPlayer

VALID_BATTLESNAKE_BOT = """
import bottle

def info():
    return {"apiversion": "1", "author": "test", "color": "#888888", "head": "default", "tail": "default"}

def start(game_state):
    pass

def end(game_state):
    pass

def move(game_state):
    return {"move": "up"}

if __name__ == "__main__":
    bottle.run(host="0.0.0.0", port=8080)
"""


class TestBattleSnakeValidation:
    """Tests for BattleSnakeArena.validate_code()"""

    @pytest.fixture
    def arena(self, tmp_log_dir, minimal_config):
        """Create BattleSnakeArena instance with mocked environment."""
        config = minimal_config.copy()
        config["game"]["name"] = "BattleSnake"
        arena = BattleSnakeArena.__new__(BattleSnakeArena)
        arena.submission = "main.py"
        arena.log_local = tmp_log_dir
        return arena

    def test_valid_submission(self, arena, mock_player_factory):
        """Test that a valid BattleSnake bot passes validation."""
        player = mock_player_factory(
            name="test_player",
            files={"main.py": VALID_BATTLESNAKE_BOT},
            command_outputs={
                "ls": {"output": "main.py\n", "returncode": 0},
                "cat main.py": {"output": VALID_BATTLESNAKE_BOT, "returncode": 0},
            },
        )
        is_valid, error = arena.validate_code(player)
        assert is_valid is True
        assert error is None

    def test_missing_main_file(self, arena, mock_player_factory):
        """Test that missing main.py fails validation."""
        player = mock_player_factory(
            name="test_player",
            files={},
            command_outputs={
                "ls": {"output": "other.py\n", "returncode": 0},
            },
        )
        is_valid, error = arena.validate_code(player)
        assert is_valid is False
        assert "main.py" in error

    def test_missing_info_function(self, arena, mock_player_factory):
        """Test that missing info() function fails validation."""
        bot_code = """
def start(game_state):
    pass

def end(game_state):
    pass

def move(game_state):
    return {"move": "up"}
"""
        player = mock_player_factory(
            name="test_player",
            files={"main.py": bot_code},
            command_outputs={
                "ls": {"output": "main.py\n", "returncode": 0},
                "cat main.py": {"output": bot_code, "returncode": 0},
            },
        )
        is_valid, error = arena.validate_code(player)
        assert is_valid is False
        assert "def info(" in error

    def test_missing_move_function(self, arena, mock_player_factory):
        """Test that missing move() function fails validation."""
        bot_code = """
def info():
    return {}

def start(game_state):
    pass

def end(game_state):
    pass
"""
        player = mock_player_factory(
            name="test_player",
            files={"main.py": bot_code},
            command_outputs={
                "ls": {"output": "main.py\n", "returncode": 0},
                "cat main.py": {"output": bot_code, "returncode": 0},
            },
        )
        is_valid, error = arena.validate_code(player)
        assert is_valid is False
        assert "def move(" in error

    def test_missing_multiple_functions(self, arena, mock_player_factory):
        """Test that missing multiple functions reports all of them."""
        bot_code = """
def info():
    return {}
"""
        player = mock_player_factory(
            name="test_player",
            files={"main.py": bot_code},
            command_outputs={
                "ls": {"output": "main.py\n", "returncode": 0},
                "cat main.py": {"output": bot_code, "returncode": 0},
            },
        )
        is_valid, error = arena.validate_code(player)
        assert is_valid is False
        assert "def start(" in error
        assert "def end(" in error
        assert "def move(" in error


class TestBattleSnakeResults:
    """Tests for BattleSnakeArena.get_results()"""

    @pytest.fixture
    def arena(self, tmp_log_dir, minimal_config):
        """Create BattleSnakeArena instance."""
        config = minimal_config.copy()
        config["game"]["name"] = "BattleSnake"
        config["game"]["sims_per_round"] = 3
        arena = BattleSnakeArena.__new__(BattleSnakeArena)
        arena.submission = "main.py"
        arena.log_local = tmp_log_dir
        arena.config = config  # game_config is a property that reads from self.config
        arena._failed_to_start_player = []
        return arena

    def _create_sim_file(self, round_dir, idx: int, winner_name: str, is_draw: bool = False):
        """Helper to create a simulation result file."""
        sim_file = round_dir / f"sim_{idx}.jsonl"
        result = {"isDraw": is_draw, "winnerName": winner_name if not is_draw else None}
        # Write multiple lines with result as last line
        sim_file.write_text(f'{{"turn": 1}}\n{{"turn": 2}}\n{json.dumps(result)}\n')

    def test_parse_results_clear_winner(self, arena, tmp_log_dir):
        """Test parsing results with a clear winner."""
        round_dir = tmp_log_dir / "rounds" / "1"
        round_dir.mkdir(parents=True)

        # Alice wins 2 games, Bob wins 1
        self._create_sim_file(round_dir, 0, "Alice")
        self._create_sim_file(round_dir, 1, "Alice")
        self._create_sim_file(round_dir, 2, "Bob")

        agents = [MockPlayer("Alice"), MockPlayer("Bob")]
        stats = RoundStats(round_num=1, agents=agents)

        arena.get_results(agents, round_num=1, stats=stats)

        assert stats.winner == "Alice"
        assert stats.scores["Alice"] == 2
        assert stats.scores["Bob"] == 1

    def test_parse_results_with_draws(self, arena, tmp_log_dir):
        """Test parsing results that include draws."""
        round_dir = tmp_log_dir / "rounds" / "1"
        round_dir.mkdir(parents=True)

        self._create_sim_file(round_dir, 0, "Alice")
        self._create_sim_file(round_dir, 1, None, is_draw=True)
        self._create_sim_file(round_dir, 2, "Bob")

        agents = [MockPlayer("Alice"), MockPlayer("Bob")]
        stats = RoundStats(round_num=1, agents=agents)

        arena.get_results(agents, round_num=1, stats=stats)

        # Both have 1 win, plus 1 draw
        assert stats.scores["Alice"] == 1
        assert stats.scores["Bob"] == 1
        assert stats.scores[RESULT_TIE] == 1

    def test_parse_results_all_draws(self, arena, tmp_log_dir):
        """Test parsing results when all games are draws."""
        round_dir = tmp_log_dir / "rounds" / "1"
        round_dir.mkdir(parents=True)

        for idx in range(3):
            self._create_sim_file(round_dir, idx, None, is_draw=True)

        agents = [MockPlayer("Alice"), MockPlayer("Bob")]
        stats = RoundStats(round_num=1, agents=agents)

        arena.get_results(agents, round_num=1, stats=stats)

        assert stats.winner == RESULT_TIE
        assert stats.scores[RESULT_TIE] == 3

    def test_parse_results_tie_wins(self, arena, tmp_log_dir):
        """Test parsing results when players have equal wins."""
        arena.game_config["sims_per_round"] = 4
        round_dir = tmp_log_dir / "rounds" / "1"
        round_dir.mkdir(parents=True)

        self._create_sim_file(round_dir, 0, "Alice")
        self._create_sim_file(round_dir, 1, "Alice")
        self._create_sim_file(round_dir, 2, "Bob")
        self._create_sim_file(round_dir, 3, "Bob")

        agents = [MockPlayer("Alice"), MockPlayer("Bob")]
        stats = RoundStats(round_num=1, agents=agents)

        arena.get_results(agents, round_num=1, stats=stats)

        assert stats.winner == RESULT_TIE
        assert stats.scores["Alice"] == 2
        assert stats.scores["Bob"] == 2


class TestBattleSnakeConfig:
    """Tests for BattleSnakeArena configuration and properties."""

    def test_arena_name(self):
        """Test that arena has correct name."""
        assert BattleSnakeArena.name == "BattleSnake"

    def test_submission_file(self):
        """Test that submission file is main.py."""
        assert BattleSnakeArena.submission == "main.py"

    def test_default_args(self):
        """Test default arena arguments."""
        assert BattleSnakeArena.default_args["width"] == 11
        assert BattleSnakeArena.default_args["height"] == 11
        assert BattleSnakeArena.default_args["browser"] is False
