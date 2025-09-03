from minisweagent.environments.docker import DockerEnvironment

from codeclash.agents.dummy_agent import Dummy
from codeclash.agents.minisweagent import MiniSWEAgent
from codeclash.agents.player import Player
from codeclash.agents.utils import GameContext


def get_agent(config: dict, game_context: GameContext, environment: DockerEnvironment) -> Player:
    agents = {
        "dummy": Dummy,
        "mini": MiniSWEAgent,
    }.get(config["agent"])
    if agents is None:
        raise ValueError(f"Unknown agent type: {config['agent']}")
    return agents(config, environment, game_context)
