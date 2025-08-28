import argparse

import yaml

from codeclash.tournaments.single_player_training import SinglePlayerTraining


def main(config_path: str, cleanup: bool = False):
    with open(config_path) as f:
        config = yaml.safe_load(f)
    training = SinglePlayerTraining(config, cleanup)
    training.run()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CodeClash")
    parser.add_argument(
        "config_path",
        type=str,
        default="configs/battlesnake.yaml",
        help="Path to the config file.",
    )
    parser.add_argument(
        "-c",
        "--cleanup",
        action="store_true",
        help="If set, do not clean up the game environment after running.",
    )
    args = parser.parse_args()
    main(**vars(args))
