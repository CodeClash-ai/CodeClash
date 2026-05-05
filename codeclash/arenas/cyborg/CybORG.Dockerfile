FROM python:3.11-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
    ca-certificates git build-essential jq \
 && rm -rf /var/lib/apt/lists/*

RUN python -m pip install --upgrade pip \
 && git clone https://github.com/cage-challenge/CybORG.git /opt/CybORG \
 && cd /opt/CybORG \
 && git checkout a2d03f99e587af153ae0ac50fb94ba6272e4fff2 \
 && python -m pip install "numpy<1.24" -e /opt/CybORG

WORKDIR /workspace

COPY codeclash/arenas/cyborg/runtime/ /workspace/

RUN git init \
 && git config user.email "player@codeclash.com" \
 && git config user.name "Player" \
 && git add . \
 && git commit -m "Initial CybORG workspace"
