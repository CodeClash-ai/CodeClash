FROM python:3.10-slim

ARG DEBIAN_FRONTEND=noninteractive
ENV TZ=Etc/UTC

RUN apt update && apt install -y \
wget \
git \
build-essential \
unzip \
lsof \
&& rm -rf /var/lib/apt/lists/*

ARG GITHUB_TOKEN
RUN git clone https://${GITHUB_TOKEN}@github.com/CodeClash-ai/HuskyBench.git /workspace \
    && cd /workspace \
    && git remote set-url origin https://github.com/CodeClash-ai/HuskyBench.git \
    && unset GITHUB_TOKEN

WORKDIR /workspace

RUN pip install -r engine/requirements.txt
RUN mkdir -p /workspace/engine/output
