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
    && usermod -aG docker root

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

# Create Docker directory and set permissions
RUN mkdir -p /var/lib/docker && chmod 755 /var/lib/docker

# Start Docker daemon temporarily to build game images
RUN dockerd --storage-driver=vfs --iptables=false --ip-masq=false & \
    # Wait for Docker daemon to be ready
    for i in {1..30}; do \
        if docker info >/dev/null 2>&1; then \
            echo "Docker daemon is ready for building images!"; \
            break; \
        fi; \
        if [ $i -eq 30 ]; then \
            echo "ERROR: Docker daemon failed to start"; \
            exit 1; \
        fi; \
        sleep 1; \
    done && \
    # Build all game-specific Docker images
    docker build --no-cache --build-arg GITHUB_TOKEN=${GITHUB_TOKEN} -t codeclash/battlesnake -f ../docker/BattleSnake.Dockerfile . && \
    docker build --no-cache --build-arg GITHUB_TOKEN=${GITHUB_TOKEN} -t codeclash/dummygame -f ../docker/DummyGame.Dockerfile . && \
    docker build --no-cache --build-arg GITHUB_TOKEN=${GITHUB_TOKEN} -t codeclash/robotrumble -f ../docker/RobotRumble.Dockerfile . && \
    docker build --no-cache --build-arg GITHUB_TOKEN=${GITHUB_TOKEN} -t codeclash/huskybench -f ../docker/HuskyBench.Dockerfile . && \
    # Stop the Docker daemon
    pkill dockerd || true && \
    # Wait for daemon to stop
    sleep 5

# Set build timestamp as environment variable
ARG BUILD_TIMESTAMP
ENV BUILD_TIMESTAMP=${BUILD_TIMESTAMP}

# Entry script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Note: Container must be run with --privileged flag for Docker-in-Docker
ENTRYPOINT ["/entrypoint.sh"]
