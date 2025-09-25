import os
import subprocess
from logging import Logger


def is_running_in_aws_batch() -> bool:
    """Returns True if running in AWS Batch, False otherwise."""
    return os.getenv("AWS_BATCH_JOB_ID") is not None


def get_aws_metadata() -> dict:
    """Returns a dictionary of AWS metadata."""
    if not is_running_in_aws_batch():
        return {}
    # Official AWS Batch environment variables as documented at:
    # https://docs.aws.amazon.com/batch/latest/userguide/job_env_vars.html
    env_variables = [
        "AWS_BATCH_CE_NAME",
        "AWS_BATCH_JOB_ATTEMPT",
        "AWS_BATCH_JOB_ID",
        "AWS_BATCH_JQ_NAME",
    ]
    return {env_variable: os.getenv(env_variable) for env_variable in env_variables}


def pull_game_container_aws_ecr(*, game_name: str, image_name: str, logger: Logger) -> None:
    """Pull a game container from AWS ECR and tag it with the local name.

    Args:
        game_name: The game name (e.g., 'BattleSnake')
        image_name: The local image name (e.g., 'codeclash/battlesnake')
        logger: Logger instance for debug output

    Raises:
        AssertionError: If AWS_DOCKER_REGISTRY is not set
        RuntimeError: If docker pull or tag fails
    """
    logger.info(f"Running in AWS Batch, pulling Docker image {image_name}")

    aws_docker_registry = os.getenv("AWS_DOCKER_REGISTRY")
    assert aws_docker_registry is not None, (
        "AWS_DOCKER_REGISTRY environment variable must be set when running in AWS Batch"
    )

    registry_image = f"{aws_docker_registry}/codeclash/{game_name.lower()}"

    logger.debug(f"Pulling {registry_image} and tagging as {image_name}")
    result = subprocess.run(
        f"docker pull {registry_image} && docker tag {registry_image} {image_name}",
        shell=True,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        logger.error(f"❌ Failed to pull and tag Docker image: {result.stderr}\n{result.stdout}")
        raise RuntimeError(f"Failed to pull and tag Docker image: {result.stderr}")

    logger.info(f"✅ Pulled and tagged Docker image {image_name}")
