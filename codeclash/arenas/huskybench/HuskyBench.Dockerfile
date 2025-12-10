FROM python:3.10-slim

ARG DEBIAN_FRONTEND=noninteractive
ENV TZ=Etc/UTC

RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    git \
    build-essential \
    unzip \
    lsof \
 && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

RUN git clone https://github.com/CodeClash-ai/HuskyBench.git /workspace \
    && cd /workspace \
    && git remote set-url origin https://github.com/CodeClash-ai/HuskyBench.git
WORKDIR /workspace

# Install Cython first (required build dependency for eval7, which doesn't declare it)
RUN uv pip install --system --no-cache-dir Cython
RUN uv pip install --system --no-cache-dir --no-build-isolation -r engine/requirements.txt
RUN mkdir -p /workspace/engine/output
