FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

# Install Python 3.10 (and alias python→python3.10), pip, and prerequisites
# Also install C++ compiler and make for building Kojiro
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
    curl ca-certificates python3.10 python3.10-venv \
    python3-pip python-is-python3 wget git build-essential \
    g++ make jq curl locales \
 && rm -rf /var/lib/apt/lists/*

# Clone Kojiro repository
RUN git clone https://github.com/Babak-SSH/Kojiro.git /workspace \
    && cd /workspace \
    && git remote set-url origin https://github.com/Babak-SSH/Kojiro.git

# Clone and build Fastchess
RUN git clone https://github.com/Disservin/fastchess.git /tmp/fastchess \
    && cd /tmp/fastchess \
    && make -j \
    && install -d /usr/local/bin \
    && install fastchess /usr/local/bin/fastchess \
    && rm -rf /tmp/fastchess

WORKDIR /workspace

