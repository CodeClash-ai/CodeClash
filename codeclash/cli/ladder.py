"""`codeclash ladder` subcommands: build a ladder (make) and climb it (run).

Thin CLI adapter over :mod:`codeclash.tournaments.ladder`, which holds all ladder logic.
"""

from pathlib import Path

import typer
import yaml

from codeclash import CONFIG_DIR
from codeclash.tournaments.ladder import LadderTournament, build_ladder, resolve_ladder_rules  # noqa: F401
from codeclash.utils.yaml_utils import resolve_includes

ladder_app = typer.Typer(
    no_args_is_help=True,
    add_completion=False,
    rich_markup_mode="rich",  # enables the [dim] markup used in the Examples blocks
    context_settings={"help_option_names": ["-h", "--help"]},
)


def _load_config(config_path: Path) -> dict:
    yaml_content = config_path.read_text()
    preprocessed_yaml = resolve_includes(yaml_content, base_dir=CONFIG_DIR)
    return yaml.safe_load(preprocessed_yaml)


@ladder_app.command("make")
def make(
    config_path: Path = typer.Argument(..., help="Path to the ladder (round-robin) config file."),
    workers: int = typer.Option(
        1, "--workers", "-w", help="Pairwise tournaments to run concurrently (each pair is independent)."
    ),
):
    """Build a ladder: run PvP tournaments across all pairs of players (for ranking).

    [dim]• codeclash ladder make configs/ladder/make_battlesnake.yaml[/dim]
    """
    build_ladder(_load_config(config_path), workers=workers)


@ladder_app.command("run")
def run(
    config_path: Path = typer.Argument(..., help="Path to the ladder config (with `player` + `ladder`)."),
    cleanup: bool = typer.Option(False, "--cleanup", "-c", help="Clean up the game environment after running."),
    output_dir: Path | None = typer.Option(None, "--output-dir", "-o", help="Output directory (default: logs/<user>)."),
    suffix: str = typer.Option("", "--suffix", "-s", help="Suffix for the output folder name (no leading dot)."),
    keep_containers: bool = typer.Option(
        False, "--keep-containers", "-k", help="Do not remove containers after games/agent finish."
    ),
):
    """Send a model up a ranked ladder, rung by rung, until it loses.

    [dim]• codeclash ladder run path/to/ladder_config.yaml -c  # clean up after each rung[/dim]
    """
    config = _load_config(config_path)
    try:
        tournament = LadderTournament(
            config,
            output_dir=output_dir,
            suffix=suffix,
            cleanup=cleanup,
            keep_containers=keep_containers,
        )
    except ValueError as e:
        typer.echo(str(e))
        raise typer.Exit(1)
    tournament.run()
