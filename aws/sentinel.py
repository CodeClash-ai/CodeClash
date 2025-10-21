#! /usr/bin/env python3

"""For running things overnight, throttles the number of jobs running in parallel
if things start going south.
"""

import time
from datetime import UTC, datetime, timedelta
from typing import Any

import boto3
from pydantic import BaseModel

from codeclash.utils.log import get_logger


class StatusData(BaseModel):
    n_jobs_running: int
    n_jobs_failed_last_2h: int
    """2h is relative to job start time, not submission time."""
    n_jobs_succeeded_last_2h: int
    """2h is relative to job start time, not submission time."""
    n_jobs_runnable: int

    @property
    def n_jobs_completed_last_2h(self) -> int:
        return self.n_jobs_failed_last_2h + self.n_jobs_succeeded_last_2h

    @property
    def failed_ratio(self) -> float:
        if self.n_jobs_failed_last_2h + self.n_jobs_succeeded_last_2h == 0:
            return 0.0
        return self.n_jobs_failed_last_2h / (self.n_jobs_failed_last_2h + self.n_jobs_succeeded_last_2h)


def get_status_data() -> StatusData:
    """Collect AWS Batch status for the last 2 hours."""
    batch: Any = boto3.client("batch", region_name="us-east-1")

    def list_jobs_count(status: str) -> tuple[int, list[dict[str, Any]]]:
        paginator = batch.get_paginator("list_jobs")
        pages = paginator.paginate(jobQueue="codeclash-queue", jobStatus=status)
        jobs: list[dict[str, Any]] = []
        for page in pages:
            jobs.extend(page.get("jobSummaryList", []))
        return len(jobs), jobs

    n_running, _ = list_jobs_count("RUNNING")
    n_runnable, _ = list_jobs_count("RUNNABLE")

    since = datetime.now(UTC) - timedelta(hours=2)
    since_ms = int(since.timestamp() * 1000)

    def count_completed_recent(status: str) -> int:
        _, jobs = list_jobs_count(status)
        count = 0
        for j in jobs:
            # Prefer startedAt if present; fall back to createdAt
            started_at = j.get("startedAt") or j.get("createdAt")
            if isinstance(started_at, datetime):
                ts_ms = int(started_at.timestamp() * 1000)
            else:
                ts_ms = int(started_at) if started_at is not None else 0
            if ts_ms >= since_ms:
                count += 1
        return count

    n_failed_recent = count_completed_recent("FAILED")
    n_succeeded_recent = count_completed_recent("SUCCEEDED")

    return StatusData(
        n_jobs_running=n_running,
        n_jobs_failed_last_2h=n_failed_recent,
        n_jobs_succeeded_last_2h=n_succeeded_recent,
        n_jobs_runnable=n_runnable,
    )


def set_max_vcpus(vcpus: int, logger: Any = None) -> None:
    batch: Any = boto3.client("batch", region_name="us-east-1")
    # See aws/setup/batch/environment.json for the environment name and defaults
    response = batch.update_compute_environment(
        computeEnvironment="codeclash-batch",
        computeResources={"maxvCpus": int(vcpus)},
    )
    if logger:
        logger.info(f"Update response: {response}")
        # Verify the update
        env = batch.describe_compute_environments(computeEnvironments=["codeclash-batch"])
        status = env["computeEnvironments"][0]["status"]
        current_max = env["computeEnvironments"][0]["computeResources"].get("maxvCpus")
        logger.info(f"Compute environment status: {status}, current maxvCpus in config: {current_max}")


class AutoScaler:
    def __init__(self, max_vcpus: int = 40 * 4):
        self.default_max_vcpus = max_vcpus
        self.current_max_vcpus = max_vcpus
        self.logger = get_logger("AutoScaler", emoji="🔄")

    def get_scale_factor(self, status_data: StatusData) -> float:
        if status_data.n_jobs_completed_last_2h >= 5:
            if status_data.failed_ratio > 0.2:
                return 0.0
            elif status_data.failed_ratio > 0.1:
                return 0.5
            elif status_data.failed_ratio > 0.05:
                return 0.75
            return 1.0
        # Run at least 1 vCPU, but otherwise don't change anything
        return max(4, self.current_max_vcpus / self.default_max_vcpus)

    def run(self) -> None:
        self.logger.info(f"Starting AutoScaler with default max vCPUs: {self.default_max_vcpus}")
        set_max_vcpus(self.default_max_vcpus, logger=self.logger)
        self.current_max_vcpus = self.default_max_vcpus
        while True:
            try:
                status_data = get_status_data()
                print(status_data)
                scale_factor = self.get_scale_factor(status_data)
                new_max_vcpus = int(self.default_max_vcpus * scale_factor)
                if new_max_vcpus != self.current_max_vcpus:
                    self.logger.info(f"Scaling from {self.current_max_vcpus} to {new_max_vcpus}")
                    set_max_vcpus(new_max_vcpus, logger=self.logger)
                    self.current_max_vcpus = new_max_vcpus
            except Exception as e:
                self.logger.error(f"Error scaling: {e}", exc_info=True)
            finally:
                time.sleep(600)


if __name__ == "__main__":
    scaler = AutoScaler()
    scaler.run()
