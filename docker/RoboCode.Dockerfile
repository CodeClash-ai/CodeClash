FROM maven:3.9-eclipse-temurin-24

ARG DEBIAN_FRONTEND=noninteractive
ENV TZ=Etc/UTC

# Install Python 3.10+, pip, and common tools
RUN apt update && apt install -y \
    wget \
    git \
    build-essential \
    ant \
    unzip \
    python3 \
    python3-pip \
    python3-venv \
 && ln -sf /usr/bin/python3 /usr/bin/python \
 && ln -sf /usr/bin/pip3 /usr/bin/pip \
 && rm -rf /var/lib/apt/lists/*

ARG GITHUB_TOKEN
RUN git clone https://${GITHUB_TOKEN}@github.com/CodeClash-ai/RoboCode.git /workspace \
    && cd /workspace \
    && git remote set-url origin https://github.com/CodeClash-ai/RoboCode.git \
    && unset GITHUB_TOKEN

WORKDIR /workspace
