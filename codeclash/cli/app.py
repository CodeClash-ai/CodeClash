"""Root `codeclash` Typer app.

Single entrypoint for CodeClash. Subcommands:
    codeclash run <config>            run a PvP tournament
    codeclash ladder make <config>    build a ladder (round-robin ranking)
    codeclash ladder run <config>     send a model up a ranked ladder
    codeclash rank {win-rate,elo,matrix} ...   compute standings from logs
    codeclash replay <log-folder>     browse/animate recorded games
"""

import getpass
import random
import time
import uuid
from pathlib import Path

import typer
import yaml

from codeclash import CONFIG_DIR
from codeclash.cli.ladder import ladder_app
from codeclash.cli.rank import rank_app
from codeclash.cli.replay import replay
from codeclash.constants import LOCAL_LOG_DIR
from codeclash.tournaments.pvp import PvpTournament
from codeclash.utils.aws import is_running_in_aws_batch
from codeclash.utils.yaml_utils import resolve_includes

app = typer.Typer(
    no_args_is_help=True,
    add_completion=False,
    rich_markup_mode="rich",  # enables the [dim] markup used in the Examples blocks
    context_settings={"help_option_names": ["-h", "--help"]},
    help="CodeClash: run coding-game tournaments, build ladders, and rank players.",
)
app.add_typer(ladder_app, name="ladder", help="Build and run CC:Ladder tournaments.")
app.add_typer(rank_app, name="rank", help="Compute player standings from game logs.")
app.command("replay")(replay)


@app.command()
def run(
    config_path: Path = typer.Argument(..., help="Path to the tournament config file."),
    cleanup: bool = typer.Option(False, "--cleanup", "-c", help="Clean up the game environment after running."),
    output_dir: Path | None = typer.Option(None, "--output-dir", "-o", help="Output directory (default: logs/<user>)."),
    suffix: str = typer.Option("", "--suffix", "-s", help="Suffix for the output folder name (no leading dot)."),
    keep_containers: bool = typer.Option(
        False, "--keep-containers", "-k", help="Do not remove containers after games/agent finish."
    ),
):
    """Run a PvP tournament from a config file.

    [dim]• codeclash run configs/test/battlesnake_pvp_test.yaml[/dim]
    [dim]• codeclash run path/to/config.yaml -c -o out/  # cleanup + custom output dir[/dim]
    """
    yaml_content = config_path.read_text()
    preprocessed_yaml = resolve_includes(yaml_content, base_dir=CONFIG_DIR)
    config = yaml.safe_load(preprocessed_yaml)

    def get_output_path() -> Path:
        if is_running_in_aws_batch():
            # Offset timestamp by random seconds to avoid collisions
            offset = random.randint(0, 600)
            timestamp = time.strftime("%y%m%d%H%M%S", time.localtime(time.time() + offset))
        else:
            timestamp = time.strftime("%y%m%d%H%M%S")
        rounds = config["tournament"]["rounds"]
        transparent = config["tournament"].get("transparent", False)
        sims = config["game"]["sims_per_round"]

        players = [p["name"] for p in config["players"]]
        p_num = len(players)
        p_list = ".".join(sorted(players))
        suffix_part = f".{suffix}" if suffix else ""
        folder_name = (
            f"PvpTournament.{config['game']['name']}.r{rounds}.s{sims}.p{p_num}.{p_list}{suffix_part}.{timestamp}"
        )
        if transparent:
            folder_name += ".transparent"
        if is_running_in_aws_batch():
            _uuid = str(uuid.uuid4())
            folder_name += f".{_uuid}-uuid"
        if output_dir is None:
            if is_running_in_aws_batch():
                return LOCAL_LOG_DIR / "batch" / folder_name
            else:
                return LOCAL_LOG_DIR / getpass.getuser() / folder_name
        else:
            return output_dir / folder_name

    full_output_dir = get_output_path()
    tournament = PvpTournament(config, output_dir=full_output_dir, cleanup=cleanup, keep_containers=keep_containers)
    tournament.run()


def main() -> None:
    """Console-script entrypoint (`codeclash`)."""
    app()


if __name__ == "__main__":
    app()
