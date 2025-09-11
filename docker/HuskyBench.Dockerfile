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
RUN git clone https://${GITHUB_TOKEN}@github.com/emagedoc/HuskyBench.git /testbed \
    && cd /testbed \
    && git remote set-url origin https://github.com/emagedoc/HuskyBench.git \
    && unset GITHUB_TOKEN

WORKDIR /testbed

RUN pip install -r engine/requirements.txt
RUN mkdir -p /testbed/engine/output
