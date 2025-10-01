#!/usr/bin/env python3
"""
AWS Batch job listing script for CodeClash.

This is a convenience script that lists all AWS Batch jobs sorted by creation time.

Usage:
    python list_jobs.py
    python list_jobs.py --status RUNNING
    python list_jobs.py --queue my-queue --limit 20
"""

import argparse
from datetime import datetime
from typing import Any

import boto3

from codeclash.utils.log import get_logger

logger = get_logger("list_jobs", emoji="📋")


class AWSBatchJobLister:
    def __init__(self, job_queue: str = "codeclash-queue"):
        self.batch_client = boto3.client("batch")
        self.job_queue = job_queue

    def list_jobs(self, *, status: str | None = None, limit: int | None = None) -> list[dict[str, Any]]:
        """List jobs from AWS Batch, optionally filtered by status."""
        all_jobs = []

        # If specific status is requested, only query that status
        if status:
            statuses = [status.upper()]
        else:
            # Query all active statuses
            statuses = ["SUBMITTED", "PENDING", "RUNNABLE", "STARTING", "RUNNING", "SUCCEEDED", "FAILED"]

        for job_status in statuses:
            try:
                # Use paginator to handle large number of jobs
                paginator = self.batch_client.get_paginator("list_jobs")
                page_iterator = paginator.paginate(jobQueue=self.job_queue, jobStatus=job_status)

                for page in page_iterator:
                    jobs_in_page = page.get("jobSummaryList", [])
                    all_jobs.extend(jobs_in_page)

            except Exception as e:
                logger.warning(f"Failed to list jobs with status {job_status}: {e}")
                continue

        # Sort by creation time (newest first)
        all_jobs.sort(key=lambda x: x["createdAt"], reverse=True)

        # Apply limit if specified
        if limit:
            all_jobs = all_jobs[:limit]

        return all_jobs

    def format_job_info(self, job: dict[str, Any]) -> str:
        """Format job information for display."""
        job_id = job["jobId"]
        job_name = job["jobName"]
        status = job["status"]
        created_at = job["createdAt"]

        # Format creation time
        if isinstance(created_at, datetime):
            created_str = created_at.strftime("%Y-%m-%d %H:%M:%S")
        else:
            # Handle timestamp (milliseconds since epoch)
            created_str = datetime.fromtimestamp(created_at / 1000).strftime("%Y-%m-%d %H:%M:%S")

        # Get additional info if available
        started_at = job.get("startedAt")
        stopped_at = job.get("stoppedAt")

        duration = ""
        if started_at and stopped_at:
            if isinstance(started_at, datetime):
                start_time = started_at
                stop_time = stopped_at
            else:
                start_time = datetime.fromtimestamp(started_at / 1000)
                stop_time = datetime.fromtimestamp(stopped_at / 1000)
            duration_seconds = (stop_time - start_time).total_seconds()
            duration = f" ({duration_seconds:.0f}s)"
        elif started_at:
            if isinstance(started_at, datetime):
                start_time = started_at
            else:
                start_time = datetime.fromtimestamp(started_at / 1000)
            running_seconds = (datetime.now() - start_time).total_seconds()
            duration = f" (running {running_seconds:.0f}s)"

        return f"{job_id:<36} {status:<10} {created_str} {job_name}{duration}"

    def print_jobs(self, jobs: list[dict[str, Any]]) -> None:
        """Print jobs in a formatted table."""
        if not jobs:
            logger.info("No jobs found")
            return

        # Print header
        header = f"{'Job ID':<36} {'Status':<10} {'Created':<19} {'Job Name'}"
        print(header)
        print("-" * len(header))

        # Print jobs
        for job in jobs:
            print(self.format_job_info(job))

        print(f"\nTotal: {len(jobs)} job(s)")


def main():
    parser = argparse.ArgumentParser(
        description="List AWS Batch jobs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--status",
        choices=["SUBMITTED", "PENDING", "RUNNABLE", "STARTING", "RUNNING", "SUCCEEDED", "FAILED"],
        help="Filter jobs by status (default: show all statuses)",
    )
    parser.add_argument("--queue", default="codeclash-queue", help="Job queue name (default: codeclash-queue)")
    parser.add_argument("--limit", type=int, help="Maximum number of jobs to display")

    args = parser.parse_args()

    lister = AWSBatchJobLister(job_queue=args.queue)

    # List jobs
    logger.info(f"Listing jobs from queue: {args.queue}")
    if args.status:
        logger.info(f"Filtering by status: {args.status}")

    jobs = lister.list_jobs(status=args.status, limit=args.limit)
    lister.print_jobs(jobs)


if __name__ == "__main__":
    main()
