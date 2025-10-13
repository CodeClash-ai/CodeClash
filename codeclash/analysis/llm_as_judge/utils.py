import fcntl
import json
from pathlib import Path

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

    def get_lm_name_self_opponent(self) -> tuple[str, str]:
        metadata_path = self.trajectory_path.parent.parent.parent / "metadata.json"
        metadata = json.loads(metadata_path.read_text())
        player_configs = metadata["config"]["players"]
        player_config = [pc for pc in player_configs if pc["name"] == self.player_name][0]
        other_player_config = [pc for pc in player_configs if pc["name"] != self.player_name][0]
        return player_config["config"]["model"]["model_name"].removeprefix("@"), other_player_config["config"]["model"]["model_name"].removeprefix("@")


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
