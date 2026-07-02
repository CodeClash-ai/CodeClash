"""`codeclash rank` subcommands: compute player standings from game logs."""

import subprocess
import sys
from pathlib import Path

import typer

from codeclash.analysis import matrix as matrix_mod
from codeclash.analysis.metrics import win_rate as win_rate_mod
from codeclash.constants import LOCAL_LOG_DIR

rank_app = typer.Typer(
    no_args_is_help=True, add_completion=False, context_settings={"help_option_names": ["-h", "--help"]}
)


@rank_app.command("win-rate")
def win_rate(
    logs: Path = typer.Argument(LOCAL_LOG_DIR, help="Path to game logs (default: logs/)."),
):
    """Print per-game and game-agnostic win rates for each model."""
    win_rate_mod.main(logs)


@rank_app.command("matrix")
def matrix(
    pvp_output_dir: Path = typer.Argument(..., help="Path to a PvP tournament output directory."),
    repetitions: int = typer.Option(3, "--repetitions", "-n", help="Repetitions per matchup."),
    max_workers: int = typer.Option(4, "--max-workers", "-w", help="Number of parallel game workers."),
):
    """Evaluate PvP tournament matrices (head-to-head win matrix)."""
    matrix_mod.main(pvp_output_dir, n_repetitions=repetitions, max_workers=max_workers)


@rank_app.command(
    "elo",
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
    help=(
        "Fit a Bradley-Terry/Elo model and generate plots. Forwards all arguments to the elo "
        "analysis module, e.g.:  codeclash rank elo -d logs/ --print-matrix --output-dir assets/elo_plots"
    ),
)
def elo(ctx: typer.Context):
    """Passthrough to `python -m codeclash.analysis.metrics.elo` (rich analysis + plots)."""
    raise SystemExit(subprocess.run([sys.executable, "-m", "codeclash.analysis.metrics.elo", *ctx.args]).returncode)
