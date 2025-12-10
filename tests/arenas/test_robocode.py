"""
Unit tests for RoboCodeArena.

Tests validate_code() and get_results() methods without requiring Docker.
"""

import pytest

from codeclash.arenas.arena import RoundStats
from codeclash.arenas.robocode.robocode import RC_FILE, SIMS_PER_RUN, RoboCodeArena

from .conftest import MockPlayer

VALID_JAVA_TANK = """
package custom;

import robocode.*;

public class MyTank extends Robot {
    public void run() {
        while (true) {
            ahead(100);
            turnGunRight(360);
            back(100);
            turnGunRight(360);
        }
    }

    public void onScannedRobot(ScannedRobotEvent e) {
        fire(1);
    }
}
"""


class TestRoboCodeValidation:
    """Tests for RoboCodeArena.validate_code()"""

    @pytest.fixture
    def arena(self, tmp_log_dir, minimal_config):
        """Create RoboCodeArena instance with mocked environment."""
        arena = RoboCodeArena.__new__(RoboCodeArena)
        arena.submission = "robots/custom/"
        arena.log_local = tmp_log_dir
        arena.run_cmd_round = "./robocode.sh -nodisplay -nosound"
        return arena

    def test_valid_submission(self, arena, mock_player_factory):
        """Test that a valid Java tank passes validation."""
        player = mock_player_factory(
            name="test_player",
            files={
                "robots/custom/MyTank.java": VALID_JAVA_TANK,
            },
            command_outputs={
                "ls": {"output": "robots\n", "returncode": 0},
                "ls robots": {"output": "custom\n", "returncode": 0},
                "ls robots/custom": {"output": "MyTank.java\n", "returncode": 0},
                'javac -cp "libs/robocode.jar" robots/custom/*.java': {
                    "output": "",
                    "returncode": 0,
                },
            },
        )
        # After compilation, class file exists
        player.environment.command_outputs["ls robots/custom"] = {
            "output": "MyTank.java\nMyTank.class\n",
            "returncode": 0,
        }
        is_valid, error = arena.validate_code(player)
        assert is_valid is True
        assert error is None

    def test_missing_robots_directory(self, arena, mock_player_factory):
        """Test that missing robots/ directory fails validation."""
        player = mock_player_factory(
            name="test_player",
            files={},
            command_outputs={
                "ls": {"output": "src\n", "returncode": 0},
            },
        )
        is_valid, error = arena.validate_code(player)
        assert is_valid is False
        assert "robots" in error.lower()

    def test_missing_custom_directory(self, arena, mock_player_factory):
        """Test that missing robots/custom/ directory fails validation."""
        player = mock_player_factory(
            name="test_player",
            files={"robots/sample/Sample.java": "public class Sample {}"},
            command_outputs={
                "ls": {"output": "robots\n", "returncode": 0},
                "ls robots": {"output": "sample\n", "returncode": 0},
            },
        )
        is_valid, error = arena.validate_code(player)
        assert is_valid is False
        assert "custom" in error.lower()

    def test_missing_mytank_file(self, arena, mock_player_factory):
        """Test that missing MyTank.java fails validation."""
        player = mock_player_factory(
            name="test_player",
            files={"robots/custom/OtherBot.java": "public class OtherBot {}"},
            command_outputs={
                "ls": {"output": "robots\n", "returncode": 0},
                "ls robots": {"output": "custom\n", "returncode": 0},
                "ls robots/custom": {"output": "OtherBot.java\n", "returncode": 0},
            },
        )
        is_valid, error = arena.validate_code(player)
        assert is_valid is False
        assert "MyTank.java" in error

    def test_compilation_failure(self, arena, mock_player_factory):
        """Test that Java compilation failure fails validation."""
        player = mock_player_factory(
            name="test_player",
            files={"robots/custom/MyTank.java": "invalid java code {{{"},
            command_outputs={
                "ls": {"output": "robots\n", "returncode": 0},
                "ls robots": {"output": "custom\n", "returncode": 0},
                "ls robots/custom": {"output": "MyTank.java\n", "returncode": 0},
                'javac -cp "libs/robocode.jar" robots/custom/*.java': {
                    "output": "error: class, interface, or enum expected",
                    "returncode": 1,
                },
            },
        )
        is_valid, error = arena.validate_code(player)
        assert is_valid is False
        assert "compilation" in error.lower()


class TestRoboCodeResults:
    """Tests for RoboCodeArena.get_results()"""

    @pytest.fixture
    def arena(self, tmp_log_dir, minimal_config):
        """Create RoboCodeArena instance."""
        config = minimal_config.copy()
        config["game"]["name"] = "RoboCode"
        config["game"]["sims_per_round"] = 20  # 2 * SIMS_PER_RUN
        arena = RoboCodeArena.__new__(RoboCodeArena)
        arena.submission = "robots/custom/"
        arena.log_local = tmp_log_dir
        arena.config = config
        arena.logger = type("Logger", (), {"debug": lambda self, msg: None, "info": lambda self, msg: None})()
        return arena

    def _create_results_file(self, round_dir, idx: int, results: list[tuple[int, str, int]]):
        """
        Create a results file.

        Args:
            results: List of (rank, bot_name, total_score) tuples
        """
        results_file = round_dir / f"results_{idx}.txt"
        lines = ["Results:\n", "BattlefieldWidth, 800\n", "BattlefieldHeight, 600\n"]
        for rank, bot_name, total_score in results:
            lines.append(f"{rank}st: {bot_name}  {total_score}\n")
        results_file.write_text("".join(lines))

    def test_parse_results_player1_wins(self, arena, tmp_log_dir):
        """Test parsing results when player 1 has higher total score."""
        round_dir = tmp_log_dir / "rounds" / "1"
        round_dir.mkdir(parents=True)

        # Create results files for 2 simulations (20 sims / SIMS_PER_RUN=10 = 2)
        self._create_results_file(
            round_dir,
            0,
            [
                (1, "Alice.MyTank", 5000),
                (2, "Bob.MyTank", 3000),
            ],
        )
        self._create_results_file(
            round_dir,
            1,
            [
                (1, "Alice.MyTank", 4500),
                (2, "Bob.MyTank", 3500),
            ],
        )

        agents = [MockPlayer("Alice"), MockPlayer("Bob")]
        stats = RoundStats(round_num=1, agents=agents)

        arena.get_results(agents, round_num=1, stats=stats)

        assert stats.winner == "Alice"
        assert stats.scores["Alice"] == 9500
        assert stats.scores["Bob"] == 6500

    def test_parse_results_player2_wins(self, arena, tmp_log_dir):
        """Test parsing results when player 2 has higher total score."""
        round_dir = tmp_log_dir / "rounds" / "1"
        round_dir.mkdir(parents=True)

        self._create_results_file(
            round_dir,
            0,
            [
                (2, "Alice.MyTank", 2000),
                (1, "Bob.MyTank", 5000),
            ],
        )
        self._create_results_file(
            round_dir,
            1,
            [
                (2, "Alice.MyTank", 2500),
                (1, "Bob.MyTank", 4500),
            ],
        )

        agents = [MockPlayer("Alice"), MockPlayer("Bob")]
        stats = RoundStats(round_num=1, agents=agents)

        arena.get_results(agents, round_num=1, stats=stats)

        assert stats.winner == "Bob"
        assert stats.scores["Alice"] == 4500
        assert stats.scores["Bob"] == 9500


class TestRoboCodeConfig:
    """Tests for RoboCodeArena configuration and properties."""

    def test_arena_name(self):
        """Test that arena has correct name."""
        assert RoboCodeArena.name == "RoboCode"

    def test_submission_path(self):
        """Test that submission path is correct."""
        assert RoboCodeArena.submission == "robots/custom/"

    def test_main_file(self):
        """Test that main file is MyTank.java."""
        assert str(RC_FILE) == "MyTank.java"

    def test_sims_per_run(self):
        """Test that simulations per run is configured."""
        assert SIMS_PER_RUN == 10

    def test_default_args(self):
        """Test default arguments include nodisplay and nosound."""
        assert RoboCodeArena.default_args.get("nodisplay") is True
        assert RoboCodeArena.default_args.get("nosound") is True

    def test_description_mentions_java(self):
        """Test that description mentions Java as the language."""
        assert "java" in RoboCodeArena.description.lower()
