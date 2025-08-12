import os
import platform
import traceback
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path

import yaml
from jinja2 import Template
from minisweagent import Environment, Model
from minisweagent.agents.default import AgentConfig, DefaultAgent
from minisweagent.models.litellm_model import LitellmModel
from minisweagent.run.utils.save import save_traj
from rich.console import Console

from codeclash.agents.abstract import Player
from codeclash.agents.utils import resolve_api_key
from codeclash.constants import DIR_LOGS


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
        format_vars: dict,
        *,
        config_class: Callable = AgentConfig,
        **kwargs,
    ):
        super().__init__(model, env, config_class=config_class, **kwargs)
        self.name = name
        self.format_vars = format_vars
        self.console = Console()

    def add_message(self, role: str, content: str, **kwargs):
        super().add_message(role, content, **kwargs)
        if role == "assistant":
            self.console.print(
                f"[{self.name}] Step taken (step {self.model.n_calls}, cost {self.model.cost:.2f})"
            )

    def render_template(self, template: str, **kwargs) -> str:
        cs = (
            asdict(self.config)
            | asdict(self.env.config)
            | asdict(self.model.config)
            | platform.uname()._asdict()
            | self.format_vars
        )
        return Template(template).render(**kwargs, **cs, **os.environ)

    def run(self) -> tuple[str, str]:
        """Run step() until agent is finished. Return exit status & message"""
        with self.console.status(f"[bold green]{self.name} updating codebase..."):
            return super().run(task="")


class MiniSWEAgent(Player):
    """Player with agentic code editing capabilities"""

    def __init__(self, config: dict, environment: Environment, format_vars: dict):
        super().__init__(config, environment=environment, format_vars=format_vars)
        self.agent = ClashAgent(
            LitellmModel(
                model_name=config["model"],
                model_kwargs={"api_key": resolve_api_key(config["model"])},
            ),
            self.environment,
            self.name,
            format_vars,
            **yaml.safe_load(Path(config["config"]).read_text())["agent"],
        )

    def run(self):
        exit_status = None
        result = None
        try:
            exit_status, result = self.agent.run()
        except Exception as e:
            exit_status = str(e)
            exc_message = traceback.format_exc()
            result = exc_message
            print(exc_message)
        finally:
            player_id = self.name.split("_")[-1]
            save_traj(
                self.agent,  # type: ignore
                DIR_LOGS
                / f"{self.format_vars['game_id']}/{player_id}_r{self.format_vars['round']}.traj.json",
                exit_status=exit_status,
                result=result,
            )
            self.commit()
