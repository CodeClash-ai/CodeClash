"""
Integration test for main.py with BattleSnake configuration.

This test verifies that the main execution flow works without exceptions,
using DeterministicModel instead of real LLM models.
"""

from codeclash import CONFIG_DIR
from main import main_cli


def test_pvp_battlesnake():
    config_path = CONFIG_DIR / "test_configs" / "battlesnake_pvp_test.yaml"
    main_cli(["-c", str(config_path)])
