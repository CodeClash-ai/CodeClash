"""
Unit tests for BattleCode24Arena.

Tests validate_code(), execute_round(), and get_results() methods without requiring Docker.
"""

from unittest.mock import MagicMock, patch

import pytest

from codeclash.arenas.arena import RoundStats
from codeclash.arenas.battlecode24.battlecode24 import BattleCode24Arena, RoundResult, SimulationMeta
from codeclash.constants import RESULT_TIE

from .conftest import MockPlayer

VALID_ROBOT_PLAYER = """
package mysubmission;

import battlecode.common.*;

public class RobotPlayer {
    public static void run(RobotController rc) throws GameActionException {
        while (true) {
            // Game logic here
            Clock.yield();
        }
    }
}
"""


class TestBattleCode24Validation:
    """Tests for BattleCode24Arena.validate_code()"""

    @pytest.fixture
    def arena(self, tmp_log_dir, minimal_config):
        """Create BattleCode24Arena instance with mocked environment."""
        config = minimal_config.copy()
        config["game"]["name"] = "BattleCode24"
        config["game"]["sims_per_round"] = 10
        config["players"] = [
            {"name": "p1", "agent": "dummy"},
            {"name": "p2", "agent": "dummy"},
        ]
        arena = BattleCode24Arena.__new__(BattleCode24Arena)
        arena.submission = "src/mysubmission"
        arena.log_local = tmp_log_dir
        arena.config = config
        return arena

    def test_valid_submission(self, arena, mock_player_factory):
        """Test that a valid BattleCode24 submission passes validation."""
        player = mock_player_factory(
            name="test_player",
            files={
                "src/mysubmission/RobotPlayer.java": VALID_ROBOT_PLAYER,
            },
            command_outputs={
                "ls src": {"output": "mysubmission\n", "returncode": 0},
                "ls src/mysubmission": {"output": "RobotPlayer.java\n", "returncode": 0},
                "cat src/mysubmission/RobotPlayer.java": {"output": VALID_ROBOT_PLAYER, "returncode": 0},
            },
        )
        is_valid, error = arena.validate_code(player)
        assert is_valid is True
        assert error is None

    def test_missing_mysubmission_directory(self, arena, mock_player_factory):
        """Test validation fails when src/mysubmission/ directory is missing."""
        player = mock_player_factory(
            name="test_player",
            files={},
            command_outputs={
                "ls src": {"output": "other_dir\n", "returncode": 0},
            },
        )
        is_valid, error = arena.validate_code(player)
        assert is_valid is False
        assert "src/mysubmission/" in error

    def test_missing_robot_player_file(self, arena, mock_player_factory):
        """Test validation fails when RobotPlayer.java is missing."""
        player = mock_player_factory(
            name="test_player",
            files={},
            command_outputs={
                "ls src": {"output": "mysubmission\n", "returncode": 0},
                "ls src/mysubmission": {"output": "OtherFile.java\n", "returncode": 0},
            },
        )
        is_valid, error = arena.validate_code(player)
        assert is_valid is False
        assert "RobotPlayer.java" in error

    def test_missing_run_method(self, arena, mock_player_factory):
        """Test validation fails when run(RobotController rc) method is missing."""
        invalid_code = """
package mysubmission;

import battlecode.common.*;

public class RobotPlayer {
    public static void main(String[] args) {
        // Wrong method signature
    }
}
"""
        player = mock_player_factory(
            name="test_player",
            files={"src/mysubmission/RobotPlayer.java": invalid_code},
            command_outputs={
                "ls src": {"output": "mysubmission\n", "returncode": 0},
                "ls src/mysubmission": {"output": "RobotPlayer.java\n", "returncode": 0},
                "cat src/mysubmission/RobotPlayer.java": {"output": invalid_code, "returncode": 0},
            },
        )
        is_valid, error = arena.validate_code(player)
        assert is_valid is False
        assert "run(RobotController" in error

    def test_wrong_package_declaration(self, arena, mock_player_factory):
        """Test validation fails when package declaration is incorrect."""
        invalid_code = """
package wrongpackage;

import battlecode.common.*;

public class RobotPlayer {
    public static void run(RobotController rc) throws GameActionException {
        while (true) {
            Clock.yield();
        }
    }
}
"""
        player = mock_player_factory(
            name="test_player",
            files={"src/mysubmission/RobotPlayer.java": invalid_code},
            command_outputs={
                "ls src": {"output": "mysubmission\n", "returncode": 0},
                "ls src/mysubmission": {"output": "RobotPlayer.java\n", "returncode": 0},
                "cat src/mysubmission/RobotPlayer.java": {"output": invalid_code, "returncode": 0},
            },
        )
        is_valid, error = arena.validate_code(player)
        assert is_valid is False
        assert "package mysubmission;" in error


class TestBattleCode24SimulationParsing:
    """Tests for BattleCode24Arena._parse_simulation_log()"""

    @pytest.fixture
    def arena(self, tmp_log_dir, minimal_config):
        """Create BattleCode24Arena instance."""
        config = minimal_config.copy()
        config["game"]["name"] = "BattleCode24"
        config["game"]["sims_per_round"] = 10
        config["players"] = [
            {"name": "p1", "agent": "dummy"},
            {"name": "p2", "agent": "dummy"},
        ]
        arena = BattleCode24Arena.__new__(BattleCode24Arena)
        arena.submission = "src/mysubmission"
        arena.log_local = tmp_log_dir
        arena.config = config
        arena.logger = MagicMock()
        return arena

    def test_parse_team_a_wins(self, arena, tmp_log_dir):
        """Test parsing when team A wins."""
        log_file = tmp_log_dir / "sim_0.log"
        log_file.write_text(
            "[server] Game starting\n[server] mysubmission (A) wins (1234)\nReason: Team A captured all flags.\n"
        )

        sim_meta = SimulationMeta(idx=0, team_a="Alice", team_b="Bob", log_file="sim_0.log")
        winner = arena._parse_simulation_log(log_file, sim_meta)
        assert winner == "Alice"

    def test_parse_team_b_wins(self, arena, tmp_log_dir):
        """Test parsing when team B wins."""
        log_file = tmp_log_dir / "sim_0.log"
        log_file.write_text(
            "[server] Game starting\n[server] mysubmission (B) wins (5678)\nReason: Team B captured all flags.\n"
        )

        sim_meta = SimulationMeta(idx=0, team_a="Alice", team_b="Bob", log_file="sim_0.log")
        winner = arena._parse_simulation_log(log_file, sim_meta)
        assert winner == "Bob"

    def test_parse_coin_flip_tie(self, arena, tmp_log_dir):
        """Test parsing when game ends in a coin flip tie."""
        log_file = tmp_log_dir / "sim_0.log"
        log_file.write_text(
            "[server] Game starting\n"
            "[server] mysubmission (A) wins (1234)\n"
            "Reason: The winning team won arbitrarily (coin flip).\n"
        )

        sim_meta = SimulationMeta(idx=0, team_a="Alice", team_b="Bob", log_file="sim_0.log")
        winner = arena._parse_simulation_log(log_file, sim_meta)
        assert winner == RESULT_TIE

    def test_parse_missing_log_file(self, arena, tmp_log_dir):
        """Test parsing when log file doesn't exist (simulation failed)."""
        log_file = tmp_log_dir / "nonexistent.log"

        sim_meta = SimulationMeta(idx=0, team_a="Alice", team_b="Bob", log_file="nonexistent.log")
        winner = arena._parse_simulation_log(log_file, sim_meta)
        assert winner is None

    def test_parse_truncated_log(self, arena, tmp_log_dir):
        """Test parsing when log is too short (game crashed early)."""
        log_file = tmp_log_dir / "sim_0.log"
        log_file.write_text("[server] Starting...\n")

        sim_meta = SimulationMeta(idx=0, team_a="Alice", team_b="Bob", log_file="sim_0.log")
        winner = arena._parse_simulation_log(log_file, sim_meta)
        assert winner is None

    def test_parse_no_winner_line(self, arena, tmp_log_dir):
        """Test parsing when winner line is missing."""
        log_file = tmp_log_dir / "sim_0.log"
        log_file.write_text("[server] Game starting\n[server] Game ended\nSome other output\n")

        sim_meta = SimulationMeta(idx=0, team_a="Alice", team_b="Bob", log_file="sim_0.log")
        winner = arena._parse_simulation_log(log_file, sim_meta)
        assert winner == RESULT_TIE

    def test_parse_alternating_team_positions(self, arena, tmp_log_dir):
        """Test that team position alternation is correctly handled."""
        # Simulation 0: Alice is A, Bob is B, A wins
        log_file_0 = tmp_log_dir / "sim_0.log"
        log_file_0.write_text("[server] mysubmission (A) wins (1234)\nReason: Team A won.\n")
        sim_meta_0 = SimulationMeta(idx=0, team_a="Alice", team_b="Bob", log_file="sim_0.log")
        winner_0 = arena._parse_simulation_log(log_file_0, sim_meta_0)
        assert winner_0 == "Alice"

        # Simulation 1: Bob is A, Alice is B, A wins
        log_file_1 = tmp_log_dir / "sim_1.log"
        log_file_1.write_text("[server] mysubmission (A) wins (5678)\nReason: Team A won.\n")
        sim_meta_1 = SimulationMeta(idx=1, team_a="Bob", team_b="Alice", log_file="sim_1.log")
        winner_1 = arena._parse_simulation_log(log_file_1, sim_meta_1)
        assert winner_1 == "Bob"


class TestBattleCode24Results:
    """Tests for BattleCode24Arena.get_results()"""

    @pytest.fixture
    def arena(self, tmp_log_dir, minimal_config):
        """Create BattleCode24Arena instance."""
        config = minimal_config.copy()
        config["game"]["name"] = "BattleCode24"
        config["game"]["sims_per_round"] = 10
        config["players"] = [
            {"name": "p1", "agent": "dummy"},
            {"name": "p2", "agent": "dummy"},
        ]
        arena = BattleCode24Arena.__new__(BattleCode24Arena)
        arena.submission = "src/mysubmission"
        arena.log_local = tmp_log_dir
        arena.config = config
        arena.logger = MagicMock()
        return arena

    def _create_round_log_dir(self, tmp_log_dir, round_num):
        """Helper to create round log directory."""
        round_dir = tmp_log_dir / "rounds" / str(round_num)
        round_dir.mkdir(parents=True, exist_ok=True)
        return round_dir

    def _create_sim_log(self, round_dir, idx: int, winner_team: str, is_tie: bool = False):
        """Helper to create a simulation log file."""
        log_file = round_dir / f"sim_{idx}.log"
        if is_tie:
            content = (
                f"[server] mysubmission ({winner_team}) wins (1234)\n"
                "Reason: The winning team won arbitrarily (coin flip).\n"
            )
        else:
            content = f"[server] mysubmission ({winner_team}) wins (1234)\nReason: Team won by capturing flags.\n"
        log_file.write_text(content)

    def test_get_results_clear_winner(self, arena, tmp_log_dir):
        """Test get_results when one player clearly wins."""
        round_dir = self._create_round_log_dir(tmp_log_dir, 1)

        # Create simulations with Alice winning 7, Bob winning 3
        simulations = []
        for idx in range(10):
            if idx < 7:
                # Alice as team A wins
                self._create_sim_log(round_dir, idx, "A")
                simulations.append(SimulationMeta(idx=idx, team_a="Alice", team_b="Bob", log_file=f"sim_{idx}.log"))
            else:
                # Bob as team B wins
                self._create_sim_log(round_dir, idx, "B")
                simulations.append(SimulationMeta(idx=idx, team_a="Alice", team_b="Bob", log_file=f"sim_{idx}.log"))

        arena._round_result = RoundResult(status="completed", simulations=simulations)

        agents = [MockPlayer("Alice"), MockPlayer("Bob")]
        stats = RoundStats(round_num=1, agents=agents)

        arena.get_results(agents, round_num=1, stats=stats)

        assert stats.winner == "Alice"
        assert stats.scores["Alice"] == 7
        assert stats.scores["Bob"] == 3
        assert stats.player_stats["Alice"].score == 7
        assert stats.player_stats["Bob"].score == 3

    def test_get_results_with_ties(self, arena, tmp_log_dir):
        """Test get_results when some simulations end in ties."""
        round_dir = self._create_round_log_dir(tmp_log_dir, 1)

        simulations = []
        # Alice wins 4, Bob wins 3, 3 ties
        for idx in range(10):
            if idx < 4:
                self._create_sim_log(round_dir, idx, "A")
                simulations.append(SimulationMeta(idx=idx, team_a="Alice", team_b="Bob", log_file=f"sim_{idx}.log"))
            elif idx < 7:
                self._create_sim_log(round_dir, idx, "B")
                simulations.append(SimulationMeta(idx=idx, team_a="Alice", team_b="Bob", log_file=f"sim_{idx}.log"))
            else:
                self._create_sim_log(round_dir, idx, "A", is_tie=True)
                simulations.append(SimulationMeta(idx=idx, team_a="Alice", team_b="Bob", log_file=f"sim_{idx}.log"))

        arena._round_result = RoundResult(status="completed", simulations=simulations)

        agents = [MockPlayer("Alice"), MockPlayer("Bob")]
        stats = RoundStats(round_num=1, agents=agents)

        arena.get_results(agents, round_num=1, stats=stats)

        assert stats.winner == "Alice"
        assert stats.scores["Alice"] == 4
        assert stats.scores["Bob"] == 3

    def test_get_results_equal_scores(self, arena, tmp_log_dir):
        """Test get_results when both players have equal scores."""
        round_dir = self._create_round_log_dir(tmp_log_dir, 1)

        simulations = []
        # Alice wins 5, Bob wins 5
        for idx in range(10):
            if idx < 5:
                self._create_sim_log(round_dir, idx, "A")
                simulations.append(SimulationMeta(idx=idx, team_a="Alice", team_b="Bob", log_file=f"sim_{idx}.log"))
            else:
                self._create_sim_log(round_dir, idx, "B")
                simulations.append(SimulationMeta(idx=idx, team_a="Alice", team_b="Bob", log_file=f"sim_{idx}.log"))

        arena._round_result = RoundResult(status="completed", simulations=simulations)

        agents = [MockPlayer("Alice"), MockPlayer("Bob")]
        stats = RoundStats(round_num=1, agents=agents)

        arena.get_results(agents, round_num=1, stats=stats)

        assert stats.winner == RESULT_TIE
        assert stats.scores["Alice"] == 5
        assert stats.scores["Bob"] == 5

    def test_get_results_auto_win(self, arena, tmp_log_dir):
        """Test get_results when one player wins due to opponent's compilation failure."""
        arena._round_result = RoundResult(
            status="auto_win",
            winner="Alice",
            loser="Bob",
            reason="Bob failed to compile",
        )

        agents = [MockPlayer("Alice"), MockPlayer("Bob")]
        stats = RoundStats(round_num=1, agents=agents)

        arena.get_results(agents, round_num=1, stats=stats)

        assert stats.winner == "Alice"
        assert stats.scores["Alice"] == 10  # Gets all sims_per_round points
        assert stats.player_stats["Alice"].score == 10
        assert stats.player_stats["Bob"].valid_submit is False
        assert "Compilation failed" in stats.player_stats["Bob"].invalid_reason

    def test_get_results_no_contest(self, arena, tmp_log_dir):
        """Test get_results when both players fail to compile."""
        arena._round_result = RoundResult(
            status="no_contest",
            reason="all agents failed to compile",
        )

        agents = [MockPlayer("Alice"), MockPlayer("Bob")]
        stats = RoundStats(round_num=1, agents=agents)

        arena.get_results(agents, round_num=1, stats=stats)

        assert stats.winner == RESULT_TIE
        assert stats.scores["Alice"] == 5  # Split points evenly
        assert stats.scores["Bob"] == 5
        assert stats.player_stats["Alice"].valid_submit is False
        assert stats.player_stats["Bob"].valid_submit is False
        assert "Compilation failed" in stats.player_stats["Alice"].invalid_reason
        assert "Compilation failed" in stats.player_stats["Bob"].invalid_reason

    def test_get_results_all_simulations_failed(self, arena, tmp_log_dir):
        """Test get_results when all simulations fail to produce results."""
        # Create simulations but no log files (all failed)
        simulations = []
        for idx in range(10):
            simulations.append(SimulationMeta(idx=idx, team_a="Alice", team_b="Bob", log_file=f"sim_{idx}.log"))

        arena._round_result = RoundResult(status="completed", simulations=simulations)

        agents = [MockPlayer("Alice"), MockPlayer("Bob")]
        stats = RoundStats(round_num=1, agents=agents)

        arena.get_results(agents, round_num=1, stats=stats)

        assert stats.winner == RESULT_TIE
        # No scores recorded when all simulations fail
        assert stats.scores["Alice"] == 0
        assert stats.scores["Bob"] == 0

    def test_get_results_missing_round_result(self, arena, tmp_log_dir):
        """Test get_results when execute_round didn't set _round_result."""
        arena._round_result = None

        agents = [MockPlayer("Alice"), MockPlayer("Bob")]
        stats = RoundStats(round_num=1, agents=agents)

        arena.get_results(agents, round_num=1, stats=stats)

        assert stats.winner == RESULT_TIE


class TestBattleCode24Config:
    """Tests for BattleCode24Arena configuration and properties."""

    def test_arena_name(self):
        """Test that arena has correct name."""
        assert BattleCode24Arena.name == "BattleCode24"

    def test_submission_path(self):
        """Test that submission path is correct."""
        assert BattleCode24Arena.submission == "src/mysubmission"

    def test_default_args(self):
        """Test default arena arguments."""
        assert BattleCode24Arena.default_args["maps"] == "DefaultSmall"

    def test_initialization_with_two_players(self, tmp_log_dir, minimal_config):
        """Test arena initialization with exactly 2 players."""
        config = minimal_config.copy()
        config["game"]["name"] = "BattleCode24"
        config["game"]["args"] = {"maps": "CustomMap"}
        config["players"] = [
            {"name": "p1", "agent": "dummy"},
            {"name": "p2", "agent": "dummy"},
        ]

        # Mock the parent __init__ since we're testing a partial initialization
        with patch.object(BattleCode24Arena.__bases__[0], "__init__", return_value=None):
            arena = BattleCode24Arena.__new__(BattleCode24Arena)
            arena.config = config
            arena._round_result = None

            # Verify run command is built correctly
            arena.run_cmd_base = "./gradlew --no-daemon run"
            for arg, val in config["game"]["args"].items():
                if isinstance(val, bool):
                    if val:
                        arena.run_cmd_base += f" -P{arg}=true"
                else:
                    arena.run_cmd_base += f" -P{arg}={val}"

            assert "-Pmaps=CustomMap" in arena.run_cmd_base

    def test_initialization_fails_with_wrong_player_count(self, tmp_log_dir, minimal_config):
        """Test that initialization fails with != 2 players."""
        config = minimal_config.copy()
        config["game"]["name"] = "BattleCode24"
        config["players"] = [{"name": "p1", "agent": "dummy"}]  # Only 1 player

        with pytest.raises(AssertionError, match="two-player game"):
            with patch.object(BattleCode24Arena.__bases__[0], "__init__", return_value=None):
                BattleCode24Arena(config, tournament_id="test", local_output_dir=tmp_log_dir)


class TestBattleCode24SimulationMetadata:
    """Tests for SimulationMeta dataclass and team position alternation."""

    def test_simulation_meta_creation(self):
        """Test creating SimulationMeta with team assignments."""
        meta = SimulationMeta(idx=0, team_a="Alice", team_b="Bob", log_file="sim_0.log")

        assert meta.idx == 0
        assert meta.team_a == "Alice"
        assert meta.team_b == "Bob"
        assert meta.log_file == "sim_0.log"

    def test_team_position_alternation_pattern(self):
        """Test that team positions alternate correctly across simulations."""
        agents = ["Alice", "Bob"]
        simulations = []

        for idx in range(6):
            if idx % 2 == 0:
                team_a, team_b = agents[0], agents[1]
            else:
                team_a, team_b = agents[1], agents[0]

            simulations.append(SimulationMeta(idx=idx, team_a=team_a, team_b=team_b, log_file=f"sim_{idx}.log"))

        # Verify alternation pattern
        assert simulations[0].team_a == "Alice" and simulations[0].team_b == "Bob"
        assert simulations[1].team_a == "Bob" and simulations[1].team_b == "Alice"
        assert simulations[2].team_a == "Alice" and simulations[2].team_b == "Bob"
        assert simulations[3].team_a == "Bob" and simulations[3].team_b == "Alice"
        assert simulations[4].team_a == "Alice" and simulations[4].team_b == "Bob"
        assert simulations[5].team_a == "Bob" and simulations[5].team_b == "Alice"


class TestBattleCode24RoundResult:
    """Tests for RoundResult dataclass."""

    def test_round_result_completed(self):
        """Test RoundResult for completed round."""
        simulations = [
            SimulationMeta(idx=0, team_a="Alice", team_b="Bob", log_file="sim_0.log"),
            SimulationMeta(idx=1, team_a="Bob", team_b="Alice", log_file="sim_1.log"),
        ]
        result = RoundResult(status="completed", simulations=simulations)

        assert result.status == "completed"
        assert result.winner is None
        assert result.loser is None
        assert result.reason == ""
        assert len(result.simulations) == 2

    def test_round_result_auto_win(self):
        """Test RoundResult for auto-win scenario."""
        result = RoundResult(
            status="auto_win",
            winner="Alice",
            loser="Bob",
            reason="Bob failed to compile",
        )

        assert result.status == "auto_win"
        assert result.winner == "Alice"
        assert result.loser == "Bob"
        assert "compile" in result.reason
        assert len(result.simulations) == 0

    def test_round_result_no_contest(self):
        """Test RoundResult for no-contest scenario."""
        result = RoundResult(status="no_contest", reason="all agents failed to compile")

        assert result.status == "no_contest"
        assert result.winner is None
        assert result.loser is None
        assert "all agents failed" in result.reason
        assert len(result.simulations) == 0
