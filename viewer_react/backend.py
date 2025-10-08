#!/usr/bin/env python3
"""
React-based CodeClash Trajectory Viewer Backend API

A clean Flask REST API for the React frontend.
"""

import json
import logging
import shutil
from dataclasses import dataclass
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

from codeclash.analysis.significance import calculate_p_value
from codeclash.tournaments.utils.git_utils import filter_git_diff, split_git_diff_by_files

logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder="frontend/dist", static_url_path="")
CORS(app)

LOG_BASE_DIR = Path.cwd() / "logs"


def set_log_base_directory(directory: str | Path):
    """Set the logs directory"""
    global LOG_BASE_DIR
    LOG_BASE_DIR = Path(directory).resolve()


@dataclass
class GameFolder:
    """Information about a game folder"""

    name: str
    full_path: str
    is_game: bool
    game_name: str = ""
    models: list[str] | None = None
    rounds_completed: int | None = None
    rounds_total: int | None = None
    created_timestamp: float | None = None


def load_metadata(log_dir: Path) -> dict:
    """Load metadata.json from log directory"""
    metadata_file = log_dir / "metadata.json"
    if not metadata_file.exists():
        return {}

    try:
        return json.loads(metadata_file.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def get_nested(data: dict, path: str, default=None):
    """Get value from nested dictionary using dot notation"""
    current = data
    for key in path.split("."):
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return default
    return current


def is_game_folder(log_dir: Path) -> bool:
    """Check if directory contains metadata.json"""
    return (log_dir / "metadata.json").exists()


def find_all_game_folders() -> list[dict]:
    """Recursively find all game folders and intermediate folders"""
    all_folders = []
    game_folders = set()

    def scan_directory(directory: Path, relative_path: str = ""):
        if not directory.exists() or not directory.is_dir():
            return

        try:
            for item in sorted(directory.iterdir()):
                if not item.is_dir():
                    continue

                current_relative = f"{relative_path}/{item.name}" if relative_path else item.name
                depth = current_relative.count("/")

                if is_game_folder(item):
                    metadata = load_metadata(item)

                    # Extract info from metadata
                    game_name = get_nested(metadata, "config.game.name") or get_nested(metadata, "game.name", "")

                    # Get models
                    players_config = get_nested(metadata, "config.players", [])
                    models = []
                    for player_config in players_config:
                        if isinstance(player_config, dict):
                            config = player_config.get("config", {})
                            model_name = (
                                config.get("model", {}).get("model_name")
                                if isinstance(config.get("model"), dict)
                                else config.get("model")
                            )
                            if model_name and model_name not in models:
                                models.append(model_name)

                    # Get round info
                    total_rounds = get_nested(metadata, "config.tournament.rounds")
                    round_stats = get_nested(metadata, "round_stats", {})
                    completed_rounds = sum(1 for round_key in round_stats.keys() if int(round_key) > 0)

                    game_folders.add(current_relative)
                    all_folders.append(
                        {
                            "name": current_relative,
                            "full_path": str(item),
                            "is_game": True,
                            "game_name": game_name,
                            "models": models,
                            "rounds_completed": completed_rounds if total_rounds else None,
                            "rounds_total": total_rounds,
                            "created_timestamp": get_nested(metadata, "created_timestamp"),
                            "depth": depth,
                            "parent": relative_path if relative_path else None,
                        }
                    )
                else:
                    # Add intermediate folder
                    all_folders.append(
                        {
                            "name": current_relative,
                            "full_path": str(item),
                            "is_game": False,
                            "game_name": "",
                            "models": [],
                            "rounds_completed": None,
                            "rounds_total": None,
                            "created_timestamp": None,
                            "depth": depth,
                            "parent": relative_path if relative_path else None,
                        }
                    )

                # Recursively scan
                scan_directory(item, current_relative)
        except (PermissionError, OSError):
            pass

    scan_directory(LOG_BASE_DIR)

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


def process_round_results(round_results: dict, agent_names: list[str]) -> dict:
    """Process round results to add computed fields"""
    if not round_results:
        return round_results

    processed = round_results.copy()
    scores = round_results.get("scores", {}).copy()

    # Ensure all expected players are in scores
    for name in agent_names:
        if name not in scores:
            scores[name] = 0

    scores = dict(sorted(scores.items()))
    processed["scores"] = scores

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
                processed["winner_percentage"] = None

            p_value = calculate_p_value(scores)
            processed["p_value"] = round(p_value, 2)
        else:
            processed["winner_percentage"] = None
            processed["p_value"] = None

    return processed


# ==================== API Endpoints ====================


@app.route("/")
def index():
    """Serve the React app"""
    return send_from_directory(app.static_folder, "index.html")


@app.route("/api/folders")
def api_folders():
    """Get all available game folders"""
    try:
        folders = find_all_game_folders()
        return jsonify({"success": True, "folders": folders})
    except Exception as e:
        logger.error(f"Error fetching folders: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


def get_navigation_info(selected_folder: str) -> dict:
    """Get previous and next game folders for navigation"""
    game_folders = find_all_game_folders()
    game_names = [folder["name"] for folder in game_folders if folder["is_game"]]
    game_names.sort()

    try:
        current_index = game_names.index(selected_folder)
    except ValueError:
        return {"previous": None, "next": None}

    previous_game = game_names[current_index - 1] if current_index > 0 else None
    next_game = game_names[current_index + 1] if current_index < len(game_names) - 1 else None

    return {"previous": previous_game, "next": next_game}


@app.route("/api/game/<path:folder_path>")
def api_game(folder_path):
    """Get game metadata and overview"""
    try:
        folder = LOG_BASE_DIR / folder_path

        if not folder.exists() or not is_game_folder(folder):
            return jsonify({"success": False, "error": "Game folder not found"}), 404

        metadata = load_metadata(folder)

        # Extract agent info
        players_config = get_nested(metadata, "config.players", [])
        agents = []
        for player_config in players_config:
            if isinstance(player_config, dict):
                name = player_config.get("name", "unknown")
                config = player_config.get("config", {})
                model_info = config.get("model", {})
                model_name = model_info.get("model_name") if isinstance(model_info, dict) else model_info
                agent_class = config.get("agent_class")
                agents.append(
                    {
                        "name": name,
                        "model_name": model_name,
                        "agent_class": agent_class,
                    }
                )

        agent_names = [agent["name"] for agent in agents]

        # Process rounds
        round_stats = get_nested(metadata, "round_stats", {})
        rounds = []
        for round_key, round_data in round_stats.items():
            round_num = int(round_key)
            processed_results = process_round_results(round_data, agent_names)
            rounds.append(
                {
                    "round_num": round_num,
                    "results": processed_results,
                }
            )

        rounds.sort(key=lambda x: x["round_num"])

        # Get navigation info
        navigation = get_navigation_info(folder_path)

        return jsonify(
            {
                "success": True,
                "metadata": metadata,
                "agents": agents,
                "rounds": rounds,
                "navigation": navigation,
            }
        )

    except Exception as e:
        logger.error(f"Error fetching game data: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/trajectory/<path:folder_path>/<player_name>/<int:round_num>")
def api_trajectory(folder_path, player_name, round_num):
    """Get trajectory data for a specific player and round"""
    try:
        folder = LOG_BASE_DIR / folder_path

        if not folder.exists() or not is_game_folder(folder):
            logger.warning(f"Game folder not found: {folder}")
            return jsonify({"success": False, "error": "Game folder not found"}), 404

        player_dir = folder / "players" / player_name
        traj_file = player_dir / f"{player_name}_r{round_num}.traj.json"

        if not traj_file.exists():
            logger.warning(f"Trajectory file not found: {traj_file}")
            # List available trajectory files for debugging
            if player_dir.exists():
                available = list(player_dir.glob(f"{player_name}_r*.traj.json"))
                logger.info(f"Available trajectories for {player_name}: {[f.name for f in available]}")
            return jsonify({"success": False, "error": f"Trajectory not found for round {round_num}"}), 404

        traj_data = json.loads(traj_file.read_text())
        info = traj_data.get("info", {})
        model_stats = info.get("model_stats", {})

        # Get diff data
        diff = incremental_diff = None
        diff_by_files = incremental_diff_by_files = None
        modified_files = None

        changes_file = player_dir / f"changes_r{round_num}.json"
        if changes_file.exists():
            try:
                changes_data = json.loads(changes_file.read_text())
                diff = changes_data.get("full_diff", "")
                incremental_diff = changes_data.get("incremental_diff", "")
                modified_files = changes_data.get("modified_files", {})

                filtered_diff = filter_git_diff(diff) if diff else ""
                filtered_incremental_diff = filter_git_diff(incremental_diff) if incremental_diff else ""
                diff_by_files = split_git_diff_by_files(filtered_diff) if filtered_diff else {}
                incremental_diff_by_files = (
                    split_git_diff_by_files(filtered_incremental_diff) if filtered_incremental_diff else {}
                )
            except (json.JSONDecodeError, KeyError):
                pass

        # Get valid_submission from metadata
        metadata = load_metadata(folder)
        round_stats = get_nested(metadata, f"round_stats.{round_num}", {})
        player_stats = get_nested(round_stats, f"player_stats.{player_name}", {})
        valid_submission = player_stats.get("valid_submit")

        return jsonify(
            {
                "success": True,
                "trajectory": {
                    "player_name": player_name,
                    "round_num": round_num,
                    "api_calls": model_stats.get("api_calls", 0),
                    "cost": model_stats.get("instance_cost", 0.0),
                    "exit_status": info.get("exit_status"),
                    "submission": info.get("submission"),
                    "memory": info.get("memory"),
                    "messages": traj_data.get("messages", []),
                    "diff": diff,
                    "incremental_diff": incremental_diff,
                    "diff_by_files": diff_by_files,
                    "incremental_diff_by_files": incremental_diff_by_files,
                    "modified_files": modified_files,
                    "valid_submission": valid_submission,
                },
            }
        )

    except Exception as e:
        logger.error(f"Error fetching trajectory: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/analysis/line-counts/<path:folder_path>")
def api_line_counts(folder_path):
    """Get line count analysis for a game"""
    try:
        folder = LOG_BASE_DIR / folder_path

        if not folder.exists() or not is_game_folder(folder):
            return jsonify({"success": False, "error": "Game folder not found"}), 404

        players_dir = folder / "players"

        if not players_dir.exists():
            return jsonify({"success": True, "all_files": [], "line_counts_by_round": {}})

        # Collect all files
        all_files = set()
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

        # Count lines for each file in each round for each player
        line_counts_by_round = {}

        for player_dir in players_dir.iterdir():
            if not player_dir.is_dir():
                continue

            player_name = player_dir.name
            changes_files = sorted(player_dir.glob("changes_r*.json"), key=lambda x: int(x.stem.split("_r")[1]))

            player_line_counts = {}
            current_file_lines = {}

            for changes_file in changes_files:
                try:
                    round_num = int(changes_file.stem.split("_r")[1])
                    changes_data = json.loads(changes_file.read_text())
                    modified_files = changes_data.get("modified_files", {})

                    for file_path, file_content in modified_files.items():
                        if file_content:
                            current_file_lines[file_path] = len(file_content.splitlines())

                    round_line_counts = {
                        file_path: current_file_lines.get(file_path, 0) for file_path in all_files_list
                    }
                    player_line_counts[round_num] = round_line_counts

                except (json.JSONDecodeError, KeyError, ValueError):
                    continue

            if player_line_counts:
                line_counts_by_round[player_name] = player_line_counts

        return jsonify(
            {
                "success": True,
                "all_files": all_files_list,
                "line_counts_by_round": line_counts_by_round,
            }
        )

    except Exception as e:
        logger.error(f"Error analyzing line counts: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/analysis/sim-wins/<path:folder_path>")
def api_sim_wins(folder_path):
    """Get simulation wins per round"""
    try:
        folder = LOG_BASE_DIR / folder_path

        if not folder.exists() or not is_game_folder(folder):
            return jsonify({"success": False, "error": "Game folder not found"}), 404

        metadata = load_metadata(folder)
        round_stats = get_nested(metadata, "round_stats", {})

        # Collect all player names
        player_names = set()
        for round_data in round_stats.values():
            scores = round_data.get("scores", {})
            player_names.update([k for k in scores.keys() if k != "Tie"])
        player_names = sorted(player_names)

        # Collect all round numbers
        round_nums = sorted([int(k) for k in round_stats.keys()])

        # Build scores by player
        scores_by_player = {p: [] for p in player_names}
        for round_num in round_nums:
            round_data = round_stats.get(str(round_num), {})
            scores = round_data.get("scores", {})
            ties = scores.get("Tie", 0)
            total_games = sum(scores.values())

            for p in player_names:
                wins = scores.get(p, 0)
                if total_games > 0:
                    player_score = ((wins + 0.5 * ties) / total_games) * 100
                else:
                    player_score = 0
                scores_by_player[p].append(round(player_score, 1))

        return jsonify(
            {
                "success": True,
                "players": player_names,
                "rounds": round_nums,
                "scores_by_player": scores_by_player,
            }
        )

    except Exception as e:
        logger.error(f"Error analyzing sim wins: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/delete-folder", methods=["POST"])
def api_delete_folder():
    """Delete a game folder"""
    try:
        data = request.get_json()
        folder_path = data.get("folder_path")

        if not folder_path:
            return jsonify({"success": False, "error": "No folder path provided"}), 400

        folder = LOG_BASE_DIR / folder_path

        if not folder.exists():
            return jsonify({"success": False, "error": "Folder does not exist"}), 404

        # Security check
        try:
            folder.relative_to(LOG_BASE_DIR)
        except ValueError:
            return jsonify({"success": False, "error": "Invalid folder path"}), 403

        shutil.rmtree(folder)

        return jsonify({"success": True, "message": "Folder deleted successfully"})

    except Exception as e:
        logger.error(f"Error deleting folder: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/move-folder", methods=["POST"])
def api_move_folder():
    """Move/rename a folder"""
    try:
        data = request.get_json()
        old_path = data.get("old_path", "")
        new_path = data.get("new_path", "")

        if not old_path or not new_path:
            return jsonify({"success": False, "error": "Both old_path and new_path are required"}), 400

        old_full_path = LOG_BASE_DIR / old_path
        new_full_path = LOG_BASE_DIR / new_path

        if not old_full_path.exists():
            return jsonify({"success": False, "error": "Source folder does not exist"}), 404

        if new_full_path.exists():
            return jsonify({"success": False, "error": "Target path already exists"}), 400

        # Security checks
        try:
            old_full_path.relative_to(LOG_BASE_DIR)
            new_full_path.relative_to(LOG_BASE_DIR)
        except ValueError:
            return jsonify({"success": False, "error": "Invalid path"}), 403

        # Create parent directory if needed
        new_full_path.parent.mkdir(parents=True, exist_ok=True)

        # Perform the move
        old_full_path.rename(new_full_path)

        return jsonify({"success": True, "message": "Folder moved successfully", "new_path": new_path})

    except Exception as e:
        logger.error(f"Error moving folder: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/readme", methods=["GET", "POST"])
def api_readme():
    """Get or save readme content"""
    folder_path = request.args.get("folder") if request.method == "GET" else request.get_json().get("folder")

    if not folder_path:
        return jsonify({"success": False, "error": "No folder specified"}), 400

    folder = LOG_BASE_DIR / folder_path
    if not folder.exists() or not folder.is_dir():
        return jsonify({"success": False, "error": "Invalid folder"}), 404

    readme_file = folder / "readme.txt"

    if request.method == "GET":
        content = readme_file.read_text() if readme_file.exists() else ""
        return jsonify({"success": True, "content": content})
    else:
        content = request.get_json().get("content", "")
        readme_file.write_text(content)
        return jsonify({"success": True, "message": "Readme saved successfully"})


# Catch-all route for React Router (must be last)
@app.errorhandler(404)
def not_found(e):
    """Serve React app for all non-API routes"""
    if request.path.startswith("/api/"):
        return jsonify({"success": False, "error": "Not found"}), 404
    return send_from_directory(app.static_folder, "index.html")
