import argparse
import yaml

from codegames.agents import get_agent
from codegames.agents.abstract import Agent
from codegames.games import get_game
from codegames.games.abstract import CodeGame


def main(
    config_path: str,
    no_cleanup: bool = False
):
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    game: CodeGame = get_game(config)
    game.setup()
    agents: list[Agent] = []
    for agent in config["players"]:
        agents.append(get_agent(agent, game))

    try:
        for _ in range(game.rounds):
            recap = game.run_round(agents)

            for agent in agents:
                # TODO: Parallelize this in the future
                agent.step(recap)
    finally:
        if not no_cleanup:
            game.cleanup()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CodeGames")
    parser.add_argument("config_path", type=str, default="configs/battlesnake.yaml", help="Path to the config file.")
    parser.add_argument("--no-cleanup", action="store_true", help="If set, do not clean up the game environment after running.")
    args = parser.parse_args()
    main(**vars(args))