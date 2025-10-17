#!/usr/bin/env python3

import argparse
import json
import logging
from datetime import datetime
from pathlib import Path

from aws.run_job import AWSBatchJobLauncher
from aws.utils.job_monitor import JobMonitor
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
        self.monitor = JobMonitor(region=region)

    def submit_configs(self, configs: list[str]) -> dict[str, str]:
        """Submit jobs for a list of config files. Returns job_id -> config mapping."""
        logger.info(f"Launching {len(configs)} configs")
        job_id_to_config: dict[str, str] = {}

        for config in configs:
            config_path = self.config_dir / config
            command = ["aws/docker_and_sync.sh", "python", "main.py", str(config_path)]
            job_id = self.launcher.submit_job(command)
            job_id_to_config[job_id] = config

        return job_id_to_config

    def save_job_ids(self, job_id_to_config: dict[str, str]) -> Path:
        """Save job IDs to a timestamped JSON file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = Path(f"batch_submit_{timestamp}.json")
        output_file.write_text(json.dumps(job_id_to_config, indent=2))
        logger.info(f"Job IDs saved to {output_file}")
        return output_file

    def run(self, configs: list[str]) -> None:
        """Submit jobs, save IDs, and monitor."""
        job_id_to_config = self.submit_configs(configs)
        self.save_job_ids(job_id_to_config)
        self.monitor.monitor(job_id_to_config)


def main() -> None:
    parser = argparse.ArgumentParser(description="Submit multiple AWS Batch jobs and monitor them")
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
