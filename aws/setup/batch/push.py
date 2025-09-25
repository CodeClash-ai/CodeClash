#!/usr/bin/env python3
"""Push AWS resources defined in JSON files to AWS."""

import argparse
import json
import logging
from pathlib import Path
from typing import Any

import boto3
from botocore.exceptions import ClientError

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def _update_batch_resource_tags(resource_type: str, resource_name: str, tags: dict, batch_client: Any) -> None:
    if not tags:
        return

    account_id = boto3.client("sts").get_caller_identity()["Account"]
    region = batch_client.meta.region_name
    resource_arn = f"arn:aws:batch:{region}:{account_id}:{resource_type}/{resource_name}"

    batch_client.tag_resource(resourceArn=resource_arn, tags=tags)


def _update_iam_role_tags(role_name: str, tags: list, iam_client: Any) -> None:
    if not tags:
        return

    existing_tags = iam_client.list_role_tags(RoleName=role_name)["Tags"]
    if existing_tags:
        tag_keys = [tag["Key"] for tag in existing_tags]
        iam_client.untag_role(RoleName=role_name, TagKeys=tag_keys)

    iam_client.tag_role(RoleName=role_name, Tags=tags)


def _update_iam_role(role: dict, iam_client: Any) -> None:
    """Update existing IAM role."""
    role_name = role["RoleName"]
    logger.info(f"Role {role_name} already exists, updating assume role policy")
    iam_client.update_assume_role_policy(
        RoleName=role_name, PolicyDocument=json.dumps(role["AssumeRolePolicyDocument"])
    )
    if "Description" in role:
        iam_client.update_role_description(RoleName=role_name, Description=role["Description"])

    _update_iam_role_tags(role_name, role.get("Tags"), iam_client)


def _create_iam_role(role: dict, iam_client: Any) -> None:
    """Create new IAM role."""
    role_name = role["RoleName"]
    logger.info(f"Creating new IAM role: {role_name}")
    create_params = {
        "RoleName": role_name,
        "AssumeRolePolicyDocument": json.dumps(role["AssumeRolePolicyDocument"]),
        "Description": role.get("Description", ""),
        "Path": role.get("Path", "/"),
        "MaxSessionDuration": role.get("MaxSessionDuration", 3600),
    }
    if "Tags" in role:
        create_params["Tags"] = role["Tags"]

    iam_client.create_role(**create_params)


def push_iam_role(role_data: dict, iam_client: Any) -> None:
    """Push IAM role to AWS."""
    role = role_data["Role"]
    role_name = role["RoleName"]

    roles = iam_client.list_roles()["Roles"]
    existing_role = next((r for r in roles if r["RoleName"] == role_name), None)

    if existing_role:
        _update_iam_role(role, iam_client)
    else:
        _create_iam_role(role, iam_client)

    logger.info(f"✅ Successfully pushed IAM role: {role_name}")


def _update_compute_environment(env_data: dict, batch_client: Any) -> None:
    """Update existing compute environment."""
    env_name = env_data["computeEnvironmentName"]
    logger.info(f"Compute environment {env_name} already exists, updating")

    update_params = {"computeEnvironment": env_name, "state": env_data.get("state", "ENABLED")}

    if "computeResources" in env_data:
        compute_resources = env_data["computeResources"].copy()
        compute_resources.pop("ec2Configuration", None)
        update_params["computeResources"] = compute_resources

    batch_client.update_compute_environment(**update_params)


def _create_compute_environment(env_data: dict, batch_client) -> None:
    """Create new compute environment."""
    env_name = env_data["computeEnvironmentName"]
    logger.info(f"Creating new compute environment: {env_name}")

    create_params = {
        "computeEnvironmentName": env_name,
        "type": env_data.get("type", "MANAGED"),
        "state": env_data.get("state", "ENABLED"),
    }

    if "computeResources" in env_data:
        create_params["computeResources"] = env_data["computeResources"]
    if "serviceRole" in env_data:
        create_params["serviceRole"] = env_data["serviceRole"]
    if "tags" in env_data:
        create_params["tags"] = env_data["tags"]

    batch_client.create_compute_environment(**create_params)


def push_compute_environment(env_data: dict, batch_client) -> None:
    """Push Batch compute environment to AWS."""
    env_name = env_data["computeEnvironmentName"]

    response = batch_client.describe_compute_environments(computeEnvironments=[env_name])

    if response["computeEnvironments"]:
        _update_compute_environment(env_data, batch_client)
        _update_batch_resource_tags("compute-environment", env_name, env_data.get("tags"), batch_client)
    else:
        _create_compute_environment(env_data, batch_client)

    logger.info(f"✅ Successfully pushed compute environment: {env_name}")


def push_job_queue(queue_data: dict, batch_client) -> None:
    """Push Batch job queue to AWS."""
    queue_name = queue_data["jobQueueName"]

    response = batch_client.describe_job_queues(jobQueues=[queue_name])

    if response["jobQueues"]:
        logger.info(f"Job queue {queue_name} already exists, updating")
        batch_client.update_job_queue(
            jobQueue=queue_name,
            state=queue_data.get("state", "ENABLED"),
            priority=queue_data.get("priority", 1),
            computeEnvironmentOrder=queue_data.get("computeEnvironmentOrder", []),
        )
        _update_batch_resource_tags("job-queue", queue_name, queue_data.get("tags"), batch_client)
    else:
        logger.info(f"Creating new job queue: {queue_name}")
        create_params = {
            "jobQueueName": queue_name,
            "state": queue_data.get("state", "ENABLED"),
            "priority": queue_data.get("priority", 1),
            "computeEnvironmentOrder": queue_data.get("computeEnvironmentOrder", []),
        }
        if "tags" in queue_data:
            create_params["tags"] = queue_data["tags"]

        batch_client.create_job_queue(**create_params)

    logger.info(f"✅ Successfully pushed job queue: {queue_name}")


def push_job_definition(job_data: dict, batch_client) -> None:
    """Push Batch job definition to AWS."""
    job_name = job_data["jobDefinitionName"]

    logger.info(f"Registering job definition: {job_name}")

    register_params = {
        "jobDefinitionName": job_name,
        "type": job_data.get("type", "container"),
        "platformCapabilities": job_data.get("platformCapabilities", ["EC2"]),
    }

    # Handle both old containerProperties and new ecsProperties formats
    if "ecsProperties" in job_data:
        register_params["ecsProperties"] = job_data["ecsProperties"]
    elif "containerProperties" in job_data:
        register_params["containerProperties"] = job_data["containerProperties"]

    if "parameters" in job_data:
        register_params["parameters"] = job_data["parameters"]
    if "tags" in job_data:
        register_params["tags"] = job_data["tags"]

    response = batch_client.register_job_definition(**register_params)
    revision = response["revision"]

    logger.info(f"✅ Successfully pushed job definition: {job_name}:{revision}")


def _update_launch_template(template_data: dict, existing_template: dict, ec2_client) -> None:
    """Update existing launch template by creating a new version."""
    template_name = template_data["LaunchTemplateName"]
    logger.info(f"Launch template {template_name} already exists, creating new version")

    create_params = {
        "LaunchTemplateId": existing_template["LaunchTemplateId"],
        "LaunchTemplateData": template_data["LaunchTemplateData"],
    }

    response = ec2_client.create_launch_template_version(**create_params)
    version = response["LaunchTemplateVersion"]["VersionNumber"]

    logger.info(f"✅ Successfully created new version {version} for launch template: {template_name}")


def _create_launch_template(template_data: dict, ec2_client) -> None:
    """Create new launch template."""
    template_name = template_data["LaunchTemplateName"]
    logger.info(f"Creating new launch template: {template_name}")

    create_params = {
        "LaunchTemplateName": template_name,
        "LaunchTemplateData": template_data["LaunchTemplateData"],
    }

    if "TagSpecifications" in template_data:
        create_params["TagSpecifications"] = template_data["TagSpecifications"]

    ec2_client.create_launch_template(**create_params)
    logger.info(f"✅ Successfully created launch template: {template_name}")


def push_launch_template(template_data: dict, ec2_client) -> None:
    """Push EC2 launch template to AWS."""
    template_name = template_data["LaunchTemplateName"]

    try:
        response = ec2_client.describe_launch_templates(LaunchTemplateNames=[template_name])
        existing_template = response["LaunchTemplates"][0]
        _update_launch_template(template_data, existing_template, ec2_client)
    except ClientError as e:
        if e.response["Error"]["Code"] == "InvalidLaunchTemplateName.NotFoundException":
            _create_launch_template(template_data, ec2_client)
        else:
            raise


def push_file(json_path: Path, region: str) -> None:
    """Push a single JSON file to AWS."""
    data = json.loads(json_path.read_text())
    filename = json_path.name

    match filename:
        case "iam-environment-role.json" | "iam-execution-role.json" | "iam-job-role.json" | "iam-ebs.json":
            push_iam_role(data, boto3.client("iam", region_name=region))
        case "environment.json":
            push_compute_environment(data, boto3.client("batch", region_name=region))
        case "job_queue.json":
            push_job_queue(data, boto3.client("batch", region_name=region))
        case "job_definition.json":
            push_job_definition(data, boto3.client("batch", region_name=region))
        case "launch_template.json":
            push_launch_template(data, boto3.client("ec2", region_name=region))
        case _:
            logger.error(f"Unknown filename: {filename}")
            raise ValueError(f"Unknown filename: {filename}")


def main():
    parser = argparse.ArgumentParser(description="Push AWS resources from JSON files")
    parser.add_argument("json_files", nargs="+", help="Path(s) to JSON file(s) containing resource definitions")
    parser.add_argument("--region", default="us-east-1", help="AWS region (default: us-east-1)")

    logger.info("Note: You need to wait a minute before updating job queue after you have pushed the environment.")

    args = parser.parse_args()

    for json_file in args.json_files:
        json_path = Path(json_file)
        logger.info(f"Pushing {json_path.name}")
        push_file(json_path, args.region)


if __name__ == "__main__":
    main()
