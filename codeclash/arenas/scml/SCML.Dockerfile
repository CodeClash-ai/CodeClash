FROM python:3.11-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
    ca-certificates git build-essential jq \
 && rm -rf /var/lib/apt/lists/*

RUN python -m pip install --upgrade pip \
 && python -m pip install scml==0.8.2

WORKDIR /workspace

COPY codeclash/arenas/scml/runtime/ /workspace/

RUN git init \
 && git config user.email "player@codeclash.com" \
 && git config user.name "Player" \
 && git add . \
 && git commit -m "Initial SCML workspace"
