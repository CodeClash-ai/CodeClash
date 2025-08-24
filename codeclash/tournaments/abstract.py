import getpass
import time
from pathlib import Path

from codeclash.constants import DIR_LOGS
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
