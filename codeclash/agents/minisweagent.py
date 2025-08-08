from pathlib import Path

import yaml
from minisweagent.agents.default import DefaultAgent
from minisweagent.models.litellm_model import LitellmModel

from codeclash.agents.abstract import Agent


class MiniSWEAgent(Agent):
    """https://github.com/SWE-agent/mini-swe-agent"""

    def __init__(self, config: dict, game):
        super().__init__(config, game)

        self.agent = DefaultAgent(
            LitellmModel(model_name=config["model"]),
            self.container,
            **yaml.safe_load(Path(config["config"]).read_text())["agent"],
        )

    def step(self):
        task = ""
        self.agent.run(task)
