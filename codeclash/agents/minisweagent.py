import logging
import os
import traceback
from collections.abc import Callable

from minisweagent.agents.default import AgentConfig, DefaultAgent
from minisweagent.environments.docker import DockerEnvironment
from minisweagent.models import Model, get_model

from codeclash import REPO_DIR
from codeclash.agents.player import Player
from codeclash.agents.utils import GameContext
from codeclash.utils.environment import copy_to_container

os.environ["MSWEA_MODEL_RETRY_STOP_AFTER_ATTEMPT"] = "90"
os.environ["LITELLM_MODEL_REGISTRY_PATH"] = str(
    (REPO_DIR / "configs" / "mini" / "litellm_custom_model_config.yaml").resolve()
)


class ClashAgent(DefaultAgent):
    """`DefaultAgent` from mini-SWE-agent (https://github.com/SWE-agent/mini-swe-agent)
    with per-player debug logging."""

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

    def add_messages(self, *messages: dict) -> list[dict]:
        result = super().add_messages(*messages)
        for m in messages:
            self.logger.debug(f"[{m.get('role')}] {m.get('content')}", extra={"highlighter": None})
        return result


class MiniSWEAgent(Player):
    """Player with agentic code editing capabilities"""

    def __init__(self, config: dict, environment: DockerEnvironment, game_context: GameContext):
        super().__init__(config, environment=environment, game_context=game_context)

    def run(self):
        model = get_model(config=self.config["config"]["model"])
        self.agent = ClashAgent(
            model=model,
            env=self.environment,
            logger=self.logger,
            **self.config["config"]["agent"],
        )
        exit_status = None
        exc_message = None
        try:
            result = self.agent.run(task="", **self.game_context.to_template_vars())
            exit_status = result.get("exit_status", "")
        except Exception as e:
            exit_status = str(e)
            exc_message = traceback.format_exc()
            self.logger.critical(exc_message)
        finally:
            traj_path = (
                self.game_context.log_local
                / "players"
                / self.name
                / f"{self.name}_r{self.game_context.round}.traj.json"
            )
            self.agent.save(traj_path)
            copy_to_container(
                self.environment,
                traj_path,
                self.game_context.log_env / "edits" / traj_path.name,
            )
            self._metadata["agent_stats"][self.game_context.round] = {
                "exit_status": exit_status,
                "cost": self.agent.cost,
                "api_calls": self.agent.n_calls,
            }
        if exit_status.lower().strip() not in ["", "submitted", "limitsexceeded"] and exc_message is not None:
            raise RuntimeError(f"Agent {self.name} failed with exit status: {exit_status} and exception: {exc_message}")
