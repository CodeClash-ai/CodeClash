#!/usr/bin/env python3
"""
Trajectory Viewer for AI Agent Benchmark

A Flask-based web application to visualize AI agent game trajectories
"""

import json
import logging
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, redirect, render_template, request, send_file, url_for

from codeclash.ratings.significance import calculate_p_value
from codeclash.tournaments.utils.git_utils import filter_git_diff, split_git_diff_by_files

logger = logging.getLogger(__name__)

# Global variable to store the directory to search for logs
LOG_BASE_DIR = Path.cwd() / "logs"

# Global flag to indicate if we're running in static mode
STATIC_MODE = False


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


def set_static_mode(enabled: bool = True):
    """Enable or disable static mode"""
    global STATIC_MODE
    STATIC_MODE = enabled


def is_static_mode() -> bool:
    """Check if we're running in static mode"""
    return STATIC_MODE


def is_game_folder(log_dir: Path) -> bool:
    """Check if a directory contains metadata.json and is therefore a game folder"""
    metadata_file = log_dir / "metadata.json"
    return metadata_file.exists()


def load_metadata(log_dir: Path) -> dict[str, Any] | None:
    """Load metadata.json from log directory"""
    metadata_file = log_dir / "metadata.json"
    if not metadata_file.exists():
        return None

    try:
        return json.loads(metadata_file.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def get_round_count_from_metadata(log_dir: Path) -> tuple[int, int] | None:
    """Extract round count from metadata.json

    Returns:
        tuple[int, int] | None: (completed_rounds, total_rounds) or None if not available
    """
    metadata = load_metadata(log_dir)
    if not metadata:
        return None

    total_rounds = metadata.get("config", {}).get("tournament", {}).get("rounds")

    # Count completed rounds from round_stats (excluding round 0 which is warmup)
    round_stats = metadata.get("round_stats", {})
    completed_rounds = sum(1 for round_key in round_stats.keys() if int(round_key) > 0)

    if total_rounds is not None:
        return (completed_rounds, total_rounds)
    return None


def get_models_from_metadata(log_dir: Path) -> list[str]:
    """Extract model names from metadata.json if it exists"""
    metadata = load_metadata(log_dir)
    if not metadata:
        return []

    players_config = metadata.get("config", {}).get("players", [])
    models = []
    for player_config in players_config:
        if isinstance(player_config, dict):
            model_name = player_config.get("config", {}).get("model", {}).get("model_name")
            if model_name and model_name not in models:
                models.append(model_name)
    return models


def get_readme_first_line(log_dir: Path) -> str:
    """Extract the first line from readme.txt if it exists"""
    readme_file = log_dir / "readme.txt"
    if not readme_file.exists():
        return ""

    try:
        content = readme_file.read_text().strip()
        if not content:
            return ""
        # Get the first non-empty line
        for line in content.split("\n"):
            line = line.strip()
            if line:
                return line
        return ""
    except (OSError, UnicodeDecodeError):
        return ""


def get_agent_info_from_metadata(metadata: dict[str, Any]) -> list[AgentInfo]:
    """Extract detailed agent information from metadata"""
    agents = []
    players_config = metadata.get("config", {}).get("players", [])

    for player_config in players_config:
        if isinstance(player_config, dict):
            name = player_config.get("name", "unknown")
            config = player_config.get("config", {})
            model_name = (
                config.get("model", {}).get("model_name")
                if isinstance(config.get("model"), dict)
                else config.get("model")
            )
            agent_class = config.get("agent_class")
            agents.append(AgentInfo(name=name, model_name=model_name, agent_class=agent_class))

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
                        round_info = get_round_count_from_metadata(item)
                        models = get_models_from_metadata(item)
                        readme_first_line = get_readme_first_line(item)
                        game_folders.add(current_relative)
                        all_folders.append(
                            {
                                "name": current_relative,
                                "full_path": str(item),
                                "round_info": round_info,  # Now stores (completed, total) tuple or None
                                "models": models,
                                "readme_first_line": readme_first_line,
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
                                "round_info": None,
                                "models": [],
                                "readme_first_line": "",
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
    all_logs: dict[str, dict[str, str]] | None = None  # {log_type: {"content": content, "path": path}}


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
            logger.warning(f"Players {sorted(missing_players)} not found in round results, adding with 0 wins")
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
            logger.debug(f"Calculating p-value for scores: {dict(sorted(scores.items()))}")
            p_value = calculate_p_value(scores)
            logger.debug(f"P-value result: {p_value} (rounded: {round(p_value, 2)})")
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

    def parse_game_metadata(self) -> GameMetadata:
        """Parse overall game metadata"""
        # Load metadata.json
        results = load_metadata(self.log_dir)
        if not results:
            results = {"status": "No metadata file found"}
            metadata_file_path = ""
        else:
            metadata_file_path = str(self.log_dir / "metadata.json")

        # Parse tournament.log if it exists
        main_log_file = self.log_dir / "tournament.log"
        main_log = main_log_file.read_text() if main_log_file.exists() else "No tournament log found"
        main_log_path = str(main_log_file) if main_log_file.exists() else ""

        # Parse all available logs
        all_logs = self._parse_all_logs()

        # Parse round data from metadata.json round_stats
        rounds = []
        if "round_stats" in results:
            # Get agent info for processing round results
            agent_info = get_agent_info_from_metadata(results)

            # Process each round from round_stats
            for round_key, round_data in results["round_stats"].items():
                round_num = int(round_key)
                round_results = process_round_results(round_data, agent_info)
                rounds.append({"round_num": round_num, "sim_logs": [], "results": round_results})

        # Sort rounds by round number to ensure consistent ordering
        rounds.sort(key=lambda x: x["round_num"])

        # Extract agent information
        agent_info = get_agent_info_from_metadata(results)

        return GameMetadata(
            results=results,
            main_log=main_log,
            main_log_path=main_log_path,
            metadata_file_path=metadata_file_path,
            rounds=rounds,
            agent_info=agent_info,
            all_logs=all_logs,
        )

    def parse_trajectory(self, player_name: str, round_num: int) -> TrajectoryInfo | None:
        """Parse a specific trajectory file"""
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

                    # Get diff data from changes file
                    diff = incremental_diff = modified_files = None
                    changes_file = player_dir / f"changes_r{round_num}.json"
                    if changes_file.exists():
                        try:
                            changes_data = json.loads(changes_file.read_text())
                            diff = changes_data.get("full_diff", "")
                            incremental_diff = changes_data.get("incremental_diff", "")
                            modified_files = changes_data.get("modified_files", {})
                        except (json.JSONDecodeError, KeyError):
                            pass

                    # Filter and split diffs by files
                    filtered_diff = filter_git_diff(diff) if diff else ""
                    filtered_incremental_diff = filter_git_diff(incremental_diff) if incremental_diff else ""
                    diff_by_files = split_git_diff_by_files(filtered_diff) if filtered_diff else {}
                    incremental_diff_by_files = (
                        split_git_diff_by_files(filtered_incremental_diff) if filtered_incremental_diff else {}
                    )

                    return TrajectoryInfo(
                        player_id=player_name,
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
                    logger.error(f"Error parsing {traj_file}: {e}", exc_info=True)

        return None

    def get_available_trajectories(self) -> list[tuple]:
        """Get list of available trajectory files as (player_name, round_num) tuples using metadata"""
        metadata = self.parse_game_metadata()

        # Get player names from agent_info
        player_names = [agent.name for agent in metadata.agent_info] if metadata.agent_info else []

        # Get round numbers from rounds data
        round_nums = [round_data["round_num"] for round_data in metadata.rounds]

        # Generate all possible (player_name, round_num) combinations
        return sorted((player_name, round_num) for player_name in player_names for round_num in round_nums)

    def analyze_line_counts(self) -> dict[str, Any]:
        """Analyze line counts across all rounds for all files that appear in changed files"""
        # Collect all files that appear in any changed files across all rounds and players
        all_files = set()
        players_dir = self.log_dir / "players"

        if not players_dir.exists():
            return {"all_files": [], "line_counts_by_round": {}}

        # First pass: collect all files from all changes_r*.json files
        for player_dir in players_dir.iterdir():
            if not player_dir.is_dir():
                continue

            for changes_file in player_dir.glob("changes_r*.json"):
                try:
                    changes_data = json.loads(changes_file.read_text())
                    modified_files = changes_data.get("modified_files", {})
                    all_files.update(modified_files.keys())
                except (json.JSONDecodeError, KeyError):
                    continue

        all_files_list = sorted(list(all_files))

        # Second pass: count lines for each file in each round for each player
        line_counts_by_round = {}

        for player_dir in players_dir.iterdir():
            if not player_dir.is_dir():
                continue

            player_name = player_dir.name

            # Get all rounds for this player
            changes_files = sorted(player_dir.glob("changes_r*.json"), key=lambda x: int(x.stem.split("_r")[1]))

            # Track line counts for this player across rounds
            player_line_counts = {}
            current_file_lines = {}  # Track current state of each file

            for changes_file in changes_files:
                try:
                    round_num = int(changes_file.stem.split("_r")[1])
                    changes_data = json.loads(changes_file.read_text())
                    modified_files = changes_data.get("modified_files", {})

                    # Update line counts for files that changed in this round
                    for file_path, file_content in modified_files.items():
                        if file_content:
                            current_file_lines[file_path] = len(file_content.splitlines())

                    # Record line counts for all files in this round
                    round_line_counts = {}
                    for file_path in all_files_list:
                        round_line_counts[file_path] = current_file_lines.get(file_path, 0)

                    player_line_counts[round_num] = round_line_counts

                except (json.JSONDecodeError, KeyError, ValueError):
                    continue

            if player_line_counts:
                line_counts_by_round[player_name] = player_line_counts

        return {"all_files": all_files_list, "line_counts_by_round": line_counts_by_round}

    def analyze_sim_wins_per_round(self) -> dict[str, Any]:
        """Analyze scores per round for each competitor from round_stats in metadata.json.
        Scores are calculated as wins + 0.5*ties, same as in the table."""
        metadata = load_metadata(self.log_dir)
        if not metadata:
            return {"players": [], "rounds": [], "scores_by_player": {}}

        round_stats = metadata.get("round_stats", {})
        # Collect all player names from all rounds
        player_names = set()
        for round_data in round_stats.values():
            scores = round_data.get("scores", {})
            player_names.update([k for k in scores.keys() if k != "Tie"])
        player_names = sorted(player_names)

        # Collect all round numbers (sorted)
        round_nums = sorted([int(k) for k in round_stats.keys()])

        # Build scores_by_player: {player: [scores_per_round]}
        # Scores = (wins + 0.5*ties) / total_games * 100 (percentage, same as in process_round_results)
        scores_by_player = {p: [] for p in player_names}
        for round_num in round_nums:
            round_data = round_stats.get(str(round_num), {})
            scores = round_data.get("scores", {})
            ties = scores.get("Tie", 0)
            total_games = sum(scores.values())

            for p in player_names:
                wins = scores.get(p, 0)
                if total_games > 0:
                    # Calculate score as percentage: (wins + 0.5*ties) / total_games * 100
                    player_score = ((wins + 0.5 * ties) / total_games) * 100
                else:
                    player_score = 0
                scores_by_player[p].append(round(player_score, 1))

        return {
            "players": player_names,
            "rounds": round_nums,
            "scores_by_player": scores_by_player,
        }

    def load_matrix_analysis(self) -> dict[str, Any] | None:
        """Load and process matrix.json if it exists"""
        matrix_file = self.log_dir / "matrix.json"
        if not matrix_file.exists():
            return None

        try:
            matrix_data = json.loads(matrix_file.read_text())
            matrices = matrix_data.get("matrices", {})
            processed_matrices = {}

            for matrix_name, matrix in matrices.items():
                processed_matrix = {"name": matrix_name, "data": {}, "max_rounds": 0}

                # Extract base player name from matrix name
                base_player_name = matrix_name.split("_vs_")[0] if "_vs_" in matrix_name else None

                # Determine matrix dimensions
                max_i = max_j = 0
                for i_str in matrix.keys():
                    i = int(i_str)
                    max_i = max(max_i, i)
                    for j_str in matrix[i_str].keys():
                        j = int(j_str)
                        max_j = max(max_j, j)

                processed_matrix["max_rounds"] = max(max_i, max_j)

                # Process each cell
                for i_str in matrix.keys():
                    i = int(i_str)
                    processed_matrix["data"][i] = {}

                    for j_str in matrix[i_str].keys():
                        j = int(j_str)
                        cell_data = matrix[i_str][j_str]
                        scores = cell_data.get("scores", {})

                        # Calculate win percentage from row player perspective
                        row_player_name = f"{base_player_name}_r{i}" if base_player_name else None
                        if row_player_name and row_player_name in scores:
                            row_player_score = scores.get(row_player_name, 0)
                            total_games = sum(scores.values())
                            ties = scores.get("Tie", 0)
                            win_percentage = (
                                ((row_player_score + 0.5 * ties) / total_games) * 100 if total_games > 0 else 0
                            )
                        else:
                            win_percentage = 0

                        processed_matrix["data"][i][j] = {
                            "win_percentage": round(win_percentage, 1),
                            "scores": scores,
                            "winner": cell_data.get("winner"),
                            "total_games": sum(scores.values()) if scores else 0,
                        }

                processed_matrices[matrix_name] = processed_matrix

            return {
                "matrices": processed_matrices,
                "metadata": {
                    "p1_name": matrix_data.get("p1_name"),
                    "p2_name": matrix_data.get("p2_name"),
                    "rounds": matrix_data.get("rounds"),
                    "n_repetitions": matrix_data.get("n_repetitions"),
                },
            }

        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Error loading matrix.json: {e}", exc_info=True)
            return None

    def _parse_all_logs(self) -> dict[str, dict[str, str]]:
        """Parse all available log files in the tournament directory"""
        all_logs = {}

        # Define log files to look for
        log_files = {"tournament.log": "Tournament Log", "game.log": "Game Log", "everything.log": "Everything Log"}

        # Check for main log files
        for log_file, display_name in log_files.items():
            log_path = self.log_dir / log_file
            if log_path.exists():
                try:
                    content = log_path.read_text()
                    all_logs[display_name] = {"content": content, "path": str(log_path)}
                except (OSError, UnicodeDecodeError) as e:
                    all_logs[display_name] = {"content": f"Error reading log file: {e}", "path": str(log_path)}

        # Check for player logs
        players_dir = self.log_dir / "players"
        if players_dir.exists():
            for player_dir in players_dir.iterdir():
                if not player_dir.is_dir():
                    continue

                player_name = player_dir.name
                player_log = player_dir / "player.log"

                if player_log.exists():
                    try:
                        content = player_log.read_text()
                        display_name = f"Player {player_name} Log"
                        all_logs[display_name] = {"content": content, "path": str(player_log)}
                    except (OSError, UnicodeDecodeError) as e:
                        display_name = f"Player {player_name} Log"
                        all_logs[display_name] = {"content": f"Error reading log file: {e}", "path": str(player_log)}

        return all_logs


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


def render_game_viewer(folder_path: Path, selected_folder: str) -> str:
    """Common logic for rendering game viewer pages"""
    # Parse the selected game
    parser = LogParser(folder_path)
    metadata = parser.parse_game_metadata()

    # Group trajectories by round
    trajectories_by_round = {}
    for player_name, round_num in parser.get_available_trajectories():
        if round_num not in trajectories_by_round:
            trajectories_by_round[round_num] = []
        trajectory = parser.parse_trajectory(player_name, round_num)
        if trajectory:
            trajectories_by_round[round_num].append(trajectory)

    # Get analysis data
    analysis_data = parser.analyze_line_counts()
    sim_wins_data = parser.analyze_sim_wins_per_round()
    matrix_data = parser.load_matrix_analysis()

    return render_template(
        "index.html",
        selected_folder=selected_folder,
        selected_folder_path=str(folder_path),
        metadata=metadata,
        trajectories_by_round=trajectories_by_round,
        analysis_data=analysis_data,
        sim_wins_data=sim_wins_data,
        matrix_data=matrix_data,
        is_static=STATIC_MODE,
    )


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
    folder_path = LOG_BASE_DIR / selected_folder

    if not folder_path.exists() or not is_game_folder(folder_path):
        return redirect(url_for("game_picker"))

    return render_game_viewer(folder_path, selected_folder)


@app.route("/game/<path:folder_path>")
def game_view(folder_path):
    """Static-friendly game viewer route using path parameters"""
    # Validate the selected folder exists and is a game folder
    folder_path_obj = LOG_BASE_DIR / folder_path

    if not folder_path_obj.exists() or not is_game_folder(folder_path_obj):
        return redirect(url_for("game_picker"))

    return render_game_viewer(folder_path_obj, folder_path)


@app.route("/picker")
def game_picker():
    """Game picker page with recursive folder support"""
    logs_dir = LOG_BASE_DIR
    game_folders = find_all_game_folders(logs_dir)

    return render_template("picker.html", game_folders=game_folders, base_dir=str(logs_dir), is_static=STATIC_MODE)


@app.route("/delete-experiment", methods=["POST"])
def delete_experiment():
    """Delete an experiment folder"""
    try:
        data = request.get_json()
        folder_path = data.get("folder_path")

        if not folder_path:
            return jsonify({"success": False, "error": "No folder path provided"})

        # Convert to Path object and validate it's within our logs directory
        folder_path_obj = Path(folder_path)

        # Ensure the path exists and is a directory
        if not folder_path_obj.exists():
            return jsonify({"success": False, "error": "Folder does not exist"})

        if not folder_path_obj.is_dir():
            return jsonify({"success": False, "error": "Path is not a directory"})

        # Security check: ensure the path is within our expected logs directory
        try:
            # Check if it's a subdirectory of LOG_BASE_DIR
            folder_path_obj.relative_to(LOG_BASE_DIR)
        except ValueError:
            return jsonify({"success": False, "error": "Invalid folder path"})

        # Delete the folder
        shutil.rmtree(folder_path_obj)

        return jsonify({"success": True, "message": "Experiment deleted successfully"})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/save-readme", methods=["POST"])
def save_readme():
    """Save readme content to readme.txt in the experiment folder"""
    try:
        data = request.get_json()
        selected_folder = data.get("selected_folder")
        content = data.get("content", "")

        if not selected_folder:
            return jsonify({"success": False, "error": "No folder specified"})

        # Get the folder path
        folder_path = LOG_BASE_DIR / selected_folder

        if not folder_path.exists() or not folder_path.is_dir():
            return jsonify({"success": False, "error": "Invalid folder"})

        # Save to readme.txt
        readme_file = folder_path / "readme.txt"
        readme_file.write_text(content)

        return jsonify({"success": True, "message": "Readme saved successfully"})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/load-readme")
def load_readme():
    """Load readme content from readme.txt in the experiment folder"""
    try:
        selected_folder = request.args.get("folder")

        if not selected_folder:
            return jsonify({"success": False, "error": "No folder specified"})

        # Get the folder path
        folder_path = LOG_BASE_DIR / selected_folder

        if not folder_path.exists() or not folder_path.is_dir():
            return jsonify({"success": False, "error": "Invalid folder"})

        # Load from readme.txt
        readme_file = folder_path / "readme.txt"
        content = ""

        if readme_file.exists():
            content = readme_file.read_text()

        return jsonify({"success": True, "content": content})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/rename-folders", methods=["POST"])
def rename_folders():
    """Add suffix to selected folders"""
    try:
        data = request.get_json()
        action = data.get("action")
        paths = data.get("paths", [])
        suffix = data.get("suffix", "")

        if not paths:
            return jsonify({"success": False, "error": "No paths provided"})

        if action != "add-suffix":
            return jsonify({"success": False, "error": "Invalid action"})

        if not suffix:
            return jsonify({"success": False, "error": "No suffix provided"})

        successful_renames = []
        failed_renames = []

        for relative_path in paths:
            try:
                # Get the full path
                old_path = LOG_BASE_DIR / relative_path

                if not old_path.exists():
                    failed_renames.append(f"{relative_path}: does not exist")
                    continue

                # Create new path with suffix
                parent_dir = old_path.parent
                old_name = old_path.name
                new_name = f"{old_name}.{suffix}"
                new_path = parent_dir / new_name

                # Check if target already exists
                if new_path.exists():
                    failed_renames.append(f"{relative_path}: target already exists")
                    continue

                # Perform the rename
                old_path.rename(new_path)
                successful_renames.append(f"{relative_path} → {old_name}.{suffix}")

            except Exception as e:
                failed_renames.append(f"{relative_path}: {str(e)}")

        if failed_renames:
            error_msg = "Some renames failed:\n" + "\n".join(failed_renames)
            if successful_renames:
                error_msg += "\n\nSuccessful renames:\n" + "\n".join(successful_renames)
            return jsonify({"success": False, "error": error_msg})

        return jsonify(
            {
                "success": True,
                "message": f"Successfully renamed {len(successful_renames)} folder(s)",
                "renamed": successful_renames,
            }
        )

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/move-to-subfolder", methods=["POST"])
def move_to_subfolder():
    """Move selected folders to a new subfolder"""
    try:
        data = request.get_json()
        paths = data.get("paths", [])
        subfolder_name = data.get("subfolder", "")

        if not paths:
            return jsonify({"success": False, "error": "No paths provided"})

        if not subfolder_name:
            return jsonify({"success": False, "error": "No subfolder name provided"})

        # Validate subfolder name (no path separators, etc.)
        if "/" in subfolder_name or "\\" in subfolder_name or ".." in subfolder_name:
            return jsonify({"success": False, "error": "Invalid subfolder name"})

        successful_moves = []
        failed_moves = []

        for relative_path in paths:
            try:
                # Get the full path
                old_path = LOG_BASE_DIR / relative_path

                if not old_path.exists():
                    failed_moves.append(f"{relative_path}: does not exist")
                    continue

                # Determine where to create the subfolder
                parent_dir = old_path.parent
                subfolder_path = parent_dir / subfolder_name

                # Create subfolder if it doesn't exist
                subfolder_path.mkdir(exist_ok=True)

                # Create new path inside subfolder
                folder_name = old_path.name
                new_path = subfolder_path / folder_name

                # Check if target already exists
                if new_path.exists():
                    failed_moves.append(f"{relative_path}: target already exists in subfolder")
                    continue

                # Perform the move
                old_path.rename(new_path)

                # Calculate the new relative path for display
                new_relative_path = str(new_path.relative_to(LOG_BASE_DIR))
                successful_moves.append(f"{relative_path} → {new_relative_path}")

            except Exception as e:
                failed_moves.append(f"{relative_path}: {str(e)}")

        if failed_moves:
            error_msg = "Some moves failed:\n" + "\n".join(failed_moves)
            if successful_moves:
                error_msg += "\n\nSuccessful moves:\n" + "\n".join(successful_moves)
            return jsonify({"success": False, "error": error_msg})

        return jsonify(
            {
                "success": True,
                "message": f"Successfully moved {len(successful_moves)} folder(s) to subfolder '{subfolder_name}'",
                "moved": successful_moves,
            }
        )

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/move-folder", methods=["POST"])
def move_folder():
    """Move/rename a single folder to a new path"""
    try:
        data = request.get_json()
        old_path = data.get("old_path", "")
        new_path = data.get("new_path", "")

        if not old_path:
            return jsonify({"success": False, "error": "No old path provided"})

        if not new_path:
            return jsonify({"success": False, "error": "No new path provided"})

        # Convert to Path objects relative to LOG_BASE_DIR
        old_full_path = LOG_BASE_DIR / old_path
        new_full_path = LOG_BASE_DIR / new_path

        # Validate old path exists
        if not old_full_path.exists():
            return jsonify({"success": False, "error": "Source folder does not exist"})

        # Validate new path doesn't already exist
        if new_full_path.exists():
            return jsonify({"success": False, "error": "Target path already exists"})

        # Security check: ensure both paths are within our expected logs directory
        try:
            old_full_path.relative_to(LOG_BASE_DIR)
            new_full_path.relative_to(LOG_BASE_DIR)
        except ValueError:
            return jsonify({"success": False, "error": "Invalid path - must be within logs directory"})

        # Create intermediate directories if necessary
        new_full_path.parent.mkdir(parents=True, exist_ok=True)

        # Perform the move
        old_full_path.rename(new_full_path)

        return jsonify(
            {
                "success": True,
                "message": f"Successfully moved folder from '{old_path}' to '{new_path}'",
                "old_path": old_path,
                "new_path": new_path,
            }
        )

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/analysis/line-counts")
def analysis_line_counts():
    """Get line count analysis data for the current game"""
    selected_folder = request.args.get("folder")

    if not selected_folder:
        return jsonify({"success": False, "error": "No folder specified"})

    # Validate the selected folder exists and is a game folder
    logs_dir = LOG_BASE_DIR
    folder_path = logs_dir / selected_folder

    if not folder_path.exists() or not is_game_folder(folder_path):
        return jsonify({"success": False, "error": "Invalid folder"})

    try:
        parser = LogParser(folder_path)
        analysis_data = parser.analyze_line_counts()

        return jsonify({"success": True, "data": analysis_data})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/download-file")
def download_file():
    """Download a file with proper security checks"""
    file_path = request.args.get("path")

    if not file_path:
        return jsonify({"success": False, "error": "No file path provided"}), 400

    try:
        # Convert to Path object
        file_path_obj = Path(file_path)

        # Security check: ensure the file exists
        if not file_path_obj.exists():
            return jsonify({"success": False, "error": "File does not exist"}), 404

        # Security check: ensure the file is not a directory
        if not file_path_obj.is_file():
            return jsonify({"success": False, "error": "Path is not a file"}), 400

        # Security check: ensure the path is within our expected logs directory
        try:
            file_path_obj.relative_to(LOG_BASE_DIR)
        except ValueError:
            return jsonify({"success": False, "error": "Invalid file path"}), 403

        # Send the file as an attachment
        return send_file(file_path_obj, as_attachment=True, download_name=file_path_obj.name)

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# Use run_viewer.py to launch the application
