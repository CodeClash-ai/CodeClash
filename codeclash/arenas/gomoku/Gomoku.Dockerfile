FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

# Install Python 3.10, pip, and prerequisites
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
    curl ca-certificates python3.10 python3.10-venv \
    python3-pip python-is-python3 wget git build-essential jq curl locales \
 && rm -rf /var/lib/apt/lists/*

# Clone Gomoku game repository
RUN git clone https://github.com/CodeClash-ai/Gomoku.git /workspace \
    && cd /workspace \
    && git remote set-url origin https://github.com/CodeClash-ai/Gomoku.git
WORKDIR /workspace

# No additional dependencies needed - engine uses only standard library
