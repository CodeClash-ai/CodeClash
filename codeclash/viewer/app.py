#!/usr/bin/env python3
"""
Trajectory Viewer for AI Agent Benchmark

A Flask-based web application to visualize AI agent game trajectories
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, redirect, render_template, request, url_for

# Global variable to store the directory to search for logs
LOG_BASE_DIR = Path.cwd() / "logs"


def set_log_base_directory(directory: str | Path):
    """Set the logs directory directly"""
    global LOG_BASE_DIR
    LOG_BASE_DIR = Path(directory).resolve()


def is_game_folder(log_dir: Path) -> bool:
    """Check if a directory contains metadata.json and is therefore a game folder"""
    metadata_file = log_dir / "metadata.json"
    return metadata_file.exists()


def get_round_count_from_metadata(log_dir: Path) -> int | None:
    """Extract round count from metadata.json if it exists"""
    metadata_file = log_dir / "metadata.json"
    if not metadata_file.exists():
        return None

    try:
        metadata = json.loads(metadata_file.read_text())
        return metadata.get("config", {}).get("game", {}).get("rounds")
    except (json.JSONDecodeError, KeyError):
        return None


def get_models_from_metadata(log_dir: Path) -> list[str]:
    """Extract model names from metadata.json if it exists"""
    metadata_file = log_dir / "metadata.json"
    if not metadata_file.exists():
        return []

    try:
        metadata = json.loads(metadata_file.read_text())
        models = []
        players_config = metadata.get("config", {}).get("players", [])

        # Handle both list and dict formats
        if isinstance(players_config, list):
            # If players is a list, iterate through each player
            for player_config in players_config:
                if isinstance(player_config, dict):
                    model_name = player_config.get("config", {}).get("model", {}).get("model_name")
                    if model_name and model_name not in models:
                        models.append(model_name)
        elif isinstance(players_config, dict):
            # If players is a dict, iterate through player keys (p1, p2, etc.)
            for _player_key, player_config in players_config.items():
                if isinstance(player_config, dict):
                    model_name = player_config.get("config", {}).get("model", {}).get("model_name")
                    if model_name and model_name not in models:
                        models.append(model_name)

        return models
    except (json.JSONDecodeError, KeyError, AttributeError):
        return []


def find_all_game_folders(base_dir: Path) -> list[dict[str, Any]]:
    """Recursively find all folders and mark which ones contain metadata.json"""
    all_folders = []
    game_folders = set()  # Track which folders are actual game folders

    def scan_directory(directory: Path, relative_path: str = ""):
        if not directory.exists() or not directory.is_dir():
            return

        try:
            for item in directory.iterdir():
                if item.is_dir():
                    current_relative = relative_path + "/" + item.name if relative_path else item.name

                    depth = current_relative.count("/")

                    # Check if this directory is a game folder
                    if is_game_folder(item):
                        round_count = get_round_count_from_metadata(item)
                        models = get_models_from_metadata(item)
                        game_folders.add(current_relative)
                        all_folders.append(
                            {
                                "name": current_relative,
                                "full_path": str(item),
                                "round_count": round_count,
                                "models": models,
                                "is_game": True,
                                "depth": depth,
                                "parent": relative_path if relative_path else None,
                            }
                        )
                    else:
                        # Add as intermediate folder if it has game folders in subdirectories
                        all_folders.append(
                            {
                                "name": current_relative,
                                "full_path": str(item),
                                "round_count": None,
                                "models": [],
                                "is_game": False,
                                "depth": depth,
                                "parent": relative_path if relative_path else None,
                            }
                        )

                    # Recursively scan subdirectories
                    scan_directory(item, current_relative)
        except (PermissionError, OSError):
            # Skip directories we can't access
            pass

    scan_directory(base_dir)

    # Filter out intermediate folders that don't lead to any game folders
    filtered_folders = []
    for folder in sorted(all_folders, key=lambda x: x["name"]):
        if folder["is_game"]:
            # Always include game folders
            filtered_folders.append(folder)
        else:
            # Include intermediate folders only if they have game folders as descendants
            folder_path = folder["name"]
            has_game_descendants = any(game_path.startswith(folder_path + "/") for game_path in game_folders)
            if has_game_descendants:
                filtered_folders.append(folder)

    return filtered_folders


@dataclass
class GameMetadata:
    """Metadata about a game session"""

    results: dict[str, Any]
    main_log: str
    main_log_path: str
    metadata_file_path: str
    rounds: list[dict[str, Any]]


@dataclass
class TrajectoryInfo:
    """Information about a single trajectory"""

    player_id: int
    round_num: int
    api_calls: int
    cost: float
    exit_status: str | None
    submission: str | None
    memory: str | None
    messages: list[dict[str, Any]]
    diff: str | None = None
    incremental_diff: str | None = None
    modified_files: dict[str, str] | None = None
    trajectory_file_path: str | None = None


class LogParser:
    """Parses game log files into structured data"""

    def __init__(self, log_dir: Path):
        self.log_dir = Path(log_dir)
        self._player_metadata = {}

    def parse_game_metadata(self) -> GameMetadata:
        """Parse overall game metadata"""
        # Look for metadata.json
        metadata_file = self.log_dir / "metadata.json"
        if metadata_file.exists():
            results = json.loads(metadata_file.read_text())
            metadata_file_path = str(metadata_file)
        else:
            results = {"status": "No metadata file found"}
            metadata_file_path = ""

        # Store player metadata for later use
        self._player_metadata = {}
        if "agents" in results:
            for agent in results["agents"]:
                player_name = agent.get("name", "")
                self._player_metadata[player_name] = agent

        # Parse tournament.log if it exists
        main_log_file = self.log_dir / "tournament.log"
        main_log = main_log_file.read_text() if main_log_file.exists() else "No tournament log found"
        main_log_path = str(main_log_file) if main_log_file.exists() else ""

        # Parse round directories and their sim logs
        rounds = []
        rounds_dir = self.log_dir / "rounds"
        if rounds_dir.exists():
            # Get all round directories (sorted numerically)
            round_dirs = sorted([d for d in rounds_dir.iterdir() if d.is_dir()], key=lambda x: int(x.name))

            for round_dir in round_dirs:
                round_num = int(round_dir.name)

                # Collect all sim logs for this round
                sim_logs = []
                sim_files = sorted(round_dir.glob("sim_*.log"), key=lambda x: int(x.stem.split("_")[1]))

                for sim_file in sim_files:
                    sim_content = sim_file.read_text()
                    sim_logs.append({"filename": sim_file.name, "content": sim_content, "full_path": str(sim_file)})

                # Check for round results
                results_file = round_dir / "results.json"
                round_results = None
                if results_file.exists():
                    round_results = json.loads(results_file.read_text())

                rounds.append({"round_num": round_num, "sim_logs": sim_logs, "results": round_results})

        return GameMetadata(
            results=results,
            main_log=main_log,
            main_log_path=main_log_path,
            metadata_file_path=metadata_file_path,
            rounds=rounds,
        )

    def parse_trajectory(self, player_id: int, round_num: int) -> TrajectoryInfo | None:
        """Parse a specific trajectory file"""
        # Look in players/$player_id/ directory
        player_dir = self.log_dir / "players" / f"p{player_id}"
        if not player_dir.exists():
            return None

        # Try both .json and .log extensions
        for ext in [".json", ".log"]:
            traj_file = player_dir / f"p{player_id}_r{round_num}.traj{ext}"
            if traj_file.exists():
                try:
                    data = json.loads(traj_file.read_text())

                    info = data.get("info", {})
                    model_stats = info.get("model_stats", {})

                    # Get diff data from player metadata if available
                    player_name = f"p{player_id}"
                    diff = None
                    incremental_diff = None
                    modified_files = None

                    if player_name in self._player_metadata:
                        player_meta = self._player_metadata[player_name]
                        diff = player_meta.get("diff", {}).get(str(round_num), "")
                        incremental_diff = player_meta.get("incremental_diff", {}).get(str(round_num), "")
                        modified_files = player_meta.get("modified_files", {}).get(str(round_num), {})

                    return TrajectoryInfo(
                        player_id=player_id,
                        round_num=round_num,
                        api_calls=model_stats.get("api_calls", 0),
                        cost=model_stats.get("instance_cost", 0.0),
                        exit_status=info.get("exit_status"),
                        submission=info.get("submission"),
                        memory=info.get("memory"),
                        messages=data.get("messages", []),
                        diff=diff,
                        incremental_diff=incremental_diff,
                        modified_files=modified_files,
                        trajectory_file_path=str(traj_file),
                    )
                except (json.JSONDecodeError, KeyError) as e:
                    print(f"Error parsing {traj_file}: {e}")

        return None

    def get_available_trajectories(self) -> list[tuple]:
        """Get list of available trajectory files as (player_id, round_num) tuples"""
        trajectories = []
        players_dir = self.log_dir / "players"

        if not players_dir.exists():
            return trajectories

        # Iterate through player directories
        for player_dir in players_dir.iterdir():
            if not player_dir.is_dir():
                continue

            try:
                # Extract player_id from directory name (e.g., "p1" -> 1)
                player_id = int(player_dir.name[1:])  # Remove 'p' prefix
            except (ValueError, IndexError):
                continue

            # Find trajectory files in this player's directory
            for traj_file in player_dir.glob("p*_r*.traj.*"):
                # Extract round from filename like p1_r2.traj.json
                parts = traj_file.stem.split(".")  # Remove extension
                if parts:
                    name_part = parts[0]  # p1_r2
                    try:
                        _, round_part = name_part.split("_")
                        round_num = int(round_part[1:])  # Remove 'r' prefix
                        trajectories.append((player_id, round_num))
                    except (ValueError, IndexError):
                        continue

        return sorted(trajectories)


app = Flask(__name__)


def nl2br(value):
    """Convert newlines to HTML <br> tags, escaping HTML first"""
    if value is None:
        return ""
    from markupsafe import escape

    escaped = escape(value)
    return escaped.replace("\n", "<br>\n")


def unescape_content(value):
    """Unescape literal \\n characters to actual newlines for proper display in <pre> tags"""
    if value is None:
        return ""
    # Replace literal \n with actual newlines
    return value.replace("\\n", "\n")


# Register the custom filters
app.jinja_env.filters["nl2br"] = nl2br
app.jinja_env.filters["unescape_content"] = unescape_content


@app.route("/")
def index():
    """Main viewer page - now redirects to picker if no folder is selected"""
    selected_folder = request.args.get("folder")

    if not selected_folder:
        return redirect(url_for("game_picker"))

    # Validate the selected folder exists and is a game folder
    logs_dir = LOG_BASE_DIR
    folder_path = logs_dir / selected_folder

    if not folder_path.exists() or not is_game_folder(folder_path):
        return redirect(url_for("game_picker"))

    # Parse the selected game
    parser = LogParser(folder_path)
    metadata = parser.parse_game_metadata()
    available_trajectories = parser.get_available_trajectories()

    # Group trajectories by round
    trajectories_by_round = {}
    for player_id, round_num in available_trajectories:
        if round_num not in trajectories_by_round:
            trajectories_by_round[round_num] = []
        trajectory = parser.parse_trajectory(player_id, round_num)
        if trajectory:
            trajectories_by_round[round_num].append(trajectory)

    # Get the full path of the selected folder
    selected_folder_path = str(folder_path)

    return render_template(
        "index.html",
        selected_folder=selected_folder,
        selected_folder_path=selected_folder_path,
        metadata=metadata,
        trajectories_by_round=trajectories_by_round,
    )


@app.route("/picker")
def game_picker():
    """Game picker page with recursive folder support"""
    logs_dir = LOG_BASE_DIR
    game_folders = find_all_game_folders(logs_dir)

    return render_template("picker.html", game_folders=game_folders, base_dir=str(logs_dir))


@app.route("/trajectory/<int:player_id>/<int:round_num>")
def trajectory_detail(player_id: int, round_num: int):
    """Get detailed trajectory data"""
    selected_folder = request.args.get("folder")
    if not selected_folder:
        return jsonify({"error": "No folder specified"})

    logs_dir = LOG_BASE_DIR
    parser = LogParser(logs_dir / selected_folder)
    trajectory = parser.parse_trajectory(player_id, round_num)

    if not trajectory:
        return jsonify({"error": "Trajectory not found"})

    return render_template("trajectory.html", trajectory=trajectory)


# Use run_viewer.py to launch the application
