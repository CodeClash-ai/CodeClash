FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
    python3.10 python3-pip python-is-python3 wget git build-essential \
 && rm -rf /var/lib/apt/lists/*

RUN git clone https://github.com/CodeClash-ai/TexasHoldem.git /workspace \
    && cd /workspace \
    && git remote set-url origin https://github.com/CodeClash-ai/TexasHoldem.git

WORKDIR /workspace
