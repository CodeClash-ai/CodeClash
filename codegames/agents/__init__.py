from codegames.agents.abstract import Agent
from codegames.agents.dummy import DummyAgent
from codegames.agents.simple import SimpleAgent
from codegames.games.abstract import CodeGame

def get_agent(config: dict, game: CodeGame) -> Agent:
    agents = {
        "dummy": DummyAgent,
        "simple": SimpleAgent,
    }.get(config["agent"])
    if agents is None:
        raise ValueError(f"Unknown agent type: {config['agent']}")
    return agents(config, game)