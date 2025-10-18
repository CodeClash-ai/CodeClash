#!/usr/bin/env python3
"""
Trajectory Viewer for AI Agent Benchmark

A Flask-based web application to visualize AI agent game trajectories
"""

import functools
import json
import logging
import shutil
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, redirect, render_template, request, send_file, url_for

from codeclash.analysis.significance import calculate_p_value
from codeclash.tournaments.utils.git_utils import filter_git_diff, split_git_diff_by_files
from codeclash.viewer.app_aws import AWSBatchMonitor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def print_timing(func):
    """Decorator to log timing information for functions/routes"""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        logger.info(f"Starting {func.__name__}")
        try:
            return func(*args, **kwargs)
        finally:
            elapsed = time.time() - start_time
            logger.info(f"Completed {func.__name__} in {elapsed:.2f}s")

    return wrapper


class Metadata:
    """A wrapper around metadata dictionary with convenient access methods"""

    def __init__(self, data: dict[str, Any] | None = None):
        self._data = data or {}

    def get_path(self, path: str, default: Any = None) -> Any:
        """Get value from nested dictionary using dot notation path

        Args:
            path: Dot-separated path like "config.tournament.rounds"
            default: Default value if path doesn't exist

        Returns:
            Value at path or default
        """
        current = self._data
        for key in path.split("."):
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return default
        return current

    @property
    def is_valid(self) -> bool:
        """Check if metadata was loaded successfully"""
        return bool(self._data)

    @property
    def total_rounds(self) -> int | None:
        """Get total number of rounds from config"""
        return self.get_path("config.tournament.rounds")

    @property
    def completed_rounds(self) -> int:
        """Get number of completed rounds (excluding round 0 warmup)"""
        round_stats = self.get_path("round_stats", {})
        return sum(1 for round_key in round_stats.keys() if int(round_key) > 0)

    @property
    def round_count_info(self) -> tuple[int, int] | None:
        """Get (completed_rounds, total_rounds) tuple"""
        total = self.total_rounds
        if total is not None:
            return (self.completed_rounds, total)
        return None

    @property
    def models(self) -> list[str]:
        """Get list of unique model names from players config"""
        players_config = self.get_path("config.players", [])
        models = []
        for player_config in players_config:
            if isinstance(player_config, dict):
                model_name = self.get_path_from_dict(player_config, "config.model.model_name")
                if model_name and model_name not in models:
                    models.append(model_name)
        return models

    @property
    def game_name(self) -> str:
        """Get game name from config"""
        # Try config.game.name first
        game_name = self.get_path("config.game.name")
        if game_name:
            return game_name

        # Fallback to game.name
        game_name = self.get_path("game.name")
        if game_name:
            return game_name

        return ""

    @property
    def players_config(self) -> list[dict[str, Any]]:
        """Get players configuration"""
        return self.get_path("config.players", [])

    @property
    def round_stats(self) -> dict[str, Any]:
        """Get round statistics"""
        return self.get_path("round_stats", {})

    @property
    def raw_data(self) -> dict[str, Any]:
        """Get the raw metadata dictionary"""
        return self._data

    @staticmethod
    def get_path_from_dict(data: dict[str, Any], path: str, default: Any = None) -> Any:
        """Static method to get value from any dictionary using dot notation"""
        current = data
        for key in path.split("."):
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return default
        return current


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


def load_metadata(log_dir: Path) -> Metadata:
    """Load metadata.json from log directory and return Metadata object"""
    metadata_file = log_dir / "metadata.json"
    if not metadata_file.exists():
        return Metadata()

    try:
        data = json.loads(metadata_file.read_text())
        return Metadata(data)
    except (json.JSONDecodeError, OSError):
        return Metadata()


def get_agent_info_from_metadata(metadata: Metadata) -> list[AgentInfo]:
    """Extract detailed agent information from metadata"""
    agents = []
    players_config = metadata.players_config

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


def _load_game_metadata(folder_info: dict[str, Any]) -> dict[str, Any]:
    """Helper function to load metadata for a single game folder in parallel"""
    item = Path(folder_info["full_path"])
    metadata = load_metadata(item)
    folder_info["round_info"] = metadata.round_count_info
    folder_info["models"] = metadata.models
    folder_info["game_name"] = metadata.game_name
    folder_info["created_timestamp"] = metadata.get_path("created_timestamp")
    return folder_info


@print_timing
def find_all_game_folders(base_dir: Path) -> list[dict[str, Any]]:
    """Find all game folders by locating metadata.json files

    Uses parallel loading to speed up metadata.json reading for many game folders.
    """
    if not base_dir.exists():
        return []

    # Find all metadata.json files directly
    metadata_files = list(base_dir.rglob("metadata.json"))

    # Create folder info for each game folder
    game_folder_infos = []
    game_folder_paths = set()

    for metadata_file in metadata_files:
        game_dir = metadata_file.parent
        relative_path = str(game_dir.relative_to(base_dir))
        game_folder_paths.add(relative_path)
        depth = relative_path.count("/")

        folder_info = {
            "name": relative_path,
            "full_path": str(game_dir),
            "is_game": True,
            "depth": depth,
            "parent": str(game_dir.parent.relative_to(base_dir)) if game_dir.parent != base_dir else None,
        }
        game_folder_infos.append(folder_info)

    # Load metadata.json files in parallel
    if game_folder_infos:
        with ThreadPoolExecutor(max_workers=min(32, len(game_folder_infos))) as executor:
            futures = {
                executor.submit(_load_game_metadata, folder_info): folder_info for folder_info in game_folder_infos
            }
            for future in as_completed(futures):
                try:
                    future.result()  # Updates folder_info in place
                except Exception as e:
                    # If metadata loading fails, set default values
                    folder_info = futures[future]
                    folder_info["round_info"] = None
                    folder_info["models"] = []
                    folder_info["game_name"] = ""
                    folder_info["created_timestamp"] = None
                    logger.warning(f"Failed to load metadata for {folder_info['name']}: {e}")

    # Create intermediate folder entries for all parent directories
    intermediate_folders = set()
    for game_path in game_folder_paths:
        # Extract all parent paths
        parts = game_path.split("/")
        for i in range(1, len(parts)):
            parent_path = "/".join(parts[:i])
            if parent_path not in game_folder_paths:  # Only add if not a game folder itself
                intermediate_folders.add(parent_path)

    # Add intermediate folders to the result
    all_folders = game_folder_infos.copy()
    for intermediate_path in intermediate_folders:
        depth = intermediate_path.count("/")
        parent_parts = intermediate_path.split("/")
        parent_path = "/".join(parent_parts[:-1]) if len(parent_parts) > 1 else None

        all_folders.append(
            {
                "name": intermediate_path,
                "full_path": str(base_dir / intermediate_path),
                "is_game": False,
                "depth": depth,
                "parent": parent_path,
                "round_info": None,
                "models": [],
                "game_name": "",
                "created_timestamp": None,
            }
        )

    return sorted(all_folders, key=lambda x: x["name"])


@dataclass
class GameMetadata:
    """Metadata about a game session"""

    results: dict[str, Any]
    main_log_path: str
    metadata_file_path: str
    rounds: list[dict[str, Any]]
    agent_info: list[AgentInfo] | None = None
    all_logs: dict[str, dict[str, str]] | None = None  # {log_type: {"path": path}} - content loaded on demand


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
    valid_submission: bool | None = None


class LogParser:
    """Parses game log files into structured data"""

    def __init__(self, log_dir: Path):
        self.log_dir = Path(log_dir)
        self._cached_metadata: Metadata | None = None

    def _get_metadata(self) -> Metadata:
        """Get cached metadata or load it if not cached"""
        if self._cached_metadata is None:
            self._cached_metadata = load_metadata(self.log_dir)
        return self._cached_metadata

    def parse_game_metadata(self) -> GameMetadata:
        """Parse overall game metadata"""
        # Load metadata.json
        metadata = self._get_metadata()
        if not metadata.is_valid:
            results = {"status": "No metadata file found"}
            metadata_file_path = ""
        else:
            results = metadata.raw_data
            metadata_file_path = str(self.log_dir / "metadata.json")

        # Get path to main log but don't load content
        main_log_file = self.log_dir / "tournament.log"
        main_log_path = str(main_log_file) if main_log_file.exists() else ""

        # Parse all available logs (metadata only, no content)
        all_logs = self._parse_all_logs()

        # Extract agent information once
        agent_info = get_agent_info_from_metadata(metadata)

        # Parse round data from metadata.json round_stats
        rounds = []
        round_stats = metadata.round_stats
        if round_stats:
            # Process each round from round_stats
            for round_key, round_data in round_stats.items():
                round_num = int(round_key)
                round_results = process_round_results(round_data, agent_info)
                rounds.append({"round_num": round_num, "sim_logs": [], "results": round_results})

        # Sort rounds by round number to ensure consistent ordering
        rounds.sort(key=lambda x: x["round_num"])

        return GameMetadata(
            results=results,
            main_log_path=main_log_path,
            metadata_file_path=metadata_file_path,
            rounds=rounds,
            agent_info=agent_info,
            all_logs=all_logs,
        )

    def parse_trajectory(self, player_name: str, round_num: int, *, load_diffs: bool = False) -> TrajectoryInfo | None:
        """Parse a specific trajectory file

        Args:
            player_name: Name of the player
            round_num: Round number
            load_diffs: If True, load diff data. If False (default), skip loading diffs for performance
        """
        player_dir = self.log_dir / "players" / player_name
        if not player_dir.exists():
            return None

        traj_file = player_dir / f"{player_name}_r{round_num}.traj.json"
        if not traj_file.exists():
            return None
        try:
            data = json.loads(traj_file.read_text())
            info = data.get("info", {})
            model_stats = info.get("model_stats", {})

            # Get diff data from changes file only if requested
            diff = incremental_diff = modified_files = None
            diff_by_files = incremental_diff_by_files = None

            if load_diffs:
                changes_file = player_dir / f"changes_r{round_num}.json"
                if changes_file.exists():
                    try:
                        changes_data = json.loads(changes_file.read_text())
                        diff = changes_data.get("full_diff", "")
                        incremental_diff = changes_data.get("incremental_diff", "")
                        modified_files = changes_data.get("modified_files", {})

                        # Filter and split diffs by files
                        filtered_diff = filter_git_diff(diff) if diff else ""
                        filtered_incremental_diff = filter_git_diff(incremental_diff) if incremental_diff else ""
                        diff_by_files = split_git_diff_by_files(filtered_diff) if filtered_diff else {}
                        incremental_diff_by_files = (
                            split_git_diff_by_files(filtered_incremental_diff) if filtered_incremental_diff else {}
                        )
                    except (json.JSONDecodeError, KeyError):
                        pass

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
                valid_submission=self._get_metadata().round_stats[str(round_num)]["player_stats"][player_name][
                    "valid_submit"
                ],
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
        metadata = self._get_metadata()
        if not metadata.is_valid:
            return {"players": [], "rounds": [], "scores_by_player": {}}

        round_stats = metadata.round_stats
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
        """Parse all available log files in the tournament directory (metadata only, no content)"""
        all_logs = {}

        # Define log files to look for
        log_files = {"tournament.log": "Tournament Log", "game.log": "Game Log", "everything.log": "Everything Log"}

        # Check for main log files
        for log_file, display_name in log_files.items():
            log_path = self.log_dir / log_file
            if log_path.exists():
                all_logs[display_name] = {"path": str(log_path)}

        # Check for player logs
        players_dir = self.log_dir / "players"
        if players_dir.exists():
            for player_dir in players_dir.iterdir():
                if not player_dir.is_dir():
                    continue

                player_name = player_dir.name
                player_log = player_dir / "player.log"

                if player_log.exists():
                    display_name = f"Player {player_name} Log"
                    all_logs[display_name] = {"path": str(player_log)}

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


def get_folder_name(path):
    """Extract the folder name from a path"""
    if not path:
        return ""
    from pathlib import Path

    return Path(path).name


def get_parent_folder(path):
    """Extract the parent folder name from a path"""
    if not path:
        return ""
    from pathlib import Path

    parent = Path(path).parent
    if str(parent) == "." or str(parent) == "/":
        return ""
    return parent.name


def format_timestamp(timestamp):
    """Format Unix timestamp as YYYY-MM-DD HH:MM"""
    if timestamp is None:
        return ""
    from datetime import datetime

    try:
        dt = datetime.fromtimestamp(timestamp)
        return dt.strftime("%Y-%m-%d %H:%M")
    except (ValueError, OSError):
        return ""


def strip_model_prefix(model_name):
    """Strip provider prefix from model name (e.g., 'openai/gpt-5' -> 'gpt-5')"""
    if not model_name:
        return ""
    # Strip everything up to and including the last slash
    if "/" in model_name:
        return model_name.split("/")[-1]
    return model_name


def get_navigation_info(selected_folder: str) -> dict[str, str | None]:
    """Get previous and next game folders for navigation"""
    # Get all game folders
    game_folders = find_all_game_folders(LOG_BASE_DIR)

    # Filter to only actual game folders and sort them
    game_names = [folder["name"] for folder in game_folders if folder["is_game"]]
    game_names.sort()

    # Find current game index
    try:
        current_index = game_names.index(selected_folder)
    except ValueError:
        # Current folder not found in the list
        return {"previous": None, "next": None}

    # Determine previous and next
    previous_game = game_names[current_index - 1] if current_index > 0 else None
    next_game = game_names[current_index + 1] if current_index < len(game_names) - 1 else None

    return {"previous": previous_game, "next": next_game}


@print_timing
def render_game_viewer(folder_path: Path, selected_folder: str) -> str:
    """Common logic for rendering game viewer pages"""
    # Parse the selected game
    parser = LogParser(folder_path)
    metadata = parser.parse_game_metadata()

    # Group trajectories by round (without loading diffs)
    trajectories_by_round = {}
    for player_name, round_num in parser.get_available_trajectories():
        if round_num not in trajectories_by_round:
            trajectories_by_round[round_num] = []
        trajectory = parser.parse_trajectory(player_name, round_num, load_diffs=False)
        if trajectory:
            trajectories_by_round[round_num].append(trajectory)

    # Get analysis data (skip line counting - will be loaded on demand)
    sim_wins_data = parser.analyze_sim_wins_per_round()
    matrix_data = parser.load_matrix_analysis()

    # Get navigation info
    navigation_info = get_navigation_info(selected_folder)

    return render_template(
        "index.html",
        selected_folder=selected_folder,
        selected_folder_path=str(folder_path),
        metadata=metadata,
        trajectories_by_round=trajectories_by_round,
        sim_wins_data=sim_wins_data,
        matrix_data=matrix_data,
        navigation=navigation_info,
        is_static=STATIC_MODE,
    )


# Register the custom filters
app.jinja_env.filters["nl2br"] = nl2br
app.jinja_env.filters["unescape_content"] = unescape_content
app.jinja_env.filters["get_folder_name"] = get_folder_name
app.jinja_env.filters["get_parent_folder"] = get_parent_folder
app.jinja_env.filters["format_timestamp"] = format_timestamp
app.jinja_env.filters["strip_model_prefix"] = strip_model_prefix


@app.route("/")
@print_timing
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
@print_timing
def game_view(folder_path):
    """Static-friendly game viewer route using path parameters"""
    # Validate the selected folder exists and is a game folder
    folder_path_obj = LOG_BASE_DIR / folder_path

    if not folder_path_obj.exists() or not is_game_folder(folder_path_obj):
        return redirect(url_for("game_picker"))

    return render_game_viewer(folder_path_obj, folder_path)


@app.route("/picker")
@print_timing
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
@print_timing
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


@app.route("/load-log")
def load_log():
    """Load log file content on demand"""
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

        # Read and return the file content
        content = file_path_obj.read_text()
        return jsonify({"success": True, "content": content})

    except (OSError, UnicodeDecodeError) as e:
        return jsonify({"success": False, "error": f"Error reading file: {str(e)}"}), 500


@app.route("/load-trajectory-diffs")
@print_timing
def load_trajectory_diffs():
    """Load trajectory diff data on demand"""
    selected_folder = request.args.get("folder")
    player_name = request.args.get("player")
    round_num = request.args.get("round")

    if not all([selected_folder, player_name, round_num]):
        return jsonify({"success": False, "error": "Missing required parameters"}), 400

    try:
        round_num = int(round_num)
    except ValueError:
        return jsonify({"success": False, "error": "Invalid round number"}), 400

    try:
        # Validate the selected folder exists and is a game folder
        folder_path = LOG_BASE_DIR / selected_folder
        if not folder_path.exists() or not is_game_folder(folder_path):
            return jsonify({"success": False, "error": "Invalid game folder"}), 404

        # Parse trajectory with diffs loaded
        parser = LogParser(folder_path)
        trajectory = parser.parse_trajectory(player_name, round_num, load_diffs=True)

        if not trajectory:
            return jsonify({"success": False, "error": "Trajectory not found"}), 404

        return jsonify(
            {
                "success": True,
                "diff": trajectory.diff,
                "incremental_diff": trajectory.incremental_diff,
                "modified_files": trajectory.modified_files,
                "diff_by_files": trajectory.diff_by_files,
                "incremental_diff_by_files": trajectory.incremental_diff_by_files,
            }
        )

    except Exception as e:
        logger.error(f"Error loading trajectory diffs: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/batch")
@print_timing
def batch_monitor():
    """AWS Batch job monitor page"""
    return render_template("batch.html")


@app.route("/batch/api/jobs")
@print_timing
def batch_api_jobs():
    """API endpoint to get AWS Batch jobs"""
    try:
        monitor = AWSBatchMonitor(job_queue="codeclash-queue", region="us-east-1", logs_base_dir=LOG_BASE_DIR)
        jobs = monitor.get_formatted_jobs()
        return jsonify({"success": True, "jobs": jobs})
    except Exception as e:
        logger.error(f"Error fetching AWS Batch jobs: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


# Use run_viewer.py to launch the application
