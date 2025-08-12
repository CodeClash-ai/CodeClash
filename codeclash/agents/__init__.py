from codeclash.agents.abstract import Player
from codeclash.agents.dummy import Dummy
from codeclash.agents.minisweagent import MiniSWEAgent
from codeclash.games.abstract import CodeGame


def get_agent(config: dict, game: CodeGame) -> Player:
    agents = {
        "dummy": Dummy,
        "mini": MiniSWEAgent,
    }.get(config["agent"])
    if agents is None:
        raise ValueError(f"Unknown agent type: {config['agent']}")
    environment = game.get_environment(f"{game.game_id}_{config['name']}")
    format_vars = {
        "game_id": game.game_id,
        "rounds": game.rounds,
        "round": game.round,
    }
    return agents(config, environment, format_vars)
