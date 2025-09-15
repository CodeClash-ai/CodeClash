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

from codeclash.ratings.significance import calculate_p_value
from codeclash.tournaments.utils.git_utils import filter_git_diff, split_git_diff_by_files

# Global variable to store the directory to search for logs
LOG_BASE_DIR = Path.cwd() / "logs"


@dataclass
class AgentInfo:
    """Information about a single agent"""

    name: str
    model_name: str | None = None
    agent_class: str | None = None


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
        return metadata.get("config", {}).get("tournament", {}).get("rounds")
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


def get_agent_info_from_metadata(metadata: dict[str, Any]) -> list[AgentInfo]:
    """Extract detailed agent information from metadata"""
    agents = []
    players_config = metadata.get("config", {}).get("players", {})

    # Handle both list and dict formats
    if isinstance(players_config, list):
        # If players is a list, iterate through each player
        for i, player_config in enumerate(players_config):
            if isinstance(player_config, dict):
                name = f"p{i + 1}"  # Default naming p1, p2, etc.
                config = player_config.get("config", {})
                model_name = config.get("model", {}).get("model_name")
                agent_class = config.get("agent_class")
                agents.append(AgentInfo(name=name, model_name=model_name, agent_class=agent_class))
    elif isinstance(players_config, dict):
        # If players is a dict, iterate through player keys (p1, p2, etc.)
        for player_key, player_config in sorted(players_config.items()):
            if isinstance(player_config, dict):
                config = player_config.get("config", {})
                model_name = config.get("model", {}).get("model_name")
                agent_class = config.get("agent_class")
                agents.append(AgentInfo(name=player_key, model_name=model_name, agent_class=agent_class))

    return agents


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
    agent_info: list[AgentInfo] | None = None


def process_round_results(
    round_results: dict[str, Any] | None, agent_info: list[AgentInfo] | None = None
) -> dict[str, Any] | None:
    """Process round results to add computed fields and sort scores"""
    if not round_results:
        return round_results

    # Create a copy to avoid modifying original data
    processed = round_results.copy()

    # Get scores, initialize empty dict if missing
    scores = round_results.get("scores", {}).copy()

    # Ensure all expected players are in scores, even with 0 wins
    if agent_info:
        expected_players = {agent.name for agent in agent_info}
        missing_players = expected_players - set(scores.keys())
        if missing_players:
            print(f"WARNING: Players {sorted(missing_players)} not found in round results, adding with 0 wins")
            for player in missing_players:
                scores[player] = 0

    # Sort scores alphabetically by key
    scores = dict(sorted(scores.items()))
    processed["scores"] = scores
    processed["sorted_scores"] = list(scores.items())

    # Calculate winner percentage and p-value
    winner = round_results.get("winner")
    if winner and scores:
        total_games = sum(scores.values())
        if total_games > 0:
            if winner != "Tie":
                winner_wins = scores.get(winner, 0)
                ties = scores.get("Tie", 0)
                win_percentage = round(((winner_wins + 0.5 * ties) / total_games) * 100, 1)
                processed["winner_percentage"] = win_percentage
            else:
                processed["winner_percentage"] = None  # No percentage for ties

            # Calculate p-value for statistical significance
            print(f"Calculating p-value for scores: {dict(sorted(scores.items()))}")
            p_value = calculate_p_value(scores)
            print(f"P-value result: {p_value} (rounded: {round(p_value, 2)})")
            processed["p_value"] = round(p_value, 2)
        else:
            processed["winner_percentage"] = None
            processed["p_value"] = None
    else:
        processed["winner_percentage"] = None
        processed["p_value"] = None

    return processed


@dataclass
class TrajectoryInfo:
    """Information about a single trajectory"""

    player_id: str  # Changed from int to str to support player names
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
    diff_by_files: dict[str, str] | None = None
    incremental_diff_by_files: dict[str, str] | None = None


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
                    # Get agent info for this round (we'll need to get it from metadata)
                    agent_info = get_agent_info_from_metadata(results) if results else []
                    round_results = process_round_results(round_results, agent_info)

                rounds.append({"round_num": round_num, "sim_logs": sim_logs, "results": round_results})

        # Extract agent information
        agent_info = get_agent_info_from_metadata(results) if results else []

        return GameMetadata(
            results=results,
            main_log=main_log,
            main_log_path=main_log_path,
            metadata_file_path=metadata_file_path,
            rounds=rounds,
            agent_info=agent_info,
        )

    def parse_trajectory(self, player_name: str, round_num: int) -> TrajectoryInfo | None:
        """Parse a specific trajectory file"""
        # Look in players/$player_name/ directory
        player_dir = self.log_dir / "players" / player_name
        if not player_dir.exists():
            return None

        # Try both .json and .log extensions
        for ext in [".json", ".log"]:
            traj_file = player_dir / f"{player_name}_r{round_num}.traj{ext}"
            if traj_file.exists():
                try:
                    data = json.loads(traj_file.read_text())

                    info = data.get("info", {})
                    model_stats = info.get("model_stats", {})

                    # Get diff data from player metadata and changes file
                    diff = None
                    incremental_diff = None
                    modified_files = None
                    diff_by_files = {}
                    incremental_diff_by_files = {}

                    if player_name in self._player_metadata:
                        player_meta = self._player_metadata[player_name]
                        diff = player_meta.get("diff", {}).get(str(round_num), "")

                    # Try to read incremental changes from separate JSON file
                    changes_file = player_dir / f"changes_r{round_num}.json"
                    if changes_file.exists():
                        try:
                            changes_data = json.loads(changes_file.read_text())
                            incremental_diff = changes_data.get("incremental_diff", "")
                            modified_files = changes_data.get("modified_files", {})
                        except (json.JSONDecodeError, KeyError):
                            # Fall back to metadata if changes file is corrupted
                            if player_name in self._player_metadata:
                                player_meta = self._player_metadata[player_name]
                                incremental_diff = player_meta.get("incremental_diff", {}).get(str(round_num), "")
                                modified_files = player_meta.get("modified_files", {}).get(str(round_num), {})
                    else:
                        # todo: Legacy: Remove this at some point after we have migrated
                        # Fall back to metadata if changes file doesn't exist
                        if player_name in self._player_metadata:
                            player_meta = self._player_metadata[player_name]
                            incremental_diff = player_meta.get("incremental_diff", {}).get(str(round_num), "")
                            modified_files = player_meta.get("modified_files", {}).get(str(round_num), {})

                    # Filter and split diffs by files
                    filtered_diff = filter_git_diff(diff) if diff else ""
                    filtered_incremental_diff = filter_git_diff(incremental_diff) if incremental_diff else ""
                    diff_by_files = split_git_diff_by_files(filtered_diff) if filtered_diff else {}
                    incremental_diff_by_files = (
                        split_git_diff_by_files(filtered_incremental_diff) if filtered_incremental_diff else {}
                    )

                    return TrajectoryInfo(
                        player_id=player_name,  # Now stores player name instead of numeric ID
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
                        diff_by_files=diff_by_files,
                        incremental_diff_by_files=incremental_diff_by_files,
                    )
                except (json.JSONDecodeError, KeyError) as e:
                    print(f"Error parsing {traj_file}: {e}")

        return None

    def get_available_trajectories(self) -> list[tuple]:
        """Get list of available trajectory files as (player_name, round_num) tuples"""
        trajectories = []
        players_dir = self.log_dir / "players"

        if not players_dir.exists():
            return trajectories

        # Iterate through player directories
        for player_dir in players_dir.iterdir():
            if not player_dir.is_dir():
                continue

            player_name = player_dir.name

            # Find trajectory files in this player's directory
            for traj_file in player_dir.glob("*_r*.traj.*"):
                # Extract round from filename like gpt5_r2.traj.json
                parts = traj_file.stem.split(".")  # Remove extension
                if parts:
                    name_part = parts[0]  # gpt5_r2
                    try:
                        _, round_part = name_part.split("_")
                        round_num = int(round_part[1:])  # Remove 'r' prefix
                        trajectories.append((player_name, round_num))
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
    for player_name, round_num in available_trajectories:
        if round_num not in trajectories_by_round:
            trajectories_by_round[round_num] = []
        trajectory = parser.parse_trajectory(player_name, round_num)
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


@app.route("/trajectory/<player_name>/<int:round_num>")
def trajectory_detail(player_name: str, round_num: int):
    """Get detailed trajectory data"""
    selected_folder = request.args.get("folder")
    if not selected_folder:
        return jsonify({"error": "No folder specified"})

    logs_dir = LOG_BASE_DIR
    parser = LogParser(logs_dir / selected_folder)
    trajectory = parser.parse_trajectory(player_name, round_num)

    if not trajectory:
        return jsonify({"error": "Trajectory not found"})

    return render_template("trajectory.html", trajectory=trajectory)


# Use run_viewer.py to launch the application
