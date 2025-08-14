from codeclash.agents.abstract import Player
from codeclash.agents.dummy import Dummy
from codeclash.agents.minisweagent import MiniSWEAgent
from codeclash.agents.utils import GameContext
from codeclash.games.abstract import CodeGame


def get_agent(config: dict, prompts: dict, game: CodeGame) -> Player:
    agents = {
        "dummy": Dummy,
        "mini": MiniSWEAgent,
    }.get(config["agent"])
    if agents is None:
        raise ValueError(f"Unknown agent type: {config['agent']}")
    environment = game.get_environment(
        f"{game.game_id}.{config['name']}"
    )  # NOTE: MUST be branch_name (defined in agents/abstract.py)
    return agents(
        config,
        environment,
        GameContext(
            id=game.game_id,
            name=game.name,
            num_players=len(game.config["players"]),
            player_ids=[p["name"] for p in game.config["players"]],
            player_id=config["name"],
            prompts=prompts,
            round=1,
            rounds=game.rounds,
        ),
    )
