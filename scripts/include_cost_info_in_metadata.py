#!/usr/bin/env python3

import argparse
import json
import re
from pathlib import Path

from codeclash.utils.atomic_write import atomic_write
from codeclash.utils.log import get_logger

logger = get_logger(__name__)


def find_metadata_files(log_folder: Path) -> list[Path]:
    """Find all metadata.json files in the log folder."""
    return list(log_folder.rglob("metadata.json"))


def extract_round_number(filename: str) -> int | None:
    """Extract round number from trajectory filename like player_r1.traj.json."""
    match = re.search(r"_r(\d+)\.traj\.json$", filename)
    return int(match.group(1)) if match else None


def update_agent_info(agent: dict, agent_folder: Path) -> bool:
    """Process a single agent and update their agent_stats.

    Returns True if any updates were made.
    """
    agent_name = agent.get("name")
    if not agent_name:
        logger.warning("Agent entry missing 'name'; skipping")
        return False

    if not agent_folder.is_dir():
        logger.warning(f"No folder found for agent {agent_name} in {agent_folder.parent}")
        return False

    if "agent_stats" not in agent:
        agent["agent_stats"] = {}

    updated = False

    for traj_file in agent_folder.glob(f"{agent_name}_r*.traj.json"):
        round_num = extract_round_number(traj_file.name)
        if round_num is None:
            logger.warning(f"Could not extract round number from {traj_file.name}")
            continue

        if str(round_num) in agent["agent_stats"]:
            existing = agent["agent_stats"][str(round_num)]
            logger.debug(f"Skipping {agent_name} round {round_num} (already exists): {existing}")
            continue

        try:
            traj_data = json.loads(traj_file.read_text())
            info = traj_data.get("info", {})
            model_stats = info.get("model_stats", {})

            cost = model_stats.get("instance_cost")
            api_calls = model_stats.get("api_calls")
            exit_status = info.get("exit_status")

            agent["agent_stats"][str(round_num)] = {
                "exit_status": exit_status,
                "cost": cost,
                "api_calls": api_calls,
            }

            updated = True
            logger.info(f"Added stats for {agent_name} round {round_num}: cost={cost}, api_calls={api_calls}")

        except Exception as e:
            logger.error(f"Error processing {traj_file}: {e}", exc_info=True)

    return updated


def process_tournament_folder(metadata_path: Path, *, dry_run: bool = False) -> None:
    """Process a single tournament folder and update its metadata.json."""
    tournament_folder = metadata_path.parent
    logger.info(f"Processing tournament folder: {tournament_folder}")

    original_text = metadata_path.read_text()
    metadata = json.loads(original_text)

    players_folder = tournament_folder / "players"
    if not players_folder.is_dir():
        logger.warning(f"No players folder found in {tournament_folder}")
        return

    updated = False

    for agent in metadata.get("agents", []):
        agent_name = agent.get("name")
        if not agent_name:
            logger.warning(f"Skipping agent entry without 'name' in {metadata_path}")
            continue
        agent_folder = players_folder / agent_name
        if update_agent_info(agent, agent_folder):
            updated = True

    if updated:
        if dry_run:
            logger.info(f"[DRY RUN] Would update metadata file: {metadata_path}")
        else:
            bak_path = metadata_path.with_name(metadata_path.name + ".bak")
            atomic_write(bak_path, original_text)
            atomic_write(metadata_path, json.dumps(metadata, indent=2))
            logger.info(f"Updated metadata file: {metadata_path}")
    else:
        logger.info(f"No updates needed for {metadata_path}")


def main():
    parser = argparse.ArgumentParser(description="Add cost information from trajectory files to metadata.json files")
    parser.add_argument("log_folder", type=Path, help="Path to the log folder")
    parser.add_argument(
        "--dry-run", action="store_true", help="Show what would be updated without actually modifying files"
    )
    args = parser.parse_args()

    log_folder = args.log_folder
    if not log_folder.exists():
        logger.error(f"Log folder does not exist: {log_folder}")
        return

    if args.dry_run:
        logger.info("Running in DRY RUN mode - no files will be modified")

    metadata_files = find_metadata_files(log_folder)
    logger.info(f"Found {len(metadata_files)} metadata.json files")

    for metadata_path in metadata_files:
        process_tournament_folder(metadata_path, dry_run=args.dry_run)

    logger.info("Done processing all tournament folders")


if __name__ == "__main__":
    main()
