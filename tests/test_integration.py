"""
Integration test for main.py with BattleSnake configuration.

This test verifies that the main execution flow works without exceptions,
using DeterministicModel instead of real LLM models.
"""

from codeclash import CONFIG_DIR


def test_pvp_battlesnake():
    from typer.testing import CliRunner

    from codeclash.cli.app import app

    config_path = CONFIG_DIR / "test" / "battlesnake_pvp_test.yaml"
    result = CliRunner().invoke(app, ["run", "-c", str(config_path)])
    assert result.exit_code == 0, result.output


def test_single_player_battlesnake():
    from scripts.main_single_player import main_cli

    config_path = CONFIG_DIR / "test" / "battlesnake_single_player_test.yaml"
    main_cli(["-c", str(config_path)])
