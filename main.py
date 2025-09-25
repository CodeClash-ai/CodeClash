import argparse
import getpass
import time
from pathlib import Path

import yaml

from codeclash import CONFIG_DIR
from codeclash.constants import DIR_LOGS
from codeclash.tournaments.pvp import PvpTournament
from codeclash.utils.yaml_utils import resolve_includes


def main(
    config_path: Path,
    *,
    cleanup: bool = False,
    push: bool = False,
    output_dir: Path | None = None,
    suffix: str = "",
    keep_containers: bool = False,
):
    yaml_content = config_path.read_text()
    preprocessed_yaml = resolve_includes(yaml_content, base_dir=CONFIG_DIR)
    config = yaml.safe_load(preprocessed_yaml)

    timestamp = time.strftime("%y%m%d%H%M%S")
    rounds = config["tournament"]["rounds"]
    sims = config["game"]["sims_per_round"]

    players = [p["name"] for p in config["players"]]
    p_num = len(players)
    p_list = ".".join(sorted(players))
    suffix_part = f".{suffix}" if suffix else ""
    folder_name = f"PvpTournament.{config['game']['name']}.r{rounds}.s{sims}.p{p_num}.{p_list}{suffix_part}.{timestamp}"
    if output_dir is None:
        full_output_dir = DIR_LOGS / getpass.getuser() / folder_name
    else:
        full_output_dir = output_dir / folder_name

    tournament = PvpTournament(
        config, output_dir=full_output_dir, cleanup=cleanup, push=push, keep_containers=keep_containers
    )
    tournament.run()


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
        "-p",
        "--push",
        action="store_true",
        help="If set, push each agent's codebase to a new repository after running.",
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
