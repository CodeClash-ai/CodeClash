FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

# Install Python 3.10 and basic tools
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
    curl ca-certificates python3.10 python3.10-venv \
    python3-pip python-is-python3 wget git build-essential jq curl locales \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

# Copy Bridge game server code (game logic, deck management, scoring)
COPY codeclash/arenas/bridge/game_server /workspace/game_server

# No additional dependencies needed - game logic is pure Python
