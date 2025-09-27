FROM ubuntu:22.04

RUN apt-get update \
    && apt-get install -y \
       curl ca-certificates wget git build-essential jq curl locales \
    && rm -rf /var/lib/apt/lists/*

ARG GITHUB_TOKEN
RUN git clone https://${GITHUB_TOKEN}@github.com/emagedoc/CoreWar.git /workspace \
    && cd /workspace \
    && git remote set-url origin https://github.com/emagedoc/CoreWar.git \
    && unset GITHUB_TOKEN

WORKDIR /workspace

RUN cd src/ && make CFLAGS="-O -DEXT94 -DPERMUTATE -DRWLIMIT" LIB=""
