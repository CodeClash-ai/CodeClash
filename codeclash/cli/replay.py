"""`codeclash replay` — serve a tournament folder and watch game replays in the browser.

Points at a tournament folder (the one holding ``metadata.json`` + ``rounds/``); the arena
is read from the metadata (or the folder name). Games are discovered under ``rounds/``
(including ``round_<R>.tar.gz`` archives) and each replay is rendered on demand — nothing
is written to disk.
"""

from __future__ import annotations

from pathlib import Path

import typer

from codeclash.replay import get_replayer, load_tournament
from codeclash.replay.serve import run_server


def replay(
    folder: Path = typer.Argument(..., help="Tournament log folder (contains metadata.json + rounds/)."),
    port: int = typer.Option(8000, "--port", "-p", help="Port to serve on (falls back to a free one if taken)."),
):
    """Serve a tournament folder and lazily watch game replays in the browser.

    [dim]• codeclash replay logs/<tournament-folder>[/dim]
    [dim]• codeclash replay logs/<folder> -p 9000[/dim]
    """
    tour = load_tournament(folder)
    renderer = get_replayer(tour.arena)
    if renderer is None:
        typer.echo(f"No replayer for {tour.arena or 'this arena'} yet.")
        raise typer.Exit(1)
    if not tour.games:
        typer.echo(f"No sim files found under {folder} (looked for {renderer.sim_glob}).")
        raise typer.Exit(1)
    run_server(folder, tour, renderer, port=port)
