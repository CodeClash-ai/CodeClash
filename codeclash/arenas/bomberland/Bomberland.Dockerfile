FROM python:3.11-slim-bookworm

ARG BOMBERLAND_COMMIT=8b6b7a1c013d96feb0a5468a7a59a63a7c59dadc
ENV BOMBERLAND_UPSTREAM_COMMIT=${BOMBERLAND_COMMIT}

RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Keep a pinned copy of the upstream competition source for provenance and
# agent authors who want to inspect the original starter-kit shape.
RUN git clone https://github.com/CoderOneHQ/bomberland.git /opt/bomberland \
    && cd /opt/bomberland \
    && git checkout ${BOMBERLAND_COMMIT}

WORKDIR /workspace
COPY codeclash/arenas/bomberland/runtime/ /workspace/

RUN git init \
    && git config user.email "arena@codeclash.com" \
    && git config user.name "CodeClash Arena" \
    && git add . \
    && git commit -m "Initialize Bomberland runtime"
