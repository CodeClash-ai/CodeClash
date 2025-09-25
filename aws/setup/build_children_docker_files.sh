#!/bin/bash
set -e

echo "Starting Docker daemon for image building..."

# Start Docker daemon in background
dockerd --config-file=/etc/docker/daemon.json > /var/log/dockerd-build.log 2>&1 &
DOCKERD_PID=$!
echo "Docker daemon PID: $DOCKERD_PID"

# Wait for Docker daemon to be ready with better error detection
for i in $(seq 1 60); do
    echo "Attempt $i/60: Checking Docker daemon status..."
    if docker info >/dev/null 2>&1; then
        echo "✅ Docker daemon is ready for building images!"
        break
    fi

    if ! kill -0 $DOCKERD_PID 2>/dev/null; then
        echo "❌ ERROR: Docker daemon process died. Log contents:"
        cat /var/log/dockerd-build.log
        exit 1
    fi

    if [ $i -eq 60 ]; then
        echo "❌ ERROR: Docker daemon failed to start after 60 seconds. Log contents:"
        cat /var/log/dockerd-build.log
        exit 1
    fi

    sleep 1
done

# Build all game-specific Docker images
echo "Building game-specific Docker images..."
docker build --no-cache --build-arg GITHUB_TOKEN=${GITHUB_TOKEN} -t codeclash/battlesnake -f ../../docker/BattleSnake.Dockerfile .
docker build --no-cache --build-arg GITHUB_TOKEN=${GITHUB_TOKEN} -t codeclash/dummygame -f ../../docker/DummyGame.Dockerfile .
docker build --no-cache --build-arg GITHUB_TOKEN=${GITHUB_TOKEN} -t codeclash/robotrumble -f ../../docker/RobotRumble.Dockerfile .
docker build --no-cache --build-arg GITHUB_TOKEN=${GITHUB_TOKEN} -t codeclash/huskybench -f ../../docker/HuskyBench.Dockerfile .

# Stop the Docker daemon gracefully
echo "Stopping Docker daemon..."
kill $DOCKERD_PID

# Wait for daemon to stop properly
for i in $(seq 1 10); do
    if ! kill -0 $DOCKERD_PID 2>/dev/null; then
        echo "✅ Docker daemon stopped successfully"
        break
    fi

    if [ $i -eq 10 ]; then
        echo "⚠️  Force killing Docker daemon"
        kill -9 $DOCKERD_PID || true
    fi

    sleep 1
done

echo "Docker image building completed successfully!"
