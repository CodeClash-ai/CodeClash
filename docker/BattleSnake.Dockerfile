FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive \
    GO_VERSION=1.22.0 \
    PATH=/usr/local/go/bin:$PATH

# Install Python 3.10 (and alias python→python3.10), pip, and prerequisites
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
    curl ca-certificates python3.10 python3.10-venv \
    python3-pip python-is-python3 wget git build-essential jq curl locales \
 && rm -rf /var/lib/apt/lists/*

# Set architecture and install Go 1.22
RUN ARCH=$(dpkg --print-architecture) && \
    echo "Building for architecture: $ARCH" && \
    curl -fsSL https://go.dev/dl/go${GO_VERSION}.linux-${ARCH}.tar.gz -o /tmp/go.tar.gz && \
    tar -C /usr/local -xzf /tmp/go.tar.gz && \
    rm /tmp/go.tar.gz

# Inject GitHub token for private repo access
ARG GITHUB_TOKEN
RUN git clone https://${GITHUB_TOKEN}@github.com/emagedoc/BattleSnake.git /workspace \
    && cd /workspace \
    && git remote set-url origin https://github.com/emagedoc/BattleSnake.git \
    && unset GITHUB_TOKEN

WORKDIR /workspace

RUN cd game && go build -o battlesnake ./cli/battlesnake/main.go
RUN pip install -r requirements.txt
