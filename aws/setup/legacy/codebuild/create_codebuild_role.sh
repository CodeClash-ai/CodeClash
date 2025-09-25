#!/bin/bash
set -euo pipefail

# Configuration
ROLE_NAME="kilian-codeclash-codebuild-service-role"
POLICY_NAME="CodeBuildServiceRolePolicy"
REGION="us-east-1"
AWS_ACCOUNT_ID="039984708918"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Creating CodeBuild service role and policies...${NC}"

# Create trust policy for CodeBuild
cat > /tmp/codebuild-trust-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "codebuild.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

# Create the service role
echo -e "${YELLOW}Creating IAM role: $ROLE_NAME${NC}"
if aws iam get-role --role-name "$ROLE_NAME" >/dev/null 2>&1; then
    echo -e "${YELLOW}Role $ROLE_NAME already exists, skipping creation${NC}"
else
    aws iam create-role \
        --role-name "$ROLE_NAME" \
        --assume-role-policy-document file:///tmp/codebuild-trust-policy.json \
        --description "Service role for CodeBuild to build CodeClash Docker images"
    echo -e "${GREEN}✅ Created IAM role: $ROLE_NAME${NC}"
fi

# Create policy for ECR + minimal logging (required by CodeBuild)
cat > /tmp/codebuild-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:$REGION:$AWS_ACCOUNT_ID:log-group:/aws/codebuild/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "ecr:BatchCheckLayerAvailability",
        "ecr:GetDownloadUrlForLayer",
        "ecr:BatchGetImage",
        "ecr:GetAuthorizationToken",
        "ecr:InitiateLayerUpload",
        "ecr:UploadLayerPart",
        "ecr:CompleteLayerUpload",
        "ecr:PutImage"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:GetObjectVersion"
      ],
      "Resource": "arn:aws:s3:::codeclash-source/*"
    }
  ]
}
EOF

# Attach the ECR + logging policy
echo -e "${YELLOW}Creating and attaching ECR + logging policy: $POLICY_NAME${NC}"
if aws iam get-role-policy --role-name "$ROLE_NAME" --policy-name "$POLICY_NAME" >/dev/null 2>&1; then
    echo -e "${YELLOW}Policy $POLICY_NAME already exists, updating...${NC}"
    aws iam put-role-policy \
        --role-name "$ROLE_NAME" \
        --policy-name "$POLICY_NAME" \
        --policy-document file:///tmp/codebuild-policy.json
else
    aws iam put-role-policy \
        --role-name "$ROLE_NAME" \
        --policy-name "$POLICY_NAME" \
        --policy-document file:///tmp/codebuild-policy.json
fi
echo -e "${GREEN}✅ Attached ECR + logging policy: $POLICY_NAME${NC}"

# Clean up temporary files
rm -f /tmp/codebuild-trust-policy.json /tmp/codebuild-policy.json

# Wait a moment for IAM to propagate
echo -e "${YELLOW}⏳ Waiting for IAM role to propagate...${NC}"
sleep 10

echo -e "${GREEN}✅ CodeBuild service role setup complete!${NC}"
echo -e "${YELLOW}Role ARN:${NC} arn:aws:iam::$AWS_ACCOUNT_ID:role/service-role/$ROLE_NAME"
echo ""
echo -e "${GREEN}Next steps:${NC}"
echo "1. Run ./create_codebuild_project.sh to create the CodeBuild project"
echo "2. Commit and push buildspec.yml to your repository"
echo "3. Use ./trigger_aws_build.sh to start fast cloud builds"
