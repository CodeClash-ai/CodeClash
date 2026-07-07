FROM python:3.11-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# Pin numpy/BLAS to a single math thread per container. Each SCML simulation is
# single-threaded compute (measured: pinned solo == unpinned solo)
ENV OMP_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1 \
    MKL_NUM_THREADS=1 \
    NUMEXPR_NUM_THREADS=1

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
    ca-certificates git build-essential jq \
 && rm -rf /var/lib/apt/lists/*

RUN python -m pip install --upgrade pip \
 && python -m pip install scml==0.8.2

# Clone the arena repo so `origin` is set for branch_init / push (matches the other
# arenas). Default branch holds the runtime; human/* branches overlay scml_agent.py.
RUN git clone https://github.com/CodeClash-ai/SCML.git /workspace \
    && cd /workspace \
    && git remote set-url origin https://github.com/CodeClash-ai/SCML.git \
    && git config user.email "player@codeclash.com" \
    && git config user.name "Player"
WORKDIR /workspace
