#!/usr/bin/env python3
"""
AWS Batch job launcher for CodeClash tournaments.

This script submits jobs to AWS Batch to run any command in the CodeClash container.
It automatically finds the latest job definition version.

Usage:
    python run_job.py -- main.py configs/test/battlesnake_pvp_test.yaml
    python run_job.py --job-name my-test -- main.py @battlesnake_pvp_test.yaml --suffix test-run
    python run_job.py --wait --show-logs -- python -m pytest tests/
"""

import argparse
import json
import sys
import time
from typing import Any

import boto3

from codeclash.utils.log import get_logger

logger = get_logger("launch", emoji="🚀")


class AWSBatchJobLauncher:
    def __init__(self, job_definition_name: str = "codeclash-yolo-test", job_queue: str = "codeclash-test-queue"):
        self.batch_client = boto3.client("batch")
        self.logs_client = boto3.client("logs")
        self.job_definition_name = job_definition_name
        self.job_queue = job_queue

    def get_latest_job_definition_arn(self) -> str:
        """Get the ARN of the latest active job definition."""
        response = self.batch_client.describe_job_definitions(
            jobDefinitionName=self.job_definition_name, status="ACTIVE"
        )

        if not response["jobDefinitions"]:
            raise ValueError("No active job definitions found for " + self.job_definition_name)

        # Find the job definition with the highest revision number
        latest_job_def = max(response["jobDefinitions"], key=lambda x: x["revision"])
        logger.debug(f"Latest job definition:\n{json.dumps(latest_job_def, indent=2, default=str)}")
        return latest_job_def["jobDefinitionArn"]

    def submit_job(self, command: list[str], job_name: str | None = None) -> str:
        """Submit a job to AWS Batch."""
        if job_name is None:
            # Generate a job name based on command and timestamp
            cmd_name = command[0] if command else "job"
            cmd_name = "".join(letter.lower() for letter in cmd_name if letter.isalpha())
            timestamp = int(time.time())
            job_name = f"codeclash-{cmd_name}-{timestamp}"

        # Get the latest job definition
        job_definition_arn = self.get_latest_job_definition_arn()

        response = self.batch_client.submit_job(
            jobName=job_name,
            jobQueue=self.job_queue,
            jobDefinition=job_definition_arn,
            containerOverrides={"command": command},
        )

        job_id = response["jobId"]
        logger.info("Job submitted successfully!")
        logger.info(f"Job ID: {job_id}")
        logger.info(f"Job Name: {job_name}")
        logger.info(f"Command: {' '.join(command)}")
        logger.info(f"To retrieve logs later, run: python get_job_log.py {job_id}")

        return job_id

    def get_job_status(self, job_id: str) -> dict[str, Any]:
        """Get the current status of a job."""
        response = self.batch_client.describe_jobs(jobs=[job_id])
        if response["jobs"]:
            return response["jobs"][0]
        else:
            raise ValueError(f"Job {job_id} not found")

    def wait_for_job(self, job_id: str, check_interval: int = 30) -> bool:
        """Wait for a job to complete and return success status."""
        logger.info(f"Waiting for job {job_id} to complete...")

        while True:
            job_info = self.get_job_status(job_id)
            status = job_info["status"]
            logger.info(f"Job status: {status}")

            if status in ["SUCCEEDED", "FAILED"]:
                if status == "SUCCEEDED":
                    logger.info("Job completed successfully!")
                    return True
                else:
                    logger.error("Job failed!")
                    logger.error(f"Status reason: {job_info.get('statusReason', 'Unknown')}")
                    return False

            time.sleep(check_interval)

    def get_job_logs(self, job_id: str) -> str | None:
        """Retrieve logs for a completed job."""
        job_info = self.get_job_status(job_id)

        # Get log stream name from the job info
        attempts = job_info.get("attempts", [])
        if not attempts:
            logger.warning("No job attempts found")
            return None

        latest_attempt = attempts[-1]
        container_info = latest_attempt.get("container", {})
        log_stream_name = container_info.get("logStreamName")

        if not log_stream_name:
            logger.warning("No log stream found for this job")
            return None

        # Extract log group name from the log stream name
        # Format is typically: <log-group>/<stream-name>
        log_group_name = log_stream_name.split("/")[0]

        response = self.logs_client.get_log_events(logGroupName=log_group_name, logStreamName=log_stream_name)

        return "\n".join(event["message"] for event in response["events"])


def main():
    parser = argparse.ArgumentParser(
        description="Submit jobs to AWS Batch",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s -- main.py configs/test/battlesnake_pvp_test.yaml
  %(prog)s --job-name my-test -- main.py @battlesnake_pvp_test.yaml --suffix test-run
  %(prog)s --wait --show-logs -- python -m pytest tests/
        """,
    )

    # AWS Batch specific arguments
    parser.add_argument("--job-name", help="Custom job name (auto-generated if not specified)")
    parser.add_argument(
        "--job-definition", default="codeclash-yolo-test", help="Job definition name (default: codeclash-yolo-test)"
    )
    parser.add_argument(
        "--job-queue", default="codeclash-test-queue", help="Job queue name (default: codeclash-test-queue)"
    )

    # Job monitoring arguments
    parser.add_argument("--wait", action="store_true", help="Wait for the job to complete before exiting")
    parser.add_argument("--show-logs", action="store_true", help="Show job logs after completion (implies --wait)")

    # Parse known args to handle the -- separator
    args, command = parser.parse_known_args()

    if not command:
        parser.error("No command specified. Use -- to separate AWS args from the command to run.")

    # Create launcher
    launcher = AWSBatchJobLauncher(job_definition_name=args.job_definition, job_queue=args.job_queue)

    # Submit the job
    job_id = launcher.submit_job(command, args.job_name)

    # Wait for completion if requested
    if args.wait or args.show_logs:
        success = launcher.wait_for_job(job_id)

        if args.show_logs:
            print("\n" + "=" * 50)
            print("JOB LOGS")
            print("=" * 50)
            logs = launcher.get_job_logs(job_id)
            if logs:
                print(logs)  # Print raw logs without logger formatting
            else:
                logger.warning("No logs available")

        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
