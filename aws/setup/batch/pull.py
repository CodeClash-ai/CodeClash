#!/usr/bin/env python3
"""Pull AWS resources and save them to JSON files."""

import argparse
import json
import logging
from pathlib import Path

import boto3

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def pull_iam_role(role_name: str, iam_client) -> dict:
    """Pull IAM role from AWS."""
    response = iam_client.get_role(RoleName=role_name)
    logger.info(f"✅ Successfully pulled IAM role: {role_name}")
    return response


def pull_compute_environment(env_name: str, batch_client) -> dict:
    """Pull Batch compute environment from AWS."""
    response = batch_client.describe_compute_environments(computeEnvironments=[env_name])
    env_data = response["computeEnvironments"][0]
    logger.info(f"✅ Successfully pulled compute environment: {env_name}")
    return env_data


def pull_job_queue(queue_name: str, batch_client) -> dict:
    """Pull Batch job queue from AWS."""
    response = batch_client.describe_job_queues(jobQueues=[queue_name])
    queue_data = response["jobQueues"][0]
    logger.info(f"✅ Successfully pulled job queue: {queue_name}")
    return queue_data


def pull_job_definition(job_name: str, batch_client) -> dict:
    """Pull Batch job definition from AWS."""
    response = batch_client.describe_job_definitions(jobDefinitionName=job_name, status="ACTIVE")

    if not response["jobDefinitions"]:
        raise ValueError(f"No job definitions found with name '{job_name}' and status 'ACTIVE'")

    latest_revision = max(jd["revision"] for jd in response["jobDefinitions"])
    job_data = next(jd for jd in response["jobDefinitions"] if jd["revision"] == latest_revision)

    logger.info(f"✅ Successfully pulled job definition: {job_data['jobDefinitionName']}:{job_data['revision']}")
    return job_data


def pull_launch_template(template_name: str, ec2_client) -> dict:
    """Pull EC2 launch template from AWS."""
    response = ec2_client.describe_launch_templates(LaunchTemplateNames=[template_name])
    template_data = response["LaunchTemplates"][0]

    # Get the latest version of the template
    version_response = ec2_client.describe_launch_template_versions(
        LaunchTemplateId=template_data["LaunchTemplateId"], Versions=["$Latest"]
    )
    template_version = version_response["LaunchTemplateVersions"][0]

    # Combine template metadata with version data
    result = {
        "LaunchTemplateName": template_data["LaunchTemplateName"],
        "LaunchTemplateData": template_version["LaunchTemplateData"],
    }

    # Add tags if they exist
    if template_data.get("Tags"):
        result["TagSpecifications"] = [
            {
                "ResourceType": "launch-template",
                "Tags": [{"Key": tag["Key"], "Value": tag["Value"]} for tag in template_data["Tags"]],
            }
        ]

    logger.info(f"✅ Successfully pulled launch template: {template_name}")
    return result


def clean_response_data(data: dict, is_iam_role: bool) -> dict:
    """Clean AWS response data to remove metadata and format for JSON storage."""
    if is_iam_role:
        return {"Role": data["Role"]}

    cleaned = data.copy()
    cleaned.pop("ResponseMetadata", None)
    cleaned.pop("createdAt", None)
    cleaned.pop("schedulingPriority", None)
    # Remove AWS-specific metadata fields for job definitions
    cleaned.pop("jobDefinitionArn", None)
    cleaned.pop("revision", None)
    cleaned.pop("status", None)
    cleaned.pop("containerOrchestrationType", None)
    return cleaned


def pull_file(json_path: Path, region: str) -> None:
    """Pull a single resource and save to JSON file."""
    filename = json_path.name

    match filename:
        case "iam-environment-role.json":
            data = pull_iam_role("kilian-codeclash-ecsInstanceRole", boto3.client("iam", region_name=region))
            cleaned_data = clean_response_data(data, is_iam_role=True)
        case "iam-execution-role.json":
            data = pull_iam_role("kilian-codeclash-execution-role", boto3.client("iam", region_name=region))
            cleaned_data = clean_response_data(data, is_iam_role=True)
        case "iam-job-role.json":
            data = pull_iam_role("kilian-codeclash-job-role", boto3.client("iam", region_name=region))
            cleaned_data = clean_response_data(data, is_iam_role=True)
        case "environment.json":
            data = pull_compute_environment("codeclash-batch", boto3.client("batch", region_name=region))
            cleaned_data = clean_response_data(data, is_iam_role=False)
        case "job_queue.json":
            data = pull_job_queue("codeclash-queue", boto3.client("batch", region_name=region))
            cleaned_data = clean_response_data(data, is_iam_role=False)
        case "job_definition.json":
            data = pull_job_definition("codeclash-default-job", boto3.client("batch", region_name=region))
            cleaned_data = clean_response_data(data, is_iam_role=False)
        case "launch_template.json":
            data = pull_launch_template("kilian-codeclash-launch-template", boto3.client("ec2", region_name=region))
            cleaned_data = data  # No cleaning needed for launch templates
        case _:
            logger.error(f"Unknown filename: {filename}")
            raise ValueError(f"Unknown filename: {filename}")

    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(cleaned_data, indent=2, default=str))
    logger.info(f"✅ Successfully saved to {json_path}")


def main():
    parser = argparse.ArgumentParser(description="Pull AWS resources and save to JSON files")
    parser.add_argument("json_files", nargs="+", help="Path(s) to JSON file(s) to save resource definitions")
    parser.add_argument("--region", default="us-east-1", help="AWS region (default: us-east-1)")

    args = parser.parse_args()

    for json_file in args.json_files:
        json_path = Path(json_file)
        logger.info(f"Pulling {json_path.name}")
        pull_file(json_path, args.region)


if __name__ == "__main__":
    main()
