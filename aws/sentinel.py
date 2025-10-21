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


def set_job_queue_state(enabled: bool, logger: Any = None) -> None:
    """Enable or disable the job queue to control whether new jobs can start."""
    batch: Any = boto3.client("batch", region_name="us-east-1")
    state = "ENABLED" if enabled else "DISABLED"
    batch.update_job_queue(jobQueue="codeclash-queue", state=state)
    if logger:
        logger.info(f"Job queue set to {state}")


def set_max_vcpus(vcpus: int, logger: Any = None) -> None:
    """Set the maximum vCPUs for the compute environment."""
    batch: Any = boto3.client("batch", region_name="us-east-1")
    batch.update_compute_environment(
        computeEnvironment="codeclash-batch",
        computeResources={"maxvCpus": int(vcpus)},
    )
    if logger:
        logger.info(f"Set maxvCpus to {vcpus}")


class AutoScaler:
    def __init__(self, *, max_vcpus: int = 200):
        self.queue_enabled = True
        self.max_vcpus = max_vcpus
        self.current_vcpus = max_vcpus
        self.last_scale_up_time: datetime | None = None
        self.ramp_up_schedule = [16, 32, 64, 128, max_vcpus]
        self.logger = get_logger("AutoScaler", emoji="🔄")

    def should_disable_queue(self, status_data: StatusData) -> bool:
        """Decide whether to disable the queue based on failure rate."""
        if status_data.n_jobs_completed_last_2h >= 5 and status_data.failed_ratio > 0.2:
            return True
        return False

    def handle_gradual_scale_up(self) -> None:
        """Gradually increase maxvCpus over time when ramping up after a failure."""
        if self.current_vcpus >= self.max_vcpus:
            return

        now = datetime.now(UTC)
        if self.last_scale_up_time is None:
            return

        time_since_last_scale = now - self.last_scale_up_time
        if time_since_last_scale >= timedelta(hours=1):
            for target in self.ramp_up_schedule:
                if target > self.current_vcpus:
                    self.logger.info(f"Ramping up maxvCpus from {self.current_vcpus} to {target}")
                    set_max_vcpus(target, logger=self.logger)
                    self.current_vcpus = target
                    self.last_scale_up_time = now
                    break

    def run(self) -> None:
        self.logger.info(f"Starting AutoScaler sentinel (max_vcpus={self.max_vcpus})")
        set_job_queue_state(enabled=True, logger=self.logger)
        set_max_vcpus(self.max_vcpus, logger=self.logger)
        self.queue_enabled = True
        self.current_vcpus = self.max_vcpus

        while True:
            try:
                status_data = get_status_data()
                self.logger.info(
                    f"Status: {status_data.n_jobs_running} running, {status_data.n_jobs_runnable} runnable, "
                    f"{status_data.n_jobs_failed_last_2h}/{status_data.n_jobs_completed_last_2h} failed/completed (2h)"
                )

                should_disable = self.should_disable_queue(status_data)

                if should_disable and self.queue_enabled:
                    self.logger.warning(f"High failure rate ({status_data.failed_ratio:.1%}), disabling job queue")
                    set_job_queue_state(enabled=False, logger=self.logger)
                    self.queue_enabled = False
                elif not should_disable and not self.queue_enabled:
                    self.logger.info("Failure rate acceptable, re-enabling job queue with gradual scale-up")
                    set_job_queue_state(enabled=True, logger=self.logger)
                    self.queue_enabled = True
                    # Start gradual ramp-up from 16 vCPUs
                    self.current_vcpus = self.ramp_up_schedule[0]
                    set_max_vcpus(self.current_vcpus, logger=self.logger)
                    self.last_scale_up_time = datetime.now(UTC)

                # Continue gradual scale-up if in progress
                if self.queue_enabled and self.current_vcpus < self.max_vcpus:
                    self.handle_gradual_scale_up()

            except Exception as e:
                self.logger.error(f"Error in sentinel: {e}", exc_info=True)
            finally:
                time.sleep(600)


if __name__ == "__main__":
    scaler = AutoScaler()
    scaler.run()
