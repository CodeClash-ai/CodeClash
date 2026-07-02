"""`codeclash ladder` subcommands: build a ladder (make) and climb it (run)."""

import getpass
import time
from pathlib import Path
from typing import Optional

import typer
import yaml

from codeclash import CONFIG_DIR
from codeclash.constants import LOCAL_LOG_DIR
from codeclash.tournaments.pvp import PvpTournament
from codeclash.utils.yaml_utils import resolve_includes

ladder_app = typer.Typer(
    no_args_is_help=True, add_completion=False, context_settings={"help_option_names": ["-h", "--help"]}
)


@ladder_app.command("make")
def make(
    config_path: Path = typer.Argument(..., help="Path to the ladder (round-robin) config file."),
):
    """Build a ladder: run PvP tournaments across all pairs of players (for ranking)."""
    yaml_content = config_path.read_text()
    preprocessed_yaml = resolve_includes(yaml_content, base_dir=CONFIG_DIR)
    config = yaml.safe_load(preprocessed_yaml)

    players = config["players"]
    num_players = len(players)
    for i in range(num_players):
        for j in range(i + 1, num_players):
            player1 = players[i]
            player1["name"] = player1["branch_init"]
            player2 = players[j]
            player2["name"] = player2["branch_init"]
            pvp_config = {
                **config,
                "players": [player1, player2],
            }

            vs = f"PvpTournament.{player1['name']}_vs_{player2['name']}".replace("/", "_")
            output_dir = LOCAL_LOG_DIR / "ladder" / config["game"]["name"] / vs
            try:
                tournament = PvpTournament(pvp_config, output_dir=output_dir)
            except FileExistsError:
                continue
            tournament.run()


@ladder_app.command("run")
def run(
    config_path: Path = typer.Argument(..., help="Path to the ladder config (with `player` + `ladder`)."),
    cleanup: bool = typer.Option(False, "--cleanup", "-c", help="Clean up the game environment after running."),
    output_dir: Optional[Path] = typer.Option(
        None, "--output-dir", "-o", help="Output directory (default: logs/<user>)."
    ),
    suffix: str = typer.Option("", "--suffix", "-s", help="Suffix for the output folder name (no leading dot)."),
    keep_containers: bool = typer.Option(
        False, "--keep-containers", "-k", help="Do not remove containers after games/agent finish."
    ),
):
    """Send a model up a ranked ladder, rung by rung, until it loses."""
    yaml_content = config_path.read_text()
    preprocessed_yaml = resolve_includes(yaml_content, base_dir=CONFIG_DIR)
    config = yaml.safe_load(preprocessed_yaml)
    ladder, player, rounds, sims = (
        config["ladder"],
        config["player"],
        config["tournament"]["rounds"],
        config["game"]["sims_per_round"],
    )
    timestamp = time.strftime("%y%m%d%H%M%S")
    del config["player"]
    del config["ladder"]
    ladder_folder = f"LadderTournament.{config['game']['name']}.r{rounds}.s{sims}.{timestamp}"
    player["branch"] = ladder_folder
    parent_dir = LOCAL_LOG_DIR / getpass.getuser() / ladder_folder

    for idx, opponent in enumerate(ladder):
        opponent_rank = len(ladder) - idx
        opponent["name"] = opponent["branch_init"].replace("human/", "").replace("/", "_")
        if "branch_init" in player and idx > 0:
            # After first opponent, remove branch_init so that player continues from previous tournament's codebase
            del player["branch_init"]
        c = {
            **config,
            "players": [
                player,
                opponent,
            ],
        }

        players = [p["name"] for p in c["players"]]
        p_num = len(players)
        p_list = ".".join(players)
        suffix_part = f".{suffix}" if suffix else ""
        folder_name = f"PvpTournament.{c['game']['name']}.r{rounds}.s{sims}.p{p_num}.{p_list}{suffix_part}"

        tournament_dir = parent_dir / folder_name if output_dir is None else output_dir / folder_name
        tournament = PvpTournament(
            c,
            output_dir=tournament_dir,
            cleanup=cleanup,
            keep_containers=keep_containers,
        )
        tournament.run()

        # Get results
        metadata_path = tournament_dir / "metadata.json"
        with open(metadata_path) as f:
            metadata = yaml.safe_load(f)
        round_winners = [r["winner"] for r in metadata["round_stats"].values()]

        # Player must have won majority of rounds and the last round to continue ladder
        player_wins = sum(1 for w in round_winners if w == player["name"])
        player_won_last = round_winners[-1] == player["name"]

        if not player_wins > len(round_winners) // 2 or not player_won_last:
            # If player lost tournament, ladder challenge ends
            break

        print("=" * 10)
        print(
            f"{player['name']} successfully beat {opponent['name']} (rank {opponent_rank}/{len(ladder)}) "
            f"in {player_wins}/{len(round_winners)} rounds.\n"
            "Ladder challenge continuing"
        )
        print("=" * 10)

    print(f"Ladder tournament complete. Logs saved to {parent_dir}")
    print(f"Final opponent faced: {opponent['name']} (rank {opponent_rank}/{len(ladder)} in ladder)")
