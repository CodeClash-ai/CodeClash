import argparse
from pathlib import Path

import yaml

from codeclash import CONFIG_DIR
from codeclash.constants import LOCAL_LOG_DIR
from codeclash.tournaments.pvp import PvpTournament
from codeclash.utils.yaml_utils import resolve_includes


def main(
    config_path: Path,
):
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


def main_cli(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(description="CodeClash Ladder Runner")
    parser.add_argument(
        "config_path",
        type=Path,
        help="Path to the ladder configuration YAML file.",
    )
    args = parser.parse_args(argv)
    main(**vars(args))


if __name__ == "__main__":
    main_cli()
