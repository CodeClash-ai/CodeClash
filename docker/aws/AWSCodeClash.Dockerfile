FROM ubuntu:22.04

# Install system dependencies
RUN apt update && apt install -y \
    python3-pip \
    python3.10-venv \
    git \
    curl \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Install Docker
RUN curl -fsSL https://get.docker.com -o get-docker.sh && sh get-docker.sh

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
    && pip install -e .

# Set ulimit for open files
RUN echo "* soft nofile 65536" >> /etc/security/limits.conf \
    && echo "* hard nofile 65536" >> /etc/security/limits.conf

# Entry script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
