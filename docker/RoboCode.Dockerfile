FROM maven:3.9-eclipse-temurin-24

ARG DEBIAN_FRONTEND=noninteractive
ENV TZ=Etc/UTC

RUN apt update && apt install -y \
wget \
git \
build-essential \
ant \
unzip \
&& rm -rf /var/lib/apt/lists/*

ARG GITHUB_TOKEN
RUN git clone https://${GITHUB_TOKEN}@github.com/emagedoc/RoboCode.git /testbed \
    && cd /testbed \
    && git remote set-url origin https://github.com/emagedoc/RoboCode.git \
    && unset GITHUB_TOKEN

WORKDIR /testbed
