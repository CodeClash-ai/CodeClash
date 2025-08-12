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
    environment = game.get_environment()
    template_vars = {
        "game_id": game.game_id,
        "rounds": game.rounds,
        "round": game.round,
        "player_id": config["name"],
        "game_description": game.config.get("description", ""),
    }
    return agents(config, environment, template_vars)
