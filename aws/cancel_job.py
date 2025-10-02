#!/usr/bin/env python3
"""
AWS Batch job cancellation script for CodeClash.

This script can cancel AWS Batch jobs by job name or job ID.
It can handle multiple jobs at once for cancellation.

Usage:
    python cancel_job.py job-id-1 job-id-2 job-name-3
    python cancel_job.py --reason "Manual cancellation" job-id-1
"""

import argparse
from typing import Any

import boto3

from codeclash.utils.log import get_logger

logger = get_logger("cancel")


class AWSBatchJobCanceller:
    def __init__(self, region: str = "us-east-1"):
        self.batch_client = boto3.client("batch", region_name=region)

    def find_job_by_name(self, job_name: str) -> list[dict[str, Any]]:
        """Find jobs by name. Returns list of job info dictionaries."""
        jobs = []

        # Search in different job queues and statuses
        for status in ["SUBMITTED", "PENDING", "RUNNABLE", "STARTING", "RUNNING"]:
            response = self.batch_client.list_jobs(
                jobQueue="codeclash-queue",  # Default queue name from run_job.py
                jobStatus=status,
            )

            for job in response["jobs"]:
                if job["jobName"] == job_name:
                    jobs.append(job)

        return jobs

    def get_job_info(self, job_identifier: str) -> dict[str, Any] | None:
        """Get job info by job ID or job name."""
        # First try as job ID
        try:
            response = self.batch_client.describe_jobs(jobs=[job_identifier])
            if response["jobs"]:
                return response["jobs"][0]
        except Exception:
            pass

        # Try as job name
        jobs = self.find_job_by_name(job_identifier)
        if len(jobs) == 1:
            return jobs[0]
        elif len(jobs) > 1:
            logger.warning(f"Multiple jobs found with name '{job_identifier}', using most recent")
            return max(jobs, key=lambda x: x["createdAt"])

        return None

    def cancel_job(self, job_identifier: str, *, reason: str = "Cancelled by user") -> bool:
        """Cancel a job by ID or name. Returns True if successful."""
        job_info = self.get_job_info(job_identifier)

        if not job_info:
            logger.error(f"Job not found: {job_identifier}")
            return False

        job_id = job_info["jobId"]
        job_name = job_info["jobName"]
        status = job_info["status"]

        if status in ["SUCCEEDED", "FAILED"]:
            logger.warning(f"Job {job_name} ({job_id}) is already {status.lower()}")
            return True

        try:
            self.batch_client.cancel_job(jobId=job_id, reason=reason)
            logger.info(f"Successfully cancelled job: {job_name} ({job_id})")
            return True
        except Exception as e:
            logger.error(f"Failed to cancel job {job_name} ({job_id}): {e}", exc_info=True)
            return False

    def cancel_jobs(self, job_identifiers: list[str], *, reason: str = "Cancelled by user") -> int:
        """Cancel multiple jobs. Returns number of successfully cancelled jobs."""
        successful_cancellations = 0

        for job_identifier in job_identifiers:
            if self.cancel_job(job_identifier, reason=reason):
                successful_cancellations += 1

        return successful_cancellations


def main():
    parser = argparse.ArgumentParser(
        description="Cancel AWS Batch jobs by name or ID",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("jobs", nargs="+", help="Job IDs or job names to cancel")
    parser.add_argument(
        "--reason", default="Cancelled by user", help="Reason for cancellation (default: 'Cancelled by user')"
    )
    parser.add_argument("--region", default="us-east-1", help="AWS region (default: us-east-1)")

    args = parser.parse_args()

    canceller = AWSBatchJobCanceller(region=args.region)

    # Cancel jobs
    logger.info(f"Cancelling {len(args.jobs)} job(s)...")
    canceller.cancel_jobs(args.jobs, reason=args.reason)


if __name__ == "__main__":
    main()
