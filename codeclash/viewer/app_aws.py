#!/usr/bin/env python3
"""
AWS Batch monitoring functionality for CodeClash viewer
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

try:
    import boto3
except ImportError:
    boto3 = None

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class AWSBatchMonitor:
    """Monitor AWS Batch jobs"""

    def __init__(
        self,
        *,
        job_queue: str = "codeclash-queue",
        region: str = "us-east-1",
        logs_base_dir: Path | None = None,
    ):
        if boto3 is None:
            msg = "boto3 is not installed. Install it with: pip install codeclash[aws]"
            raise ImportError(msg)
        self.batch_client = boto3.client("batch", region_name=region)
        self.job_queue = job_queue
        self.region = region
        self.logs_base_dir = logs_base_dir or Path("logs")
        self._job_id_to_folder: dict[str, str] | None = None
        self._job_id_to_round_info: dict[str, tuple[int, int] | None] | None = None

    def list_jobs(self, *, limit: int | None = None) -> list[dict[str, Any]]:
        """List all jobs from AWS Batch in the last 24h"""
        all_jobs = []
        statuses = ["SUBMITTED", "PENDING", "RUNNABLE", "STARTING", "RUNNING", "SUCCEEDED", "FAILED"]

        for job_status in statuses:
            try:
                paginator = self.batch_client.get_paginator("list_jobs")
                page_iterator = paginator.paginate(jobQueue=self.job_queue, jobStatus=job_status)

                for page in page_iterator:
                    jobs_in_page = page.get("jobSummaryList", [])
                    all_jobs.extend(jobs_in_page)

            except Exception as e:
                logger.warning(f"Failed to list jobs with status {job_status}: {e}", exc_info=True)

        all_jobs.sort(key=lambda x: x.get("createdAt", 0), reverse=True)

        if limit:
            all_jobs = all_jobs[:limit]

        return all_jobs

    def format_job_for_display(self, job: dict[str, Any]) -> dict[str, Any]:
        """Format job data for display in the UI"""
        job_id = job.get("jobId", "")
        job_name = job.get("jobName", "")
        status = job.get("status", "UNKNOWN")
        created_at = job.get("createdAt")
        started_at = job.get("startedAt")
        stopped_at = job.get("stoppedAt")

        if isinstance(created_at, datetime):
            created_str = created_at.strftime("%Y-%m-%d %H:%M:%S")
            created_timestamp = created_at.timestamp()
        elif created_at:
            created_timestamp = created_at / 1000
            created_str = datetime.fromtimestamp(created_timestamp).strftime("%Y-%m-%d %H:%M:%S")
        else:
            created_str = ""
            created_timestamp = 0

        time_running_str, time_running_seconds = self._calculate_time_running(started_at, stopped_at, status)

        aws_link = self._generate_aws_console_link(job_id)
        emagedoc_link = self._generate_emagedoc_link(job_id)
        s3_link = self._generate_s3_link(job_id)
        round_info = self._get_round_info(job_id)

        return {
            "job_id": job_id,
            "job_name": job_name,
            "status": status,
            "created_at": created_str,
            "created_timestamp": created_timestamp,
            "time_running": time_running_str,
            "time_running_seconds": time_running_seconds,
            "aws_link": aws_link,
            "emagedoc_link": emagedoc_link,
            "s3_link": s3_link,
            "round_info": round_info,
        }

    def _calculate_time_running(
        self, started_at: int | datetime | None, stopped_at: int | datetime | None, status: str
    ) -> tuple[str, float]:
        """Calculate time running for a job

        Returns:
            Tuple of (formatted_string, seconds)
        """
        if not started_at:
            return "-", 0

        if isinstance(started_at, datetime):
            start_time = started_at
        else:
            start_time = datetime.fromtimestamp(started_at / 1000)

        if stopped_at:
            if isinstance(stopped_at, datetime):
                end_time = stopped_at
            else:
                end_time = datetime.fromtimestamp(stopped_at / 1000)
        elif status in ("RUNNING", "STARTING"):
            end_time = datetime.now()
        else:
            return "-", 0

        duration_seconds = (end_time - start_time).total_seconds()

        if duration_seconds < 60:
            return f"{int(duration_seconds)}s", duration_seconds
        elif duration_seconds < 3600:
            minutes = int(duration_seconds / 60)
            seconds = int(duration_seconds % 60)
            return f"{minutes}m {seconds}s", duration_seconds
        else:
            hours = int(duration_seconds / 3600)
            minutes = int((duration_seconds % 3600) / 60)
            return f"{hours}h {minutes}m", duration_seconds

    def _build_job_id_to_folder_mapping(self) -> dict[str, str]:
        """Build mapping from AWS Batch job ID to log folder path and round info"""
        if self._job_id_to_folder is not None:
            return self._job_id_to_folder

        mapping = {}
        round_info_mapping = {}
        if not self.logs_base_dir.exists():
            logger.warning(f"Logs directory does not exist: {self.logs_base_dir}")
            self._job_id_to_folder = mapping
            self._job_id_to_round_info = round_info_mapping
            return mapping

        for metadata_file in self.logs_base_dir.rglob("metadata.json"):
            try:
                metadata = json.loads(metadata_file.read_text())
                job_id = metadata.get("aws", {}).get("AWS_BATCH_JOB_ID")
                if job_id:
                    folder_path = metadata_file.parent.relative_to(self.logs_base_dir)
                    mapping[job_id] = str(folder_path)

                    total_rounds = metadata.get("config", {}).get("tournament", {}).get("rounds")
                    round_stats = metadata.get("round_stats", {})
                    completed_rounds = sum(1 for round_key in round_stats.keys() if int(round_key) > 0)

                    if total_rounds is not None:
                        round_info_mapping[job_id] = (completed_rounds, total_rounds)
                    else:
                        round_info_mapping[job_id] = None
            except (json.JSONDecodeError, OSError, KeyError, ValueError) as e:
                logger.debug(f"Failed to read metadata from {metadata_file}: {e}")

        self._job_id_to_folder = mapping
        self._job_id_to_round_info = round_info_mapping
        logger.info(f"Built job ID mapping with {len(mapping)} entries")
        return mapping

    def _get_round_info(self, job_id: str) -> tuple[int, int] | None:
        """Get round info for a job"""
        if self._job_id_to_round_info is None:
            self._build_job_id_to_folder_mapping()
        return self._job_id_to_round_info.get(job_id) if self._job_id_to_round_info else None

    def _generate_aws_console_link(self, job_id: str) -> str:
        """Generate AWS console link for a job"""
        account_id = "039984708918"
        console_suffix = "4ppzlrng"
        return f"https://{account_id}-{console_suffix}.{self.region}.console.aws.amazon.com/batch/home?region={self.region}#jobs/ec2/detail/{job_id}"

    def _generate_emagedoc_link(self, job_id: str) -> str | None:
        """Generate emagedoc.xyz viewer link for a job"""
        mapping = self._build_job_id_to_folder_mapping()
        folder_path = mapping.get(job_id)
        if not folder_path:
            return None
        encoded_folder = quote(folder_path)
        return f"https://emagedoc.xyz/?folder={encoded_folder}"

    def _generate_s3_link(self, job_id: str) -> str | None:
        """Generate S3 console link for a job"""
        mapping = self._build_job_id_to_folder_mapping()
        folder_path = mapping.get(job_id)
        if not folder_path:
            return None
        account_id = "039984708918"
        console_suffix = "4ppzlrng"
        encoded_prefix = quote(f"logs/{folder_path}/")
        return f"https://{account_id}-{console_suffix}.{self.region}.console.aws.amazon.com/s3/buckets/codeclash?region={self.region}&bucketType=general&prefix={encoded_prefix}&showversions=false"

    def get_formatted_jobs(self, *, limit: int | None = None) -> list[dict[str, Any]]:
        """Get all jobs formatted for display"""
        jobs = self.list_jobs(limit=limit)
        return [self.format_job_for_display(job) for job in jobs]
