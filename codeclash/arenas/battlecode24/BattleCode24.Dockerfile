FROM eclipse-temurin:8-jdk

ENV JAVA_HOME=/opt/java/openjdk
RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl unzip && \
    rm -rf /var/lib/apt/lists/*

RUN git clone https://github.com/CodeClash-ai/BattleCode2024.git /workspace \
    && cd /workspace \
    && git remote set-url origin https://github.com/CodeClash-ai/BattleCode2024.git
WORKDIR /workspace

RUN chmod +x gradlew && ./gradlew update

