FROM ubuntu:22.04

RUN apt-get update \
    && apt-get install -y \
       curl ca-certificates wget git build-essential jq curl locales \
    && rm -rf /var/lib/apt/lists/*

RUN git clone https://github.com/emagedoc/CoreWar.git /testbed

WORKDIR /testbed

RUN cd src/ && make CFLAGS="-O -DEXT94 -DPERMUTATE -DRWLIMIT" LIB=""
