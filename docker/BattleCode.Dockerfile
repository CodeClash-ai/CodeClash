FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential git curl && \
    rm -rf /var/lib/apt/lists/*

ARG GITHUB_TOKEN
RUN git clone https://${GITHUB_TOKEN}@github.com/emagedoc/BattleCode.git /testbed \
    && cd /testbed \
    && git remote set-url origin https://github.com/emagedoc/BattleCode.git \
    && unset GITHUB_TOKEN
WORKDIR /testbed

RUN python run.py update
