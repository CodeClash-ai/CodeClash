FROM ubuntu:22.04

RUN apt-get update \
    && apt-get install -y \
       curl ca-certificates wget git build-essential jq curl locales \
    && rm -rf /var/lib/apt/lists/*

RUN git clone https://github.com/CodeClash-ai/CoreWar.git /workspace \
    && cd /workspace \
    && git remote set-url origin https://github.com/CodeClash-ai/CoreWar.git
WORKDIR /workspace

RUN cd src/ && make CFLAGS="-O -DEXT94 -DPERMUTATE -DRWLIMIT" LIB=""

# Copy dwarf example to home directory for validation purposes
RUN cp /workspace/doc/examples/dwarf.red /home/dwarf.red
