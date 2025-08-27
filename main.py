import argparse

import yaml

from codeclash.tournaments.pvp import PvpTournament


def main(config_path: str, *, cleanup: bool = False, push_agent: bool = False):
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    training = PvpTournament(config, cleanup=cleanup, push_agent=push_agent)
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
    parser.add_argument(
        "-p",
        "--push_agent",
        action="store_true",
        help="If set, push each agent's codebase to a new repository after running.",
    )
    args = parser.parse_args()
    main(**vars(args))
