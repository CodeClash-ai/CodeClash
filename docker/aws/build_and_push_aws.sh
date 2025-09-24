#!/bin/bash
set -euo pipefail

# Configuration
ECR_REGISTRY="039984708918.dkr.ecr.us-east-1.amazonaws.com"
ECR_REPOSITORY="codeclash"
IMAGE_TAG="latest"
REGION="us-east-1"
DOCKERFILE_PATH="AWSCodeClash.Dockerfile"
DOCKER_CONTEXT="."

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

# Build the Docker image
echo -e "${YELLOW}Building Docker image...${NC}"
FULL_IMAGE_NAME="$ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG"

# Authenticate with ECR
echo -e "${YELLOW}Authenticating with AWS ECR...${NC}"
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $ECR_REGISTRY

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
echo -e "${GREEN}You can now use this image in your AWS services.${NC}"
echo ""
echo -e "${YELLOW}IMPORTANT: When running this container on AWS Batch or other services,${NC}"
echo -e "${YELLOW}make sure to enable privileged mode for Docker-in-Docker functionality.${NC}"
echo -e "${YELLOW}For AWS Batch, add 'privileged: true' to your job definition.${NC}"
