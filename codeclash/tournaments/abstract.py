import getpass
import time
import traceback
from pathlib import Path

from codeclash.agents import get_agent
from codeclash.agents.abstract import Player
from codeclash.agents.utils import GameContext
from codeclash.constants import DIR_LOGS, DIR_WORK
from codeclash.utils.environment import create_file_on_container
from codeclash.utils.log import get_logger


class AbstractTournament:
    def __init__(self, config: dict, *, name: str, **kwargs):
        self.config: dict = config
        self.name: str = name
        self.tournament_id: str = f"{self.name}{time.strftime('%y%m%d%H%M%S')}"
        self.local_output_dir: Path = (
            DIR_LOGS / getpass.getuser() / self.tournament_id
        ).resolve()
        self._metadata: dict = {
            "name": self.name,
            "tournament_id": self.tournament_id,
        }
        self.logger = get_logger(
            self.name, log_path=self.local_output_dir / "tournament.log", emoji="🏆"
        )

    def get_metadata(self) -> dict:
        return self._metadata

    def _copy_game_log_to_agent(self, agent, round_num: int, log_output: str) -> None:
        """Copy round log to agent environment."""
        try:
            create_file_on_container(
                container=agent.environment,
                content=log_output,
                dest_path=f"logs/round_{round_num}.log",
            )
        except Exception:
            self.logger.error(
                f"Error creating round log in {agent.name}'s container: {traceback.format_exc()}"
            )
        else:
            self.logger.info(f"Created round log in {agent.name}'s container.")
