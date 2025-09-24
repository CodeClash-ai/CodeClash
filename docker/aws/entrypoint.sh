#!/bin/bash

set -euo pipefail

echo "📅 Container built at: $BUILD_TIMESTAMP"

echo "Git pull"
git pull

# Function to sync logs on exit
cleanup() {
    local exit_code=$?
    echo "Syncing logs to S3..."
    aws s3 sync logs/ s3://codeclash/logs/ || echo "Warning: Failed to sync logs to S3"
    exit $exit_code
}

# Set trap to always sync logs on exit (normal exit, signals, errors)
trap cleanup EXIT

# Start Docker daemon with proper configuration for AWS Batch
echo "Starting Docker daemon..."
# Use vfs storage driver to avoid overlay permission issues
dockerd --storage-driver=vfs --iptables=false --ip-masq=false --bridge=none &

# Wait for Docker daemon to be ready
echo "Waiting for Docker daemon to start..."
for i in {1..30}; do
    if docker info >/dev/null 2>&1; then
        echo "Docker daemon is ready!"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "ERROR: Docker daemon failed to start after 30 seconds"
        exit 1
    fi
    sleep 1
done

# Smoke test
docker run hello-world

# Activate venv
source .venv/bin/activate

# Create logs directory
mkdir -p logs
# aws s3 sync s3://codeclash/logs/ logs/

# Set ulimit for number of open files, relevant for matrix
ulimit -n 65536

# Execute the command passed to container
exec "$@"
