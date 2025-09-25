#!/bin/bash
set -euo pipefail

# Configuration
PROJECT_NAME="codeclash-build"
REGION="us-east-1"
ECR_REPOSITORY="codeclash"
AWS_ACCOUNT_ID="039984708918"
GITHUB_REPO="emagedoc/CodeClash"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Creating AWS CodeBuild project for CodeClash...${NC}"

# Check if project already exists
# if aws codebuild batch-get-projects --names "$PROJECT_NAME" --region "$REGION" >/dev/null 2>&1; then
#     echo -e "${YELLOW}Project $PROJECT_NAME already exists. Updating...${NC}"
#     ACTION="update-project"
# else
#     echo -e "${YELLOW}Creating new project $PROJECT_NAME...${NC}"
ACTION="create-project"
# fi

# Create or update the CodeBuild project
aws codebuild $ACTION \
    --name "$PROJECT_NAME" \
    --description "Build CodeClash Docker images on AWS" \
    --source type=S3,location="codeclash-source/source.zip" \
    --artifacts type=NO_ARTIFACTS \
    --environment type=LINUX_CONTAINER,image=aws/codebuild/standard:7.0,computeType=BUILD_GENERAL1_MEDIUM,privilegedMode=true \
    --service-role "arn:aws:iam::$AWS_ACCOUNT_ID:role/kilian-codeclash-codebuild-service-role" \
    --region "$REGION"

if [ $? -eq 0 ]; then
    echo -e "${GREEN}CodeBuild project created/updated successfully!${NC}"
    echo -e "${YELLOW}Project details:${NC}"
    echo "  Name: $PROJECT_NAME"
    echo "  Region: $REGION"
    echo "  GitHub Repo: $GITHUB_REPO"
    echo "  Build Spec: docker/aws/buildspec.yml"
    echo ""
    echo -e "${GREEN}Next steps:${NC}"
    echo "1. Make sure your GitHub repo has the buildspec.yml file committed"
    echo "2. Set up GitHub webhook (optional) for automatic builds"
    echo "3. Use trigger_aws_build.sh to start builds"
    echo ""
    echo -e "${YELLOW}Console URL:${NC}"
    echo "https://$REGION.console.aws.amazon.com/codesuite/codebuild/projects/$PROJECT_NAME"
else
    echo -e "${RED}Failed to create/update CodeBuild project${NC}"
    echo -e "${YELLOW}You may need to:${NC}"
    echo "1. Create a CodeBuild service role with ECR permissions"
    echo "2. Ensure you have proper IAM permissions"
    exit 1
fi
