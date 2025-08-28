#!/usr/bin/env python3
"""
Trajectory Viewer for AI Agent Benchmark

A Flask-based web application to visualize AI agent game trajectories
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, render_template, request

# Global variable to store the directory to search for logs
LOG_BASE_DIR = Path.cwd() / "logs"


def set_log_base_directory(directory: str | Path):
    """Set the logs directory directly"""
    global LOG_BASE_DIR
    LOG_BASE_DIR = Path(directory).resolve()


def is_probably_failed_run(log_dir: Path) -> bool:
    """Check if a run probably failed by checking if metadata.json is missing"""
    metadata_file = log_dir / "metadata.json"
    return not metadata_file.exists()


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


@dataclass
class GameMetadata:
    """Metadata about a game session"""

    results: dict[str, Any]
    main_log: str
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


class LogParser:
    """Parses game log files into structured data"""

    def __init__(self, log_dir: Path):
        self.log_dir = Path(log_dir)

    def parse_game_metadata(self) -> GameMetadata:
        """Parse overall game metadata"""
        # Look for results.json or metadata.json
        results_file = self.log_dir / "results.json"
        if not results_file.exists():
            # Check for metadata.json as fallback
            metadata_file = self.log_dir / "metadata.json"
            if metadata_file.exists():
                results = json.loads(metadata_file.read_text())
            else:
                results = {"status": "No results file found"}
        else:
            results = json.loads(results_file.read_text())

        # Parse main.log if it exists
        main_log_file = self.log_dir / "game.log"
        main_log = main_log_file.read_text() if main_log_file.exists() else "No main log found"

        # Parse round logs
        rounds = []
        round_files = sorted(self.log_dir.glob("round_*.log"))
        for round_file in round_files:
            round_content = round_file.read_text()
            rounds.append({"filename": round_file.name, "content": round_content})

        return GameMetadata(results=results, main_log=main_log, rounds=rounds)

    def parse_trajectory(self, player_id: int, round_num: int) -> TrajectoryInfo | None:
        """Parse a specific trajectory file"""
        # Try both .json and .log extensions
        for ext in [".json", ".log"]:
            traj_file = self.log_dir / f"p{player_id}_r{round_num}.traj{ext}"
            if traj_file.exists():
                try:
                    data = json.loads(traj_file.read_text())

                    info = data.get("info", {})
                    model_stats = info.get("model_stats", {})

                    return TrajectoryInfo(
                        player_id=player_id,
                        round_num=round_num,
                        api_calls=model_stats.get("api_calls", 0),
                        cost=model_stats.get("instance_cost", 0.0),
                        exit_status=info.get("exit_status"),
                        submission=info.get("submission"),
                        memory=info.get("memory"),
                        messages=data.get("messages", []),
                    )
                except (json.JSONDecodeError, KeyError) as e:
                    print(f"Error parsing {traj_file}: {e}")

        return None

    def get_available_trajectories(self) -> list[tuple]:
        """Get list of available trajectory files as (player_id, round_num) tuples"""
        trajectories = []
        for traj_file in self.log_dir.glob("p*_r*.traj.*"):
            # Extract player and round from filename like p1_r2.traj.json
            parts = traj_file.stem.split(".")  # Remove extension
            if parts:
                name_part = parts[0]  # p1_r2
                try:
                    player_part, round_part = name_part.split("_")
                    player_id = int(player_part[1:])  # Remove 'p' prefix
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


# Register the custom filter
app.jinja_env.filters["nl2br"] = nl2br


@app.route("/")
def index():
    """Main viewer page"""
    # Get available log directories
    logs_dir = LOG_BASE_DIR
    log_folders_info = []
    if logs_dir.exists():
        for d in logs_dir.iterdir():
            if d.is_dir():
                folder_info = {
                    "name": d.name,
                    "is_failed": is_probably_failed_run(d),
                    "round_count": get_round_count_from_metadata(d),
                }
                log_folders_info.append(folder_info)

        # Sort folders alphabetically by name
        log_folders_info.sort(key=lambda x: x["name"])

    # Extract just the names for backwards compatibility
    log_folders = [folder["name"] for folder in log_folders_info]

    selected_folder = request.args.get("folder", log_folders[0] if log_folders else None)

    if not selected_folder or not (logs_dir / selected_folder).exists():
        return render_template("no_logs.html", log_folders=log_folders)

    # Parse the selected game
    parser = LogParser(logs_dir / selected_folder)
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

    return render_template(
        "index.html",
        log_folders=log_folders,
        log_folders_info=log_folders_info,
        selected_folder=selected_folder,
        metadata=metadata,
        trajectories_by_round=trajectories_by_round,
    )


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
