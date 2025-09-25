#!/bin/bash

set -euo pipefail

echo "═══════════════════════════════════════════════════════════════════════════════"
echo "🚀 Hello from docker_entrypoint.sh"
echo "═══════════════════════════════════════════════════════════════════════════════"

echo "📅 Container built at: $BUILD_TIMESTAMP"
echo "🔄 Updating repository..."

# First parameter is the branch name, rest are the command to execute
BRANCH_NAME="$1"
shift  # Remove first argument, leaving the rest for exec

echo "🌿 Checking out branch: $BRANCH_NAME"
git fetch
git checkout "$BRANCH_NAME"
git pull origin "$BRANCH_NAME"

echo "Last commit information:"
git log -1 --pretty=format:"   Hash: %H%n   Message: %s%n   Author: %an <%ae>%n   Date: %ad" --date=format:"%Y-%m-%d %H:%M:%S %Z"
echo

echo "🚀 AWS Batch Environment Variables:"
echo "  AWS_BATCH_CE_NAME: ${AWS_BATCH_CE_NAME:-<not set>}"
echo "  AWS_BATCH_JOB_ATTEMPT: ${AWS_BATCH_JOB_ATTEMPT:-<not set>}"
echo "  AWS_BATCH_JOB_ID: ${AWS_BATCH_JOB_ID:-<not set>}"
echo "  AWS_BATCH_JQ_NAME: ${AWS_BATCH_JQ_NAME:-<not set>}"

echo "💾 Disk usage before job:"
df -h

source .venv/bin/activate

echo "═══════════════════════════════════════════════════════════════════════════════"
echo "User provided command starting below:"
echo "$@"
echo "═══════════════════════════════════════════════════════════════════════════════"
# Execute the remaining command arguments
exec "$@"
echo "═══════════════════════════════════════════════════════════════════════════════"
echo "✅ User provided command finished"
echo "═══════════════════════════════════════════════════════════════════════════════"

echo "💾 Disk usage after job:"
df -h

echo "═══════════════════════════════════════════════════════════════════════════════"
echo "✅ docker_entrypoint.sh finished"
echo "═══════════════════════════════════════════════════════════════════════════════"
