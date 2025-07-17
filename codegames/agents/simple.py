from litellm import completion
from codegames.agents.abstract import Agent
from pathlib import Path


class SimpleAgent(Agent):
    def __init__(self, config: dict, game):
        super().__init__(config, game)
    
    def step(self, game_state: Path):
        raise NotImplementedError("SimpleAgent step method not implemented yet.")
