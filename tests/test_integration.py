"""
Integration test for main.py with BattleSnake configuration.

This test verifies that the main execution flow works without exceptions,
using DeterministicModel instead of real LLM models.
"""

from codeclash import CONFIG_DIR


def test_pvp_battlesnake():
    from main import main_cli

    config_path = CONFIG_DIR / "test" / "battlesnake_pvp_test.yaml"
    main_cli(["-c", str(config_path)])


def test_single_player_battlesnake():
    from main_single_player import main_cli

    config_path = CONFIG_DIR / "test" / "battlesnake_single_player_test.yaml"
    main_cli(["-c", str(config_path)])
