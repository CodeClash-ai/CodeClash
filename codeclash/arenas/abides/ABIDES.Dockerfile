FROM python:3.11-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/opt/abides

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
    ca-certificates git build-essential jq \
 && rm -rf /var/lib/apt/lists/*

COPY codeclash/arenas/abides/constraints.txt /tmp/abides-constraints.txt

RUN python -m pip install pip==26.1.1 \
 && git clone https://github.com/abides-sim/abides.git /opt/abides \
 && cd /opt/abides \
 && git checkout c4bf157678928934417aba6073eb0651aeaf6d15 \
 && python -c "from pathlib import Path; p = Path('/opt/abides/util/OrderBook.py'); s = p.read_text(); p.write_text(s.replace('from pandas.io.json import json_normalize', 'from pandas import json_normalize'))" \
 && python -m pip install -e /opt/abides -c /tmp/abides-constraints.txt

WORKDIR /workspace

COPY codeclash/arenas/abides/runtime/ /workspace/

RUN git init \
 && git config user.email "player@codeclash.com" \
 && git config user.name "Player" \
 && git add . \
 && git commit -m "Initial ABIDES workspace"
