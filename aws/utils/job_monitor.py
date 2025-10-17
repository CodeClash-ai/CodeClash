"""Job monitoring utilities for AWS Batch jobs."""

import time
from typing import Any

import boto3
from rich.console import Console
from rich.live import Live
from rich.table import Table

from codeclash.utils.log import get_logger

logger = get_logger("job_monitor", emoji="👀")


class JobMonitor:
    def __init__(self, region: str = "us-east-1"):
        self.batch_client = boto3.client("batch", region_name=region)
        self.console = Console()

    def get_job_status(self, job_id: str) -> dict[str, Any]:
        """Get the current status of a job."""
        response = self.batch_client.describe_jobs(jobs=[job_id])
        if response["jobs"]:
            return response["jobs"][0]
        else:
            raise ValueError(f"Job {job_id} not found")

    @staticmethod
    def format_duration(seconds: float) -> str:
        """Format duration in HH:MM:SS"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    @staticmethod
    def get_status_color(status: str) -> str:
        """Get the color for a job status."""
        status_lower = status.lower()
        if status_lower in ["submitted", "pending", "runnable"]:
            return "cyan"
        elif status_lower in ["starting", "running"]:
            return "yellow"
        elif status_lower == "succeeded":
            return "green"
        elif status_lower == "failed":
            return "red"
        else:
            return ""

    def create_status_table(self, jobs_info: dict[str, dict]) -> Table:
        """Create a rich table with job status information"""
        table = Table(title="AWS Batch Jobs Status")
        table.add_column("Status")
        table.add_column("Runtime", justify="right", style="magenta")
        table.add_column("Job ID", style="yellow")
        table.add_column("Config", style="green")

        for job_id, info in jobs_info.items():
            status = info["status"]
            color = self.get_status_color(status)
            status_colored = f"[{color}]{status}[/{color}]" if color else status

            table.add_row(
                status_colored,
                info["runtime"],
                job_id,
                info["config"],
            )

        return table

    def monitor(self, job_id_to_config: dict[str, str]) -> None:
        """Monitor submitted jobs and display status in real-time"""
        jobs_info: dict[str, dict] = {}
        start_times: dict[str, float] = {job_id: time.time() for job_id in job_id_to_config}

        self.console.print("\n[bold green]Note:[/] You can ^C this script without your jobs dying\n")

        try:
            with Live(self.create_status_table({}), refresh_per_second=1, console=self.console) as live:
                while True:
                    all_done = True
                    for job_id, config in job_id_to_config.items():
                        try:
                            job_status = self.get_job_status(job_id)
                            status = job_status["status"]
                            elapsed = time.time() - start_times[job_id]

                            jobs_info[job_id] = {
                                "status": status,
                                "runtime": self.format_duration(elapsed),
                                "config": config,
                            }

                            if status not in ["SUCCEEDED", "FAILED"]:
                                all_done = False
                        except Exception as e:
                            logger.error(f"Error getting status for {job_id}: {e}", exc_info=True)
                            jobs_info[job_id] = {
                                "status": "ERROR",
                                "runtime": self.format_duration(time.time() - start_times[job_id]),
                                "config": config,
                            }

                    live.update(self.create_status_table(jobs_info))

                    if all_done:
                        break

                    time.sleep(1)

            self.console.print("\n[bold green]All jobs completed![/]")
        except KeyboardInterrupt:
            self.console.print("\n[bold yellow]Monitoring stopped. Jobs continue running on AWS.[/]")
