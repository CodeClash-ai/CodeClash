"""Unit tests for FiggieArena."""

import pytest

from codeclash.arenas.figgie.figgie import FiggieArena

VALID_FIGGIE_BOT = """
def get_action(state):
    '''Make a trading decision based on game state.'''
    hand = state.get('hand', {})
    offers = state.get('offers', {})
    bids = state.get('bids', {})
    position = state.get('position', 0)

    # Simple strategy: try to sell non-goal suits
    for suit in ['spades', 'clubs', 'hearts', 'diamonds']:
        bid = bids.get(suit)
        if bid and bid.get('player') != position and hand.get(suit, 0) > 0:
            return {'type': 'sell', 'suit': suit}

    return {'type': 'pass'}
"""


class TestFiggieValidation:
    """Tests for FiggieArena.validate_code()"""

    @pytest.fixture
    def arena(self, tmp_log_dir, minimal_config):
        """Create FiggieArena instance with mocked environment."""
        config = minimal_config.copy()
        config["game"]["name"] = "Figgie"
        config["players"] = [
            {"name": "p1", "agent": "dummy"},
            {"name": "p2", "agent": "dummy"},
            {"name": "p3", "agent": "dummy"},
            {"name": "p4", "agent": "dummy"},
        ]
        arena = FiggieArena.__new__(FiggieArena)
        arena.submission = "main.py"
        arena.log_local = tmp_log_dir
        return arena

    def test_valid_submission(self, arena, mock_player_factory):
        """Test that a valid Figgie bot passes validation."""
        player = mock_player_factory(
            name="test_player",
            files={"main.py": VALID_FIGGIE_BOT},
            command_outputs={
                "ls": {"output": "main.py\n", "returncode": 0},
                "cat main.py": {"output": VALID_FIGGIE_BOT, "returncode": 0},
            },
        )
        is_valid, error = arena.validate_code(player)
        assert is_valid is True
        assert error is None

    def test_missing_file(self, arena, mock_player_factory):
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

    def test_missing_get_action_function(self, arena, mock_player_factory):
        """Test that missing get_action function fails validation."""
        bot_code = """
def make_move(game_state):
    '''Wrong function name.'''
    return {'type': 'pass'}
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
        assert "get_action" in error


class TestFiggieRequirements:
    """Test Figgie-specific requirements."""

    def test_rejects_invalid_player_count(self, minimal_config, tmp_log_dir):
        """Test that Figgie rejects invalid player counts (not 4 or 5)."""
        config = minimal_config.copy()
        config["game"]["name"] = "Figgie"
        config["players"] = [
            {"name": "p1", "agent": "dummy"},
            {"name": "p2", "agent": "dummy"},
        ]

        with pytest.raises(ValueError, match="Figgie requires 4 or 5 players"):
            FiggieArena(config, tournament_id="test_tournament", local_output_dir=tmp_log_dir)

    def test_rejects_6_players(self, minimal_config, tmp_log_dir):
        """Test that Figgie rejects 6 players."""
        config = minimal_config.copy()
        config["game"]["name"] = "Figgie"
        config["players"] = [{"name": f"p{i}", "agent": "dummy"} for i in range(6)]

        with pytest.raises(ValueError, match="Figgie requires 4 or 5 players"):
            FiggieArena(config, tournament_id="test_tournament", local_output_dir=tmp_log_dir)

    def test_accepts_4_or_5_players(self):
        """Test that Figgie accepts 4 or 5 players by checking class properties."""
        assert FiggieArena.name == "Figgie"
        assert FiggieArena.submission == "main.py"
        # Description should mention both 4 and 5 players
        assert "4 or 5 players" in FiggieArena.description
