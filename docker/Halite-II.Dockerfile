FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

# Install Python 3.10 (and alias python→python3.10), pip, and prerequisites
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
    curl ca-certificates python3.10 python3.10-venv \
    python3-pip python-is-python3 wget git build-essential jq curl locales cmake \
 && rm -rf /var/lib/apt/lists/*

# Install Rust via rustup
RUN curl https://sh.rustup.rs -sSf | sh -s -- -y \
    && . "$HOME/.cargo/env" \
    && echo 'source $HOME/.cargo/env' >> /etc/bash.bashrc
ENV PATH="/root/.cargo/bin:${PATH}"

# Install ocaml
RUN apt-get update && apt-get install -y ocaml ocamlbuild

# Clone Halite repository
ARG GITHUB_TOKEN
RUN git clone https://${GITHUB_TOKEN}@github.com/CodeClash-ai/Halite-II.git /workspace \
    && cd /workspace \
    && git remote set-url origin https://github.com/CodeClash-ai/Halite-II.git \
    && unset GITHUB_TOKEN

WORKDIR /workspace

RUN cd environment && cmake . && make
