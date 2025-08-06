from codeclash.agents.abstract import Agent
from codeclash.agents.dummy import DummyAgent
from codeclash.agents.simple import SimpleAgent
from codeclash.games.abstract import CodeGame


def get_agent(config: dict, game: CodeGame) -> Agent:
    agents = {
        "dummy": DummyAgent,
        "simple": SimpleAgent,
    }.get(config["agent"])
    if agents is None:
        raise ValueError(f"Unknown agent type: {config['agent']}")
    return agents(config, game)
