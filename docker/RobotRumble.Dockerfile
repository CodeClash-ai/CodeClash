FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

# Install Python 3.10 (and alias python→python3.10), pip, and prerequisites
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
    curl ca-certificates python3.10 python3.10-venv \
    python3-pip python-is-python3 wget git build-essential jq curl locales \
 && rm -rf /var/lib/apt/lists/*

RUN git clone https://github.com/emagedoc/RobotRumble.git /testbed

WORKDIR /testbed
