#!/usr/bin/env bash

# Avoid consuming lots of storage by chatty docker logs

set -euo pipefail

# Configure Docker log rotation
cat <<EOF > /etc/docker/daemon.json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
EOF

# Restart Docker to apply changes
systemctl restart docker
