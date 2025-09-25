#!/bin/bash

set -euo pipefail

echo "📅 Container built at: $BUILD_TIMESTAMP"
echo "🔄 Updating repository..."

# First parameter is the branch name, rest are the command to execute
BRANCH_NAME="$1"
shift  # Remove first argument, leaving the rest for exec

echo "🌿 Checking out branch: $BRANCH_NAME"
git fetch
git checkout "$BRANCH_NAME"
git pull origin "$BRANCH_NAME"

source .venv/bin/activate

# Execute the remaining command arguments
exec "$@"
