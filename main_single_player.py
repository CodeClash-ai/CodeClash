import argparse
import getpass
from pathlib import Path

import yaml

from codeclash import CONFIG_DIR
from codeclash.constants import DIR_LOGS
from codeclash.tournaments.single_player import SinglePlayerTraining
from codeclash.utils.yaml_utils import resolve_includes


def main(
    config_path: Path,
    *,
    cleanup: bool = False,
    output_dir: Path | None = None,
    suffix: str = "",
):
    yaml_content = config_path.read_text()
    preprocessed_yaml = resolve_includes(yaml_content, base_dir=CONFIG_DIR)
    config = yaml.safe_load(preprocessed_yaml)

    folder_name = f"SinglePlayerTraining.{config['game']['name']}{suffix}"
    if output_dir is None:
        full_output_dir = DIR_LOGS / getpass.getuser() / folder_name
    else:
        full_output_dir = output_dir / folder_name

    training = SinglePlayerTraining(config, cleanup=cleanup, output_dir=full_output_dir)
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
    args = parser.parse_args(argv)
    main(**vars(args))


if __name__ == "__main__":
    main_cli()
