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

# Install Haskell
RUN apt-get update && apt-get install -y libgmp-dev \
 && rm -rf /var/lib/apt/lists/*

# Install GHCup non-interactively
RUN curl --proto '=https' --tlsv1.2 -sSf https://get-ghcup.haskell.org | \
    BOOTSTRAP_HASKELL_NONINTERACTIVE=1 BOOTSTRAP_HASKELL_ADJUST_BASHRC=1 sh

# Add ghcup to PATH
ENV PATH="/root/.ghcup/bin:${PATH}"

# Verify installation
RUN ghc --version && cabal --version

# Clone Halite repository
RUN git clone https://github.com/CodeClash-ai/Halite2.git /workspace \
    && cd /workspace \
    && git remote set-url origin https://github.com/CodeClash-ai/Halite2.git
WORKDIR /workspace

RUN cd environment && cmake . && make
