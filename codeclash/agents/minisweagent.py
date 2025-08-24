import logging
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
from codeclash.agents.utils import GameContext, resolve_api_key
from codeclash.utils.environment import copy_file_to_container


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
        game_context: GameContext,
        *,
        logger: logging.Logger,
        config_class: Callable = AgentConfig,
        **kwargs,
    ):
        super().__init__(model, env, config_class=config_class, **kwargs)
        self.name = name
        self.game_context = game_context
        self.console = Console()
        self.logger = logger

    def add_message(self, role: str, content: str, **kwargs):
        super().add_message(role, content, **kwargs)
        self.logger.debug(f"[{role}] {content}", extra={"highlighter": None})
        if role == "assistant":
            self.logger.info(
                f"Step taken (step {self.model.n_calls}, cost {self.model.cost:.2f})"
            )

    def render_template(self, template: str, **kwargs) -> str:
        cs = (
            asdict(self.config)
            | asdict(self.env.config)
            | asdict(self.model.config)
            | platform.uname()._asdict()
            | self.game_context.to_dict()
        )
        return Template(template).render(**kwargs, **cs, **os.environ)

    def run(self) -> tuple[str, str]:
        """Run step() until agent is finished. Return exit status & message"""
        return super().run(task="")


class MiniSWEAgent(Player):
    """Player with agentic code editing capabilities"""

    def __init__(
        self, config: dict, environment: Environment, game_context: GameContext
    ):
        super().__init__(config, environment=environment, game_context=game_context)

    def run(self):
        self.agent = ClashAgent(
            LitellmModel(
                model_name=self.config["model"],
                model_kwargs={"api_key": resolve_api_key(self.config["model"])},
            ),
            self.environment,
            self.name,
            self.game_context,
            logger=self.logger,
            **yaml.safe_load(Path(self.config["config"]).read_text())["agent"],
        )
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
            traj_path = (
                self.game_context.log_local
                / f"{self.name}_r{self.game_context.round}.traj.json"
            )
            save_traj(
                self.agent,  # type: ignore
                traj_path,
                exit_status=exit_status,
                result=result,
            )
            copy_file_to_container(
                self.environment,
                traj_path,
                self.game_context.log_env / traj_path.name,
            )
            # self.commit()  # now called in post_round_hook
