import argparse
import getpass
import time
from pathlib import Path

import yaml

from codeclash import CONFIG_DIR
from codeclash.constants import LOCAL_LOG_DIR
from codeclash.tournaments.pvp import PvpTournament
from codeclash.utils.yaml_utils import resolve_includes


def main(
    config_path: Path,
    *,
    cleanup: bool = False,
    output_dir: Path | None = None,
    suffix: str = "",
    keep_containers: bool = False,
):
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


def main_cli(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(description="CodeClash")
    parser.add_argument(
        "config_path",
        type=Path,
        help="Path to the config file.",
    )
    parser.add_argument(
        "-c",
        "--cleanup",
        action="store_true",
        help="If set, do not clean up the game environment after running.",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        help="Sets the output directory (default is 'logs' with current user subdirectory).",
    )
    parser.add_argument(
        "-s",
        "--suffix",
        type=str,
        help="Suffix to attach to the folder name. Does not include leading dot or underscore.",
        default="",
    )
    parser.add_argument(
        "-k",
        "--keep-containers",
        action="store_true",
        help="Do not remove containers after games/agent finish",
    )
    args = parser.parse_args(argv)
    main(**vars(args))


if __name__ == "__main__":
    main_cli()
