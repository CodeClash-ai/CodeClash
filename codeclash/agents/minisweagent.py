import logging
import traceback
from collections.abc import Callable

from minisweagent import Model
from minisweagent.agents.default import AgentConfig, DefaultAgent
from minisweagent.environments.docker import DockerEnvironment
from minisweagent.models import get_model
from minisweagent.models.test_models import DeterministicModel
from minisweagent.run.utils.save import save_traj

from codeclash.agents.player import Player
from codeclash.agents.utils import GameContext
from codeclash.utils.environment import copy_to_container


class ClashAgent(DefaultAgent):
    """
    Slightly modified version of `DefaultAgent` from mini-SWE-agent
    (https://github.com/SWE-agent/mini-swe-agent)
    """

    def __init__(
        self,
        model: Model,
        env: DockerEnvironment,
        *,
        logger: logging.Logger,
        config_class: Callable = AgentConfig,
        **kwargs,
    ):
        super().__init__(model, env, config_class=config_class, **kwargs)
        self.logger = logger

    def add_message(self, role: str, content: str, **kwargs):
        super().add_message(role, content, **kwargs)
        self.logger.debug(f"[{role}] {content}", extra={"highlighter": None})


class MiniSWEAgent(Player):
    """Player with agentic code editing capabilities"""

    def __init__(self, config: dict, environment: DockerEnvironment, game_context: GameContext):
        super().__init__(config, environment=environment, game_context=game_context)

    def run(self):
        # temporary workaround around https://github.com/SWE-agent/mini-swe-agent/issues/477
        if "DeterministicModel" not in self.config["config"]["model"].get("model_class", ""):
            model = get_model(config=self.config["config"]["model"])
        else:
            model = DeterministicModel(outputs=self.config["config"]["model"]["outputs"])
        self.agent = ClashAgent(
            model=model,
            env=self.environment,
            logger=self.logger,
            **self.config["config"]["agent"],
        )
        exit_status = None
        result = None
        try:
            exit_status, result = self.agent.run(task="", **self.game_context.to_template_vars())
        except Exception as e:
            exit_status = str(e)
            exc_message = traceback.format_exc()
            result = exc_message
            print(exc_message)
        finally:
            traj_path = (
                self.game_context.log_local
                / "players"
                / self.name
                / f"{self.name}_r{self.game_context.round}.traj.json"
            )
            save_traj(
                self.agent,  # type: ignore
                traj_path,
                exit_status=exit_status,
                result=result,
                print_fct=self.logger.debug,
            )
            copy_to_container(
                self.environment,
                traj_path,
                self.game_context.log_env / "edits" / traj_path.name,
            )
