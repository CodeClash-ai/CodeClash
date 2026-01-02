"""
Unit tests for BattleCodeArena.

Tests validate_code() and get_results() methods without requiring Docker.
"""

import pytest

from codeclash.arenas.arena import RoundStats
from codeclash.arenas.battlecode2025.battlecode2025 import BC_FOLDER, BC_LOG, BC_TIE, BattleCode2025Arena

from .conftest import MockPlayer

VALID_BOT_PY = """
from battlecode25.stubs import *

def turn():
    # Simple bot that does nothing
    pass
"""


class TestBattleCodeValidation:
    """Tests for BattleCodeArena.validate_code()"""

    @pytest.fixture
    def arena(self, tmp_log_dir, minimal_config):
        """Create BattleCodeArena instance with mocked environment."""
        arena = BattleCode2025Arena.__new__(BattleCode2025Arena)
        arena.submission = f"src/{BC_FOLDER}"
        arena.log_local = tmp_log_dir
        arena.run_cmd_round = "python run.py run"
        return arena

    def test_valid_submission(self, arena, mock_player_factory):
        """Test that a valid bot.py passes validation."""
        player = mock_player_factory(
            name="test_player",
            files={
                f"src/{BC_FOLDER}/bot.py": VALID_BOT_PY,
            },
            command_outputs={
                "ls src": {"output": f"{BC_FOLDER}\n", "returncode": 0},
                f"ls src/{BC_FOLDER}": {"output": "bot.py\n__init__.py\n", "returncode": 0},
                f"cat src/{BC_FOLDER}/bot.py": {"output": VALID_BOT_PY, "returncode": 0},
            },
        )
        is_valid, error = arena.validate_code(player)
        assert is_valid is True
        assert error is None

    def test_missing_mysubmission_directory(self, arena, mock_player_factory):
        """Test that missing src/mysubmission/ fails validation."""
        player = mock_player_factory(
            name="test_player",
            files={},
            command_outputs={
                "ls src": {"output": "otherpackage\n", "returncode": 0},
            },
        )
        is_valid, error = arena.validate_code(player)
        assert is_valid is False
        assert BC_FOLDER in error

    def test_missing_bot_file(self, arena, mock_player_factory):
        """Test that missing bot.py fails validation."""
        player = mock_player_factory(
            name="test_player",
            files={
                f"src/{BC_FOLDER}/__init__.py": "",
            },
            command_outputs={
                "ls src": {"output": f"{BC_FOLDER}\n", "returncode": 0},
                f"ls src/{BC_FOLDER}": {"output": "__init__.py\n", "returncode": 0},
            },
        )
        is_valid, error = arena.validate_code(player)
        assert is_valid is False
        assert "bot.py" in error

    def test_missing_turn_function(self, arena, mock_player_factory):
        """Test that bot.py without turn() function fails validation."""
        invalid_bot = """
from battlecode25.stubs import *

def setup():
    pass

def run():
    pass
"""
        player = mock_player_factory(
            name="test_player",
            files={
                f"src/{BC_FOLDER}/bot.py": invalid_bot,
            },
            command_outputs={
                "ls src": {"output": f"{BC_FOLDER}\n", "returncode": 0},
                f"ls src/{BC_FOLDER}": {"output": "bot.py\n", "returncode": 0},
                f"cat src/{BC_FOLDER}/bot.py": {"output": invalid_bot, "returncode": 0},
            },
        )
        is_valid, error = arena.validate_code(player)
        assert is_valid is False
        assert "turn()" in error


class TestBattleCodeResults:
    """Tests for BattleCodeArena.get_results()"""

    @pytest.fixture
    def arena(self, tmp_log_dir, minimal_config):
        """Create BattleCodeArena instance."""
        config = minimal_config.copy()
        config["game"]["name"] = "BattleCode"
        config["game"]["sims_per_round"] = 3
        arena = BattleCode2025Arena.__new__(BattleCode2025Arena)
        arena.submission = f"src/{BC_FOLDER}"
        arena.log_local = tmp_log_dir
        arena.config = config
        arena.logger = type("Logger", (), {"debug": lambda self, msg: None, "info": lambda self, msg: None})()
        return arena

    def _create_sim_log(self, round_dir, idx: int, winner_key: str, is_coin_flip: bool = False):
        """
        Create a simulation log file.

        Args:
            winner_key: "A" or "B" to indicate which player won
            is_coin_flip: If True, sets reason to coin flip (arbitrary win)
        """
        log_file = round_dir / BC_LOG.format(idx=idx)
        reason = BC_TIE if is_coin_flip else "Reason: Team won by controlling more territory."
        # The log format has winner info in third-to-last line
        log_file.write_text(
            f"""Round starting...
Turn 100...
Turn 200...
Winner: Team ({winner_key}) wins (game over)
{reason}
Final stats
"""
        )

    def test_parse_results_player_a_wins(self, arena, tmp_log_dir):
        """Test parsing results when player A (first player) wins."""
        round_dir = tmp_log_dir / "rounds" / "1"
        round_dir.mkdir(parents=True)

        # A wins 2 games, B wins 1
        self._create_sim_log(round_dir, 0, "A")
        self._create_sim_log(round_dir, 1, "A")
        self._create_sim_log(round_dir, 2, "B")

        agents = [MockPlayer("Alice"), MockPlayer("Bob")]
        stats = RoundStats(round_num=1, agents=agents)

        arena.get_results(agents, round_num=1, stats=stats)

        assert stats.winner == "Alice"
        assert stats.scores["Alice"] == 2
        assert stats.scores["Bob"] == 1

    def test_parse_results_player_b_wins(self, arena, tmp_log_dir):
        """Test parsing results when player B (second player) wins."""
        round_dir = tmp_log_dir / "rounds" / "1"
        round_dir.mkdir(parents=True)

        # A wins 1 game, B wins 2
        self._create_sim_log(round_dir, 0, "B")
        self._create_sim_log(round_dir, 1, "B")
        self._create_sim_log(round_dir, 2, "A")

        agents = [MockPlayer("Alice"), MockPlayer("Bob")]
        stats = RoundStats(round_num=1, agents=agents)

        arena.get_results(agents, round_num=1, stats=stats)

        assert stats.winner == "Bob"
        assert stats.scores["Alice"] == 1
        assert stats.scores["Bob"] == 2

    def test_parse_results_with_coin_flips(self, arena, tmp_log_dir):
        """Test parsing results where some wins are coin flips (don't count)."""
        round_dir = tmp_log_dir / "rounds" / "1"
        round_dir.mkdir(parents=True)

        # Coin flip wins should be treated as ties
        self._create_sim_log(round_dir, 0, "A")
        self._create_sim_log(round_dir, 1, "A", is_coin_flip=True)  # Doesn't count
        self._create_sim_log(round_dir, 2, "B")

        agents = [MockPlayer("Alice"), MockPlayer("Bob")]
        stats = RoundStats(round_num=1, agents=agents)

        arena.get_results(agents, round_num=1, stats=stats)

        # Only non-coin-flip wins count
        assert stats.scores["Alice"] == 1
        assert stats.scores["Bob"] == 1


class TestBattleCodeConfig:
    """Tests for BattleCodeArena configuration and properties."""

    def test_arena_name(self):
        """Test that arena has correct name."""
        assert BattleCode2025Arena.name == "BattleCode2025"

    def test_submission_path(self):
        """Test that submission path is correct."""
        assert BattleCode2025Arena.submission == f"src/{BC_FOLDER}"

    def test_bc_folder_name(self):
        """Test that BC folder name is mysubmission."""
        assert BC_FOLDER == "mysubmission"

    def test_default_args(self):
        """Test default arguments."""
        assert BattleCode2025Arena.default_args.get("maps") == "quack"

    def test_description_mentions_python(self):
        """Test that description mentions Python as the language."""
        assert "python" in BattleCode2025Arena.description.lower()
