import argparse
from pathlib import Path

import yaml

from codeclash import CONFIG_DIR
from codeclash.tournaments.single_player import SinglePlayerTraining
from codeclash.utils.yaml_utils import resolve_includes


def main(config_path: Path, cleanup: bool = False):
    yaml_content = config_path.read_text()
    preprocessed_yaml = resolve_includes(yaml_content, base_dir=CONFIG_DIR)
    config = yaml.safe_load(preprocessed_yaml)
    training = SinglePlayerTraining(config, cleanup=cleanup)
    training.run()


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
    args = parser.parse_args(argv)
    main(**vars(args))


if __name__ == "__main__":
    main_cli()
