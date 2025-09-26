#!/bin/bash

# This wrapper is used together with a script like main.py to run a command in a container
# while ensuring that docker is alive and guaranteeing to sync logs to S3 on exit.

echo "═══════════════════════════════════════════════════════════════════════════════"
echo "🚀 Wrapper script docker_and_sync.sh"
echo "═══════════════════════════════════════════════════════════════════════════════"

set -x
set -euo pipefail

echo "📅 Container built at: $BUILD_TIMESTAMP"


# Function to sync logs on exit
cleanup() {
    local exit_code=$?
    if [ -n "$(ls -A logs/ 2>/dev/null)" ]; then
        echo "Syncing logs to S3..."
        aws s3 sync logs/ s3://codeclash/logs/ || echo "Warning: Failed to sync logs to S3"
    else
        echo "No logs to sync"
    fi
    echo "Docker space usage:"
    docker system df
    echo "Docker cleanup"
    docker system prune -af
    echo "Docker space usage:"
    docker system df
    exit $exit_code
}

# Set trap to always sync logs on exit (normal exit, signals, errors)
trap cleanup EXIT

# Start Docker daemon with proper configuration for AWS Batch
echo "Starting Docker daemon..."
# Start daemon with config file and capture logs
dockerd --config-file=/etc/docker/daemon.json > /var/log/dockerd-runtime.log 2>&1 &
DOCKERD_PID=$!
echo "Docker daemon PID: $DOCKERD_PID"

# Wait for Docker daemon to be ready with better error detection
echo "Waiting for Docker daemon to start..."
for i in {1..60}; do
    echo "Attempt $i/60: Checking Docker daemon status..."
    if docker info >/dev/null 2>&1; then
        echo "✅ Docker daemon is ready!"
        break
    fi
    # Check if daemon process is still alive
    if ! kill -0 $DOCKERD_PID 2>/dev/null; then
        echo "❌ ERROR: Docker daemon process died. Log contents:"
        cat /var/log/dockerd-runtime.log
        exit 1
    fi
    if [ $i -eq 60 ]; then
        echo "❌ ERROR: Docker daemon failed to start after 60 seconds. Log contents:"
        cat /var/log/dockerd-runtime.log
        exit 1
    fi
    sleep 1
done

# Smoke test
docker run hello-world

echo "Docker space usage:"
docker system df

# Pull images from ECR so we don't have to build them
export AWS_DOCKER_REGISTRY="039984708918.dkr.ecr.us-east-1.amazonaws.com"
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin $AWS_DOCKER_REGISTRY
export AWS_S3_BUCKET="codeclash"
export AWS_S3_PREFIX="logs"

# Create logs directory
mkdir -p logs
# aws s3 sync s3://codeclash/logs/ logs/

# Set ulimit for number of open files, relevant for matrix
ulimit -n 65536

# Execute the command passed to container
"$@"

echo "═══════════════════════════════════════════════════════════════════════════════"
echo "✅ Wrapper script docker_and_sync.sh finished"
echo "═══════════════════════════════════════════════════════════════════════════════"
