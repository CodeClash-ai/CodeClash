"""
Unit tests for RobotRumbleArena.

Tests validate_code() and get_results() methods without requiring Docker.
"""

import json

import pytest

from codeclash.arenas.arena import RoundStats
from codeclash.arenas.robotrumble.robotrumble import (
    MAP_EXT_TO_HEADER,
    ROBOTRUMBLE_HIDDEN_EXEC,
    RobotRumbleArena,
)
from codeclash.constants import RESULT_TIE

from .conftest import MockPlayer

VALID_JS_ROBOT = """
function robot(state, unit) {
    if (state.turn % 2 === 0) {
        return Action.move(Direction.East);
    }
    return Action.attack(Direction.South);
}
"""

VALID_PY_ROBOT = """
def robot(state, unit):
    if state.turn % 2 == 0:
        return Action.move(Direction.East)
    return Action.attack(Direction.South)
"""


class TestRobotRumbleValidation:
    """Tests for RobotRumbleArena.validate_code()"""

    @pytest.fixture
    def arena(self, tmp_log_dir, minimal_config):
        """Create RobotRumbleArena instance with mocked environment."""
        arena = RobotRumbleArena.__new__(RobotRumbleArena)
        arena.submission = "robot.js"
        arena.log_local = tmp_log_dir
        arena.run_cmd_round = "./rumblebot run term --raw"
        return arena

    def test_valid_js_submission(self, arena, mock_player_factory):
        """Test that a valid JavaScript robot passes validation."""
        player = mock_player_factory(
            name="test_player",
            files={"robot.js": VALID_JS_ROBOT},
            command_outputs={
                "test -f robot.js && echo 'exists'": {"output": "exists", "returncode": 0},
                "cat robot.js": {"output": VALID_JS_ROBOT, "returncode": 0},
                f'echo "robot.js" > {ROBOTRUMBLE_HIDDEN_EXEC}': {"output": "", "returncode": 0},
                "./rumblebot run term --raw robot.js robot.js -t 1": {
                    "output": "Blue won",
                    "returncode": 0,
                },
            },
        )
        is_valid, error = arena.validate_code(player)
        assert is_valid is True
        assert error is None

    def test_valid_py_submission(self, arena, mock_player_factory):
        """Test that a valid Python robot passes validation."""
        player = mock_player_factory(
            name="test_player",
            files={"robot.py": VALID_PY_ROBOT},
            command_outputs={
                "test -f robot.js && echo 'exists'": {"output": "", "returncode": 1},
                "test -f robot.py && echo 'exists'": {"output": "exists", "returncode": 0},
                "cat robot.py": {"output": VALID_PY_ROBOT, "returncode": 0},
                f'echo "robot.py" > {ROBOTRUMBLE_HIDDEN_EXEC}': {"output": "", "returncode": 0},
                "./rumblebot run term --raw robot.py robot.py -t 1": {
                    "output": "Blue won",
                    "returncode": 0,
                },
            },
        )
        is_valid, error = arena.validate_code(player)
        assert is_valid is True
        assert error is None

    def test_missing_robot_file(self, arena, mock_player_factory):
        """Test that missing robot file fails validation."""
        player = mock_player_factory(
            name="test_player",
            files={},
            command_outputs={
                "test -f robot.js && echo 'exists'": {"output": "", "returncode": 1},
                "test -f robot.py && echo 'exists'": {"output": "", "returncode": 1},
            },
        )
        is_valid, error = arena.validate_code(player)
        assert is_valid is False
        assert "robot.js" in error or "robot.py" in error

    def test_missing_robot_function_js(self, arena, mock_player_factory):
        """Test that missing robot function in JS fails validation."""
        invalid_code = "function notRobot(state, unit) { return null; }"
        player = mock_player_factory(
            name="test_player",
            files={"robot.js": invalid_code},
            command_outputs={
                "test -f robot.js && echo 'exists'": {"output": "exists", "returncode": 0},
                "cat robot.js": {"output": invalid_code, "returncode": 0},
            },
        )
        is_valid, error = arena.validate_code(player)
        assert is_valid is False
        assert "robot function" in error.lower()

    def test_missing_robot_function_py(self, arena, mock_player_factory):
        """Test that missing robot function in Python fails validation."""
        invalid_code = "def not_robot(state, unit):\n    return None"
        player = mock_player_factory(
            name="test_player",
            files={"robot.py": invalid_code},
            command_outputs={
                "test -f robot.js && echo 'exists'": {"output": "", "returncode": 1},
                "test -f robot.py && echo 'exists'": {"output": "exists", "returncode": 0},
                "cat robot.py": {"output": invalid_code, "returncode": 0},
            },
        )
        is_valid, error = arena.validate_code(player)
        assert is_valid is False
        assert "robot function" in error.lower()


class TestRobotRumbleResults:
    """Tests for RobotRumbleArena.get_results()"""

    @pytest.fixture
    def arena(self, tmp_log_dir, minimal_config):
        """Create RobotRumbleArena instance."""
        config = minimal_config.copy()
        config["game"]["name"] = "RobotRumble"
        config["game"]["sims_per_round"] = 5
        config["game"]["args"] = {"raw": True}
        arena = RobotRumbleArena.__new__(RobotRumbleArena)
        arena.submission = "robot.js"
        arena.log_local = tmp_log_dir
        arena.config = config
        arena.sim_ext = "json"
        arena.logger = type("Logger", (), {"warning": lambda self, msg: None, "info": lambda self, msg: None})()
        return arena

    def _create_json_sim_file(self, round_dir, idx: int, winner: str):
        """Helper to create a JSON simulation result file."""
        sim_file = round_dir / f"sim_{idx}.json"
        result = {"winner": winner}  # "Blue", "Red", or "Tie"
        sim_file.write_text(json.dumps(result))

    def _create_txt_sim_file(self, round_dir, idx: int, winner_text: str):
        """Helper to create a TXT simulation result file."""
        sim_file = round_dir / f"sim_{idx}.txt"
        sim_file.write_text(f"Turn 100\n{winner_text}\n")

    def test_parse_json_results_blue_wins(self, arena, tmp_log_dir):
        """Test parsing JSON results when Blue (player 1) wins more."""
        round_dir = tmp_log_dir / "rounds" / "1"
        round_dir.mkdir(parents=True)

        # Blue (Alice) wins 3, Red (Bob) wins 2
        self._create_json_sim_file(round_dir, 0, "Blue")
        self._create_json_sim_file(round_dir, 1, "Blue")
        self._create_json_sim_file(round_dir, 2, "Blue")
        self._create_json_sim_file(round_dir, 3, "Red")
        self._create_json_sim_file(round_dir, 4, "Red")

        agents = [MockPlayer("Alice"), MockPlayer("Bob")]
        stats = RoundStats(round_num=1, agents=agents)

        arena.get_results(agents, round_num=1, stats=stats)

        assert stats.winner == "Alice"
        assert stats.scores["Alice"] == 3
        assert stats.scores["Bob"] == 2

    def test_parse_json_results_red_wins(self, arena, tmp_log_dir):
        """Test parsing JSON results when Red (player 2) wins more."""
        round_dir = tmp_log_dir / "rounds" / "1"
        round_dir.mkdir(parents=True)

        # Blue (Alice) wins 1, Red (Bob) wins 4
        self._create_json_sim_file(round_dir, 0, "Blue")
        self._create_json_sim_file(round_dir, 1, "Red")
        self._create_json_sim_file(round_dir, 2, "Red")
        self._create_json_sim_file(round_dir, 3, "Red")
        self._create_json_sim_file(round_dir, 4, "Red")

        agents = [MockPlayer("Alice"), MockPlayer("Bob")]
        stats = RoundStats(round_num=1, agents=agents)

        arena.get_results(agents, round_num=1, stats=stats)

        assert stats.winner == "Bob"
        assert stats.scores["Alice"] == 1
        assert stats.scores["Bob"] == 4

    def test_parse_json_results_tie(self, arena, tmp_log_dir):
        """Test parsing JSON results with ties."""
        round_dir = tmp_log_dir / "rounds" / "1"
        round_dir.mkdir(parents=True)

        self._create_json_sim_file(round_dir, 0, "Blue")
        self._create_json_sim_file(round_dir, 1, "Blue")
        self._create_json_sim_file(round_dir, 2, "Red")
        self._create_json_sim_file(round_dir, 3, "Red")
        self._create_json_sim_file(round_dir, 4, "Tie")

        agents = [MockPlayer("Alice"), MockPlayer("Bob")]
        stats = RoundStats(round_num=1, agents=agents)

        arena.get_results(agents, round_num=1, stats=stats)

        assert stats.winner == RESULT_TIE
        assert stats.scores["Alice"] == 2
        assert stats.scores["Bob"] == 2

    def test_parse_txt_results(self, arena, tmp_log_dir):
        """Test parsing TXT format results."""
        arena.sim_ext = "txt"
        round_dir = tmp_log_dir / "rounds" / "1"
        round_dir.mkdir(parents=True)

        self._create_txt_sim_file(round_dir, 0, "Blue won")
        self._create_txt_sim_file(round_dir, 1, "Blue won")
        self._create_txt_sim_file(round_dir, 2, "Red won")
        self._create_txt_sim_file(round_dir, 3, "it was a tie")
        self._create_txt_sim_file(round_dir, 4, "Blue won")

        agents = [MockPlayer("Alice"), MockPlayer("Bob")]
        stats = RoundStats(round_num=1, agents=agents)

        arena.get_results(agents, round_num=1, stats=stats)

        assert stats.winner == "Alice"
        assert stats.scores["Alice"] == 3
        assert stats.scores["Bob"] == 1


class TestRobotRumbleConfig:
    """Tests for RobotRumbleArena configuration and properties."""

    def test_arena_name(self):
        """Test that arena has correct name."""
        assert RobotRumbleArena.name == "RobotRumble"

    def test_submission_file(self):
        """Test that submission file is robot.js."""
        assert RobotRumbleArena.submission == "robot.js"

    def test_supported_extensions(self):
        """Test that both JS and Python are supported."""
        assert "js" in MAP_EXT_TO_HEADER
        assert "py" in MAP_EXT_TO_HEADER
        assert "function robot(state, unit) {" in MAP_EXT_TO_HEADER["js"]
        assert "def robot(state, unit):" in MAP_EXT_TO_HEADER["py"]
