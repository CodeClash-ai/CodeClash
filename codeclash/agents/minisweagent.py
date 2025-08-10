import os
import platform
import traceback
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path

import yaml
from jinja2 import Template
from minisweagent import Environment, Model
from minisweagent.agents.default import (
    AgentConfig,
    DefaultAgent,
    NonTerminatingException,
    TerminatingException,
)
from minisweagent.models.litellm_model import LitellmModel
from minisweagent.run.utils.save import save_traj
from rich.console import Console

from codeclash.agents.abstract import Player
from codeclash.agents.utils import resolve_api_key
from codeclash.games.abstract import CodeGame


class ClashAgent(DefaultAgent):
    """
    Slightly modified version of `DefaultAgent` from mini-SWE-agent
    (https://github.com/SWE-agent/mini-swe-agent)
    """

    def __init__(
        self,
        model: Model,
        env: Environment,
        name: str,
        game: CodeGame,
        *,
        config_class: Callable = AgentConfig,
        **kwargs,
    ):
        super().__init__(model, env, config_class=config_class, **kwargs)
        self.name = name
        self.game = game
        self.console = Console()

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

    def run(self) -> tuple[str, str]:
        """Run step() until agent is finished. Return exit status & message"""
        self.messages = []
        self.add_message("system", self.render_template(self.config.system_template))
        self.add_message("user", self.render_template(self.config.instance_template))

        # Start rich spinner
        with self.console.status(
            f"[bold green]{self.name} updating codebase..."
        ) as status:
            while True:
                try:
                    self.step()
                except NonTerminatingException as e:
                    self.add_message("user", str(e))
                except TerminatingException as e:
                    self.add_message("user", str(e))
                    return type(e).__name__, str(e)

    def has_finished(self, output: dict[str, str]):
        """Raises Submitted exception with final output if the agent has finished its task."""
        save_traj(self, f"{self.name}_r{self.game.round}.json")
        super().has_finished(output)


class MiniSWEAgent(Player):
    """Player with agentic code editing capabilities"""

    def __init__(self, config: dict, game: CodeGame):
        super().__init__(config, game)
        self.agent = ClashAgent(
            LitellmModel(
                model_name=config["model"],
                model_kwargs={"api_key": resolve_api_key(config["model"])},
            ),
            self.container,
            self.name,
            game,
            **yaml.safe_load(Path(config["config"]).read_text())["agent"],
        )

    def run(self):
        try:
            exit_status, result = self.agent.run()
        except Exception as e:
            result = str(e)
            print(traceback.format_exc())
        self.commit()
