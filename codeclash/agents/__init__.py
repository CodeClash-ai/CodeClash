from codeclash.agents.abstract import Player
from codeclash.agents.dummy import Dummy
from codeclash.agents.minisweagent import MiniSWEAgent
from codeclash.agents.utils import GameContext
from codeclash.constants import DIR_WORK
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
            player_id=config["name"],
            prompts=prompts,
            round=1,
            rounds=game.rounds,
            working_dir=str(DIR_WORK),
        ),
    )
