FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive \
    GO_VERSION=1.22.0 \
    PATH=/usr/local/go/bin:/root/.local/bin:$PATH

# Install Python 3.10 and prerequisites (no pip needed - using uv)
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
    curl ca-certificates python3.10 python3.10-venv \
    python-is-python3 wget git build-essential jq locales \
 && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Set architecture and install Go 1.22
RUN ARCH=$(dpkg --print-architecture) && \
    echo "Building for architecture: $ARCH" && \
    curl -fsSL https://go.dev/dl/go${GO_VERSION}.linux-${ARCH}.tar.gz -o /tmp/go.tar.gz && \
    tar -C /usr/local -xzf /tmp/go.tar.gz && \
    rm /tmp/go.tar.gz

# Clone repository
RUN git clone https://github.com/CodeClash-ai/BattleSnake.git /workspace \
    && cd /workspace \
    && git remote set-url origin https://github.com/CodeClash-ai/BattleSnake.git
WORKDIR /workspace

RUN cd game && go build -o battlesnake ./cli/battlesnake/main.go
RUN uv pip install --system --no-cache-dir -r requirements.txt
