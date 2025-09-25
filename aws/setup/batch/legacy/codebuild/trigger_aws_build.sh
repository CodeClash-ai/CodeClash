#!/bin/bash
set -euo pipefail

# Configuration
PROJECT_NAME="codeclash-build"
REGION="us-east-1"
ECR_REPOSITORY="codeclash"
AWS_ACCOUNT_ID="039984708918"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 Triggering AWS CodeBuild for CodeClash (fast cloud build)...${NC}"
echo -e "${BLUE}💡 Tip: Use build_and_push_aws.sh as a fallback if CodeBuild is unavailable${NC}"

# Check if required tools are installed
command -v aws >/dev/null 2>&1 || { echo -e "${RED}Error: AWS CLI is required but not installed.${NC}" >&2; exit 1; }

# Check if GITHUB_TOKEN is set
if [ -z "${GITHUB_TOKEN:-}" ]; then
    echo -e "${RED}Error: GITHUB_TOKEN environment variable is required.${NC}"
    echo "Please set it with: export GITHUB_TOKEN=your_token_here"
    exit 1
fi

# Start the build
echo -e "${YELLOW}Starting CodeBuild project: $PROJECT_NAME${NC}"

BUILD_ID=$(aws codebuild start-build \
    --project-name "$PROJECT_NAME" \
    --environment-variables-override \
        name=GITHUB_TOKEN,value="$GITHUB_TOKEN" \
        name=AWS_DEFAULT_REGION,value="$REGION" \
        name=AWS_ACCOUNT_ID,value="$AWS_ACCOUNT_ID" \
        name=IMAGE_REPO_NAME,value="$ECR_REPOSITORY" \
    --query 'build.id' \
    --output text)

if [ $? -eq 0 ]; then
    echo -e "${GREEN}Build started successfully!${NC}"
    echo -e "${YELLOW}Build ID: $BUILD_ID${NC}"
    echo -e "${YELLOW}You can monitor the build at:${NC}"
    echo "https://$REGION.console.aws.amazon.com/codesuite/codebuild/projects/$PROJECT_NAME/build/$BUILD_ID"

    # Optional: Wait for build to complete
    read -p "Do you want to wait for the build to complete? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}⏳ Waiting for build to complete...${NC}"

        # Poll for completion
        while true; do
            STATUS=$(aws codebuild batch-get-builds --ids "$BUILD_ID" --query 'builds[0].buildStatus' --output text)
            case $STATUS in
                "SUCCEEDED")
                    echo -e "${GREEN}✅ Build completed successfully!${NC}"
                    echo -e "${GREEN}🐳 Docker image pushed to: $AWS_ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$ECR_REPOSITORY:latest${NC}"
                    break
                    ;;
                "FAILED"|"FAULT"|"STOPPED"|"TIMED_OUT")
                    echo -e "${RED}❌ Build failed with status: $STATUS${NC}"
                    echo -e "${YELLOW}💡 You can use the fallback script: ./build_and_push_aws.sh${NC}"
                    exit 1
                    ;;
                "IN_PROGRESS")
                    echo -e "${YELLOW}🔄 Build in progress...${NC}"
                    sleep 30
                    ;;
                *)
                    echo -e "${YELLOW}📊 Build status: $STATUS${NC}"
                    sleep 30
                    ;;
            esac
        done
    else
        echo -e "${BLUE}🔗 Monitor your build at:${NC}"
        echo "   https://$REGION.console.aws.amazon.com/codesuite/codebuild/projects/$PROJECT_NAME/build/$BUILD_ID"
        echo -e "${BLUE}💡 Or check status with:${NC}"
        echo "   aws codebuild batch-get-builds --ids $BUILD_ID --query 'builds[0].buildStatus'"
    fi
else
    echo -e "${RED}Failed to start build${NC}"
    exit 1
fi
