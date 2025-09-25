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

# Copy and run the Docker image building script
COPY build_children_docker_files.sh /build_children_docker_files.sh
RUN chmod +x /build_children_docker_files.sh && \
    /build_children_docker_files.sh

# Set build timestamp as environment variable
ARG BUILD_TIMESTAMP
ENV BUILD_TIMESTAMP=${BUILD_TIMESTAMP}

# Entry script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Note: Container must be run with --privileged flag for Docker-in-Docker
ENTRYPOINT ["/entrypoint.sh"]
