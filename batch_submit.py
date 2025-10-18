#!/usr/bin/env python3

import argparse
import json
import logging
from datetime import datetime
from pathlib import Path

from aws.run_job import AWSBatchJobLauncher
from codeclash.utils.log import get_logger

logger = get_logger("batch_submit", emoji="🚀")


class BatchSubmitter:
    def __init__(
        self,
        config_dir: Path = Path("configs/main"),
        job_definition_name: str = "codeclash-default-job",
        job_queue: str = "codeclash-queue",
        region: str = "us-east-1",
    ):
        self.config_dir = config_dir
        self.launcher = AWSBatchJobLauncher(
            job_definition_name=job_definition_name,
            job_queue=job_queue,
            region=region,
        )

    def submit_configs(self, configs: list[str]) -> dict[str, dict[str, str]]:
        """Submit jobs for a list of config files. Returns job_id -> {job_name, config} mapping."""
        logger.info(f"Launching {len(configs)} configs")
        job_info: dict[str, dict[str, str]] = {}

        for config in configs:
            config_path = self.config_dir / config
            command = ["aws/docker_and_sync.sh", "python", "main.py", str(config_path)]
            job_id, job_name = self.launcher.submit_job(command)
            job_info[job_id] = {"job_name": job_name, "config": config}

        return job_info

    def save_job_ids(self, job_info: dict[str, dict[str, str]]) -> Path:
        """Save job IDs and names to a timestamped JSON file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = Path(f"batch_submit_{timestamp}.json")
        output_file.write_text(json.dumps(job_info, indent=2))
        logger.info(f"Job IDs saved to {output_file}")
        return output_file

    def run(self, configs: list[str]) -> None:
        """Submit jobs and save IDs."""
        job_info = self.submit_configs(configs)
        self.save_job_ids(job_info)


def main() -> None:
    parser = argparse.ArgumentParser(description="Submit multiple AWS Batch jobs")
    parser.add_argument("configs_file", type=Path, help="Text file containing config file names (one per line)")
    parser.add_argument(
        "--config-dir",
        type=Path,
        default=Path("configs/main"),
        help="Directory containing config files (default: configs/main)",
    )
    args = parser.parse_args()

    # Set logging level for the AWS Batch launcher
    logging.getLogger("launch").setLevel(logging.INFO)

    configs_to_run = [line.strip() for line in args.configs_file.read_text().strip().split("\n") if line.strip()]

    submitter = BatchSubmitter(config_dir=args.config_dir)
    submitter.run(configs_to_run)


if __name__ == "__main__":
    main()
