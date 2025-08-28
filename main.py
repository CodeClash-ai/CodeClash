import argparse
from pathlib import Path

import yaml

from codeclash.tournaments.pvp import PvpTournament
from codeclash.utils.yaml_utils import resolve_includes


def main(config_path: Path, *, cleanup: bool = False, push_agent: bool = False):
    yaml_content = config_path.read_text()
    preprocessed_yaml = resolve_includes(yaml_content, base_dir=config_path.parent)
    config = yaml.safe_load(preprocessed_yaml)
    training = PvpTournament(config, cleanup=cleanup, push_agent=push_agent)
    training.run()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CodeClash")
    parser.add_argument(
        "config_path",
        type=Path,
        default="configs/battlesnake.yaml",
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
        "--push_agent",
        action="store_true",
        help="If set, push each agent's codebase to a new repository after running.",
    )
    args = parser.parse_args()
    main(**vars(args))
