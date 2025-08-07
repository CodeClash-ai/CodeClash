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

RUN git clone https://github.com/emagedoc/RoboCode.git testbed

WORKDIR /testbed