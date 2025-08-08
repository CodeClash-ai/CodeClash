import os
import platform
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path

import yaml
from jinja2 import Template
from minisweagent import Environment, Model
from minisweagent.agents.default import AgentConfig, DefaultAgent
from minisweagent.models.litellm_model import LitellmModel

from codeclash.agents.abstract import Player
from codeclash.agents.utils import resolve_api_key
from codeclash.games.abstract import CodeGame


class ClashAgent(DefaultAgent):
    """
    Slightly modified version of mini-SWE-agent
    (https://github.com/SWE-agent/mini-swe-agent)
    """

    def __init__(
        self,
        model: Model,
        env: Environment,
        game: CodeGame,
        *,
        config_class: Callable = AgentConfig,
        **kwargs,
    ):
        super().__init__(model, env, config_class=config_class, **kwargs)
        self.game = game

    def render_template(self, template: str, **kwargs) -> str:
        cs = (
            asdict(self.config)
            | asdict(self.env.config)
            | asdict(self.model.config)
            | platform.uname()._asdict()
            | {
                "rounds": self.game.rounds,
                "round": self.game.round,
            }
        )
        return Template(template).render(**kwargs, **cs, **os.environ)


class MiniSWEAgent(Player):
    """Player with agentic code editing capabilities"""

    def __init__(self, config: dict, game):
        super().__init__(config, game)
        self.agent = ClashAgent(
            LitellmModel(
                model_name=config["model"],
                model_kwargs={"api_key": resolve_api_key(config["model"])},
            ),
            self.container,
            game,
            **yaml.safe_load(Path(config["config"]).read_text())["agent"],
        )

    def run(self):
        self.agent.run("")
