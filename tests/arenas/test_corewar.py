"""
Unit tests for CoreWarArena.

Tests validate_code() and get_results() methods without requiring Docker.
"""

import pytest

from codeclash.arenas.arena import RoundStats
from codeclash.arenas.corewar.corewar import COREWAR_LOG, CoreWarArena

from .conftest import MockPlayer

VALID_WARRIOR = """;redcode-94
;name Imp
;author A. K. Dewdney
;strategy A simple imp that marches through memory.

MOV 0, 1
"""


class TestCoreWarValidation:
    """Tests for CoreWarArena.validate_code()"""

    @pytest.fixture
    def arena(self, tmp_log_dir, minimal_config):
        """Create CoreWarArena instance with mocked environment."""
        arena = CoreWarArena.__new__(CoreWarArena)
        arena.submission = "warrior.red"
        arena.log_local = tmp_log_dir
        arena.run_cmd_round = "./src/pmars"
        return arena

    def test_valid_submission(self, arena, mock_player_factory):
        """Test that a valid warrior file passes validation."""
        player = mock_player_factory(
            name="test_player",
            files={"warrior.red": VALID_WARRIOR},
            command_outputs={
                "ls": {"output": "warrior.red\n", "returncode": 0},
                "./src/pmars warrior.red /home/dwarf.red": {
                    "output": "warrior.red by Imp scores 10\ndwarf.red by Dwarf scores 5",
                    "returncode": 0,
                },
            },
        )
        is_valid, error = arena.validate_code(player)
        assert is_valid is True
        assert error is None

    def test_missing_warrior_file(self, arena, mock_player_factory):
        """Test that missing warrior.red fails validation."""
        player = mock_player_factory(
            name="test_player",
            files={},
            command_outputs={
                "ls": {"output": "other.txt\n", "returncode": 0},
            },
        )
        is_valid, error = arena.validate_code(player)
        assert is_valid is False
        assert "warrior.red" in error

    def test_malformed_warrior_file(self, arena, mock_player_factory):
        """Test that malformed warrior file fails validation."""
        player = mock_player_factory(
            name="test_player",
            files={"warrior.red": "invalid redcode syntax"},
            command_outputs={
                "ls": {"output": "warrior.red\n", "returncode": 0},
                "./src/pmars warrior.red /home/dwarf.red": {
                    "output": "Error: Invalid instruction at line 1\n",
                    "returncode": 0,  # pmars returns 0 even on parse errors
                },
            },
        )
        is_valid, error = arena.validate_code(player)
        assert is_valid is False
        assert "malformed" in error.lower()


class TestCoreWarResults:
    """Tests for CoreWarArena.get_results()"""

    @pytest.fixture
    def arena(self, tmp_log_dir, minimal_config):
        """Create CoreWarArena instance."""
        config = minimal_config.copy()
        config["game"]["name"] = "CoreWar"
        config["game"]["sims_per_round"] = 100
        arena = CoreWarArena.__new__(CoreWarArena)
        arena.submission = "warrior.red"
        arena.log_local = tmp_log_dir
        arena.config = config
        arena.logger = type(
            "Logger",
            (),
            {
                "debug": lambda self, msg: None,
                "info": lambda self, msg: None,
                "error": lambda self, msg: None,
            },
        )()
        return arena

    def _create_sim_log(self, round_dir, scores: list[tuple[str, str, int]]):
        """
        Create simulation log files (one per agent).

        Args:
            round_dir: Directory to create log files in
            scores: List of (warrior_name, author, score) tuples
        """
        # Create one sim_{idx}.log file per agent to match new logging structure
        for idx in range(len(scores)):
            log_file = round_dir / COREWAR_LOG.format(idx=idx)
            # Rotate player order to match what _run_single_simulation does
            rotated_scores = scores[idx:] + scores[:idx]

            lines = []
            for warrior_name, author, score in rotated_scores:
                lines.append(f"{warrior_name} by {author} scores {score}\n")
            # Results line: wins for each player, then ties (always 0)
            wins = " ".join([str(score) for _, _, score in rotated_scores] + ["0"])
            lines.append(f"Results: {wins}\n")
            log_file.write_text("".join(lines))

    def test_parse_results_player1_wins(self, arena, tmp_log_dir):
        """Test parsing results when player 1 has higher score."""
        round_dir = tmp_log_dir / "rounds" / "1"
        round_dir.mkdir(parents=True)

        self._create_sim_log(
            round_dir,
            [
                ("alice_warrior.red", "Alice", 150),
                ("bob_warrior.red", "Bob", 100),
            ],
        )

        agents = [MockPlayer("Alice"), MockPlayer("Bob")]
        stats = RoundStats(round_num=1, agents=agents)

        arena.get_results(agents, round_num=1, stats=stats)

        assert stats.winner == "Alice"
        assert stats.scores["Alice"] == 300  # 150 per sim * 2 sims
        assert stats.scores["Bob"] == 200  # 100 per sim * 2 sims

    def test_parse_results_player2_wins(self, arena, tmp_log_dir):
        """Test parsing results when player 2 has higher score."""
        round_dir = tmp_log_dir / "rounds" / "1"
        round_dir.mkdir(parents=True)

        self._create_sim_log(
            round_dir,
            [
                ("alice_warrior.red", "Alice", 80),
                ("bob_warrior.red", "Bob", 200),
            ],
        )

        agents = [MockPlayer("Alice"), MockPlayer("Bob")]
        stats = RoundStats(round_num=1, agents=agents)

        arena.get_results(agents, round_num=1, stats=stats)

        assert stats.winner == "Bob"
        assert stats.scores["Alice"] == 160  # 80 per sim * 2 sims
        assert stats.scores["Bob"] == 400  # 200 per sim * 2 sims

    def test_parse_results_tie(self, arena, tmp_log_dir):
        """Test parsing results when scores are equal."""
        round_dir = tmp_log_dir / "rounds" / "1"
        round_dir.mkdir(parents=True)

        self._create_sim_log(
            round_dir,
            [
                ("alice_warrior.red", "Alice", 150),
                ("bob_warrior.red", "Bob", 150),
            ],
        )

        agents = [MockPlayer("Alice"), MockPlayer("Bob")]
        stats = RoundStats(round_num=1, agents=agents)

        arena.get_results(agents, round_num=1, stats=stats)

        # With equal wins, result is determined by score tiebreaker
        assert stats.scores["Alice"] == 300  # 150 per sim * 2 sims
        assert stats.scores["Bob"] == 300  # 150 per sim * 2 sims


class TestCoreWarConfig:
    """Tests for CoreWarArena configuration and properties."""

    def test_arena_name(self):
        """Test that arena has correct name."""
        assert CoreWarArena.name == "CoreWar"

    def test_submission_file(self):
        """Test that submission file is warrior.red."""
        assert CoreWarArena.submission == "warrior.red"

    def test_description_mentions_redcode(self):
        """Test that description mentions Redcode language."""
        assert "redcode" in CoreWarArena.description.lower()
