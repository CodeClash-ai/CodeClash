#!/bin/bash

# This script is used to build and push a Docker image to AWS ECR
# Example usage:
# ./build_and_push_aws.sh AWSCodeClash.Dockerfile codeclash .
# from parent directory:
# ./aws/build_and_push_aws.sh BattleSnake.Dockerfile codeclash/battlesnake .

set -euo pipefail

# Check if required arguments are provided
if [ $# -lt 3 ]; then
    echo "Usage: $0 <dockerfile_path> <ecr_repository> <docker_context>"
    echo "Example: $0 AWSCodeClash.Dockerfile codeclash ."
    exit 1
fi

DOCKERFILE_PATH="$1"
ECR_REPOSITORY="$2"
DOCKER_CONTEXT="$3"

# Check if dockerfile exists
if [ ! -f "$DOCKERFILE_PATH" ]; then
    echo "Error: Dockerfile '$DOCKERFILE_PATH' not found."
    exit 1
fi

# Check if docker context exists
if [ ! -d "$DOCKER_CONTEXT" ] && [ "$DOCKER_CONTEXT" != "." ]; then
    echo "Error: Docker context directory '$DOCKER_CONTEXT' not found."
    exit 1
fi

# Configuration
ECR_REGISTRY="039984708918.dkr.ecr.us-east-1.amazonaws.com"
IMAGE_TAG="latest"
REGION="us-east-1"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting AWS ECR build and push process...${NC}"

# Check if required tools are installed
command -v aws >/dev/null 2>&1 || { echo -e "${RED}Error: AWS CLI is required but not installed.${NC}" >&2; exit 1; }
command -v docker >/dev/null 2>&1 || { echo -e "${RED}Error: Docker is required but not installed.${NC}" >&2; exit 1; }

# Check if GITHUB_TOKEN is set (required for the Dockerfile)
if [ -z "${GITHUB_TOKEN:-}" ]; then
    echo -e "${RED}Error: GITHUB_TOKEN environment variable is required for building this container.${NC}"
    echo "Please set it with: export GITHUB_TOKEN=your_token_here"
    exit 1
fi

# Verify AWS account identity
echo -e "${YELLOW}Checking AWS account identity...${NC}"
CURRENT_ACCOUNT=$(aws sts get-caller-identity --query Account --output text 2>/dev/null || echo "unknown")
EXPECTED_ACCOUNT=$(echo $ECR_REGISTRY | cut -d'.' -f1)
if [ "$CURRENT_ACCOUNT" != "$EXPECTED_ACCOUNT" ]; then
    echo -e "${RED}ERROR: Your current AWS account ($CURRENT_ACCOUNT) does NOT match the target ECR account ($EXPECTED_ACCOUNT)!${NC}"
    exit 1
fi
echo -e "${GREEN}✓ AWS account matches target ECR account${NC}"

# Build the Docker image
echo -e "${YELLOW}Building Docker image...${NC}"
FULL_IMAGE_NAME="$ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG"

# Authenticate with ECR
echo -e "${YELLOW}Authenticating with AWS ECR...${NC}"
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $ECR_REGISTRY

# Check if ECR repository exists, create if it doesn't
echo -e "${YELLOW}Checking if ECR repository '$ECR_REPOSITORY' exists...${NC}"
if ! aws ecr describe-repositories --repository-names "$ECR_REPOSITORY" --region "$REGION" >/dev/null 2>&1; then
    echo -e "${YELLOW}Repository '$ECR_REPOSITORY' does not exist. Creating it...${NC}"
    aws ecr create-repository --repository-name "$ECR_REPOSITORY" --region "$REGION"
    echo -e "${GREEN}Successfully created ECR repository: $ECR_REPOSITORY${NC}"
else
    echo -e "${GREEN}ECR repository '$ECR_REPOSITORY' already exists.${NC}"
fi

docker build \
    --build-arg GITHUB_TOKEN="$GITHUB_TOKEN" \
    --build-arg BUILD_TIMESTAMP="$(date -u '+%Y-%m-%d %H:%M:%S UTC')" \
    --platform linux/amd64 \
    -f "$DOCKERFILE_PATH" \
    -t "$FULL_IMAGE_NAME" \
    "$DOCKER_CONTEXT"

# Push the image to ECR
echo -e "${YELLOW}Pushing image to ECR...${NC}"
docker push "$FULL_IMAGE_NAME"

echo -e "${GREEN}Successfully built and pushed image: $FULL_IMAGE_NAME${NC}"
