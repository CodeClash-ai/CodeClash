import argparse

import yaml

from codeclash.agents import get_agent
from codeclash.agents.abstract import Player
from codeclash.games import get_game
from codeclash.games.abstract import CodeGame


def main(config_path: str, cleanup: bool = False, push_agent: bool = False):
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    game: CodeGame = get_game(config)
    agents: list[Player] = []
    for agent_conf in config["players"]:
        agents.append(get_agent(agent_conf, config["prompts"], game))

    try:
        for _ in range(game.rounds):
            game.run_round(agents)
            for agent in agents:
                agent.run()
    finally:
        game.end(cleanup)
        if push_agent:
            for agent in agents:
                agent.push()


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
