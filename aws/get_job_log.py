#!/usr/bin/env python3
"""
AWS Batch job log retriever for CodeClash tournaments.

This script retrieves logs for a completed AWS Batch job by job ID.

Usage:
    python get_job_log.py <job-id>
    python get_job_log.py --job-definition my-job-def <job-id>
"""

import argparse
import sys

import boto3

from codeclash.utils.log import get_logger

logger = get_logger("get_log", emoji="📋")


class AWSBatchLogRetriever:
    def __init__(self):
        self.batch_client = boto3.client("batch")
        self.logs_client = boto3.client("logs")

    def get_job_status(self, job_id: str) -> dict:
        """Get the current status of a job."""
        response = self.batch_client.describe_jobs(jobs=[job_id])
        if response["jobs"]:
            return response["jobs"][0]
        else:
            raise ValueError(f"Job {job_id} not found")

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
        logger.debug(f"Log stream name: {log_stream_name}")

        if not log_stream_name:
            logger.warning("No log stream found for this job")
            return None

        # AWS Batch logs are typically in the /aws/batch/job log group
        log_group_name = "/aws/batch/job"
        logger.debug(f"Log group name: {log_group_name}")

        response = self.logs_client.get_log_events(logGroupName=log_group_name, logStreamName=log_stream_name)
        return "\n".join(event["message"] for event in response["events"])


def main():
    parser = argparse.ArgumentParser(
        description="Retrieve logs for AWS Batch jobs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument("job_id", help="Job ID to retrieve logs for")

    args = parser.parse_args()

    # Create log retriever
    retriever = AWSBatchLogRetriever()

    # Get job status first
    job_info = retriever.get_job_status(args.job_id)
    status = job_info["status"]

    logger.info(f"Job ID: {args.job_id}")
    logger.info(f"Job Status: {status}")
    logger.info(f"Job Name: {job_info.get('jobName', 'Unknown')}")

    if status not in ["SUCCEEDED", "FAILED"]:
        logger.warning(f"Job is in status '{status}' - logs may not be complete yet")

    # Retrieve and display logs
    logger.info("\n" + "=" * 50)
    logger.info("JOB LOGS")
    logger.info("=" * 50)

    logs = retriever.get_job_logs(args.job_id)
    if logs:
        print(logs)  # Print raw logs without logger formatting
    else:
        logger.warning("No logs available")
        sys.exit(1)


if __name__ == "__main__":
    main()
