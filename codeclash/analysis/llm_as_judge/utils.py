import fcntl
import json
from pathlib import Path

from codeclash.analysis.metrics.elo import get_scores
from pydantic import BaseModel


class FileLock:
    def __init__(self, lock_path: str | Path):
        self.lock_path = Path(lock_path)
        self.lock_file = None

    def __enter__(self):
        self.lock_file = open(self.lock_path, "w")
        fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_EX)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.lock_file:
            fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_UN)
            self.lock_file.close()
        return False


class Instance(BaseModel):
    player_name: str
    round_number: int
    tournament_name: str
    trajectory_path: Path

    @property
    def instance_id(self) -> str:
        return f"{self.tournament_name}__{self.player_name}__r{self.round_number}"
    
    @property
    def tournament_path(self) -> Path:
        return self.trajectory_path.parent.parent.parent
    
    @property
    def metadata_path(self) -> Path:
        return self.tournament_path / "metadata.json"

    def get_lm_name_self_opponent(self) -> tuple[str, str]:
        metadata = json.loads(self.metadata_path.read_text())
        player_configs = metadata["config"]["players"]
        player_config = [pc for pc in player_configs if pc["name"] == self.player_name][0]
        other_player_config = [pc for pc in player_configs if pc["name"] != self.player_name][0]
        return player_config["config"]["model"]["model_name"].removeprefix("@"), other_player_config["config"]["model"]["model_name"].removeprefix("@")
    
    def get_current_next_round_win_rate(self) -> tuple[float | None, float | None]:
        metadata = json.loads(self.metadata_path.read_text())
        current_round_stats = metadata["round_stats"].get(str(self.round_number))
        next_round_stats = metadata["round_stats"].get(str(self.round_number + 1))
        current_win_rate = None
        next_win_rate = None
        if current_round_stats is not None:
            current_win_rate = get_scores(current_round_stats).get(self.player_name)
        if next_round_stats is not None:
            next_win_rate = get_scores(next_round_stats).get(self.player_name)
        return current_win_rate, next_win_rate


class InstanceBatch(BaseModel):
    instances: list[Instance]


def find_tournament_folders(input_dir: Path) -> list[Path]:
    return [d.parent for d in input_dir.rglob("metadata.json")]


def parse_trajectory_name(trajectory_path: Path) -> Instance:
    try:
        round_number = int(trajectory_path.name.removesuffix(".traj.json").split("_r")[1])
    except:
        print(trajectory_path)
        raise
    return Instance(
        trajectory_path=trajectory_path,
        player_name=trajectory_path.parent.name,
        round_number=round_number,
        tournament_name=trajectory_path.parent.parent.parent.name,
    )


def get_instances(input_folder: Path) -> list[Instance]:
    trajectories = input_folder.rglob("*.traj.json")
    return [parse_trajectory_name(trajectory) for trajectory in trajectories]
