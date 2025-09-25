#!/usr/bin/env python3

import argparse
import json
import logging
from pathlib import Path

import boto3

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def clean_old_job_definitions(job_name: str, batch_client) -> int:
    response = batch_client.describe_job_definitions(jobDefinitionName=job_name, status="ACTIVE")

    job_definitions = response["jobDefinitions"]

    if not job_definitions:
        logger.info(f"No active job definitions found for: {job_name}")
        return 0

    job_definitions.sort(key=lambda x: x["revision"])
    old_revisions = job_definitions[:-1]

    logger.info(f"Found {len(job_definitions)} active revisions for {job_name}")
    logger.info(f"Latest revision: {job_definitions[-1]['revision']}")

    if not old_revisions:
        logger.info("No old revisions to clean up")
        return 0

    for job_def in old_revisions:
        logger.info(f"Deregistering old revision: {job_name}:{job_def['revision']}")
        batch_client.deregister_job_definition(jobDefinition=job_def["jobDefinitionArn"])

    logger.info(f"✅ Successfully cleaned up {len(old_revisions)} old revisions for {job_name}")
    return len(old_revisions)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("job_definition_json", nargs="?", default="job_definition.json")
    parser.add_argument("--region", default="us-east-1")

    args = parser.parse_args()

    json_path = Path(args.job_definition_json)
    data = json.loads(json_path.read_text())
    job_name = data["jobDefinitionName"]

    batch_client = boto3.client("batch", region_name=args.region)
    clean_old_job_definitions(job_name, batch_client)


if __name__ == "__main__":
    main()
