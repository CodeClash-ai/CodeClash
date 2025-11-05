FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential git curl && \
    rm -rf /var/lib/apt/lists/*

RUN git clone https://github.com/CodeClash-ai/BattleCode.git /workspace \
    && cd /workspace \
    && git remote set-url origin https://github.com/CodeClash-ai/BattleCode.git
WORKDIR /workspace

RUN python run.py update
