#!/usr/bin/env python3

import argparse
import json
from pathlib import Path

from aws.utils.job_monitor import JobMonitor
from codeclash.utils.log import get_logger

logger = get_logger("batch_monitor", emoji="👁️")


def load_job_files(job_files: list[Path]) -> dict[str, dict[str, str]]:
    """Load job information from multiple JSON files.

    Args:
        job_files: List of paths to batch_submit_{timestamp}.json files

    Returns:
        Combined dict mapping job_id -> {job_name, config}
    """
    all_jobs: dict[str, dict[str, str]] = {}

    for job_file in job_files:
        logger.info(f"Loading jobs from {job_file}")
        jobs = json.loads(job_file.read_text())

        # Handle both old format (job_id -> config) and new format (job_id -> {job_name, config})
        for job_id, value in jobs.items():
            if isinstance(value, dict):
                all_jobs[job_id] = value
            else:
                # Old format, convert to new format
                all_jobs[job_id] = {"job_name": "N/A", "config": value}

    logger.info(f"Loaded {len(all_jobs)} jobs total")
    return all_jobs


def main() -> None:
    parser = argparse.ArgumentParser(description="Monitor AWS Batch jobs from multiple batch_submit JSON files")
    parser.add_argument(
        "job_files",
        type=Path,
        nargs="+",
        help="One or more batch_submit_{timestamp}.json files to monitor",
    )
    parser.add_argument(
        "--region",
        default="us-east-1",
        help="AWS region (default: us-east-1)",
    )
    args = parser.parse_args()

    all_jobs = load_job_files(args.job_files)

    monitor = JobMonitor(region=args.region)
    monitor.monitor(all_jobs)


if __name__ == "__main__":
    main()
