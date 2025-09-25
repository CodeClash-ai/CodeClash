FROM ubuntu:22.04

# Install system dependencies
RUN apt update && apt install -y \
    python3-pip \
    python3.10-venv \
    git \
    curl \
    unzip \
    iptables \
    ca-certificates \
    gnupg \
    lsb-release \
    && rm -rf /var/lib/apt/lists/*

# Install Docker with proper setup for Docker-in-Docker
RUN curl -fsSL https://get.docker.com -o get-docker.sh && sh get-docker.sh \
    && usermod -aG docker root \
    && rm get-docker.sh

# Install AWS CLI
RUN curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip" \
    && unzip awscliv2.zip \
    && ./aws/install \
    && rm -rf aws awscliv2.zip

# Set up working directory
WORKDIR /app

# Clone repository (you'll pass GITHUB_TOKEN as env var)
ARG GITHUB_TOKEN
RUN git clone https://klieret:${GITHUB_TOKEN}@github.com/emagedoc/CodeClash.git . \
    && python3 -m venv .venv \
    && . .venv/bin/activate \
    && pip install -e '.[dev]'

# Set ulimit for open files
RUN echo "* soft nofile 65536" >> /etc/security/limits.conf \
    && echo "* hard nofile 65536" >> /etc/security/limits.conf

# Create Docker directories and set proper permissions
RUN mkdir -p /var/lib/docker /var/run/docker \
    && chmod 755 /var/lib/docker /var/run/docker \
    && mkdir -p /etc/docker \
    && echo '{"storage-driver": "vfs", "iptables": false, "ip-masq": false, "log-driver": "json-file", "log-opts": {"max-size": "10m", "max-file": "3"}}' > /etc/docker/daemon.json

# Start Docker daemon temporarily to build game images
RUN echo "Starting Docker daemon for image building..." && \
    dockerd --config-file=/etc/docker/daemon.json > /var/log/dockerd-build.log 2>&1 & \
    DOCKERD_PID=$! && \
    echo "Docker daemon PID: $DOCKERD_PID" && \
    # Wait for Docker daemon to be ready with better error detection
    for i in {1..60}; do \
        echo "Attempt $i/60: Checking Docker daemon status..." && \
        if docker info >/dev/null 2>&1; then \
            echo "✅ Docker daemon is ready for building images!"; \
            break; \
        fi; \
        if ! kill -0 $DOCKERD_PID 2>/dev/null; then \
            echo "❌ ERROR: Docker daemon process died. Log contents:"; \
            cat /var/log/dockerd-build.log; \
            exit 1; \
        fi; \
        if [ $i -eq 60 ]; then \
            echo "❌ ERROR: Docker daemon failed to start after 60 seconds. Log contents:"; \
            cat /var/log/dockerd-build.log; \
            exit 1; \
        fi; \
        sleep 1; \
    done && \
    # Build all game-specific Docker images
    docker build --no-cache --build-arg GITHUB_TOKEN=${GITHUB_TOKEN} -t codeclash/battlesnake -f ../docker/BattleSnake.Dockerfile . && \
    docker build --no-cache --build-arg GITHUB_TOKEN=${GITHUB_TOKEN} -t codeclash/dummygame -f ../docker/DummyGame.Dockerfile . && \
    docker build --no-cache --build-arg GITHUB_TOKEN=${GITHUB_TOKEN} -t codeclash/robotrumble -f ../docker/RobotRumble.Dockerfile . && \
    docker build --no-cache --build-arg GITHUB_TOKEN=${GITHUB_TOKEN} -t codeclash/huskybench -f ../docker/HuskyBench.Dockerfile . && \
    # Stop the Docker daemon gracefully
    echo "Stopping Docker daemon..." && \
    kill $DOCKERD_PID && \
    # Wait for daemon to stop properly
    for i in {1..10}; do \
        if ! kill -0 $DOCKERD_PID 2>/dev/null; then \
            echo "✅ Docker daemon stopped successfully"; \
            break; \
        fi; \
        if [ $i -eq 10 ]; then \
            echo "⚠️  Force killing Docker daemon"; \
            kill -9 $DOCKERD_PID || true; \
        fi; \
        sleep 1; \
    done

# Set build timestamp as environment variable
ARG BUILD_TIMESTAMP
ENV BUILD_TIMESTAMP=${BUILD_TIMESTAMP}

# Entry script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Note: Container must be run with --privileged flag for Docker-in-Docker
ENTRYPOINT ["/entrypoint.sh"]
