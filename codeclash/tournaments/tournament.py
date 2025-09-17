import getpass
import os
import time
import traceback
from pathlib import Path

from codeclash.constants import DIR_LOGS
from codeclash.utils.environment import create_file_in_container
from codeclash.utils.log import get_logger


class AbstractTournament:
    def __init__(self, config: dict, *, name: str, output_dir: Path | None = None, **kwargs):
        self.config: dict = config
        self.name: str = name
        self.tournament_id: str = f"{self.name}.{config['game']['name']}.{time.strftime('%y%m%d%H%M%S')}"
        self._custom_output_dir: Path | None = output_dir
        self._metadata: dict = {
            "name": self.name,
            "tournament_id": self.tournament_id,
            "config": self.config,
            "created_timestamp": int(time.time()),
        }
        self.logger = get_logger(self.name, log_path=self.local_output_dir / "tournament.log", emoji="🏆")

    @property
    def local_output_dir(self) -> Path:
        if self._custom_output_dir is not None:
            # Custom output directory provided, add timestamp to make it unique
            return (self._custom_output_dir / time.strftime("%y%m%d%H%M%S")).resolve()

        # Default behavior
        base_dir = DIR_LOGS
        if "PYTEST_CURRENT_TEST" in os.environ:
            base_dir = Path("/tmp/codeclash")
        return (base_dir / getpass.getuser() / self.tournament_id).resolve()

    def get_metadata(self) -> dict:
        return self._metadata

    def _copy_game_log_to_agent(self, agent, round_num: int, log_output: str, dest_path: str = None) -> None:
        """Copy round log to agent environment."""
        try:
            create_file_in_container(
                container=agent.environment,
                content=log_output,
                dest_path=dest_path if dest_path else f"logs/round_{round_num}.log",
            )
        except Exception:
            self.logger.error(f"Error creating round log in {agent.name}'s container: {traceback.format_exc()}")
