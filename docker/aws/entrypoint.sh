#!/bin/bash
set -e

# Start Docker daemon (if needed)
dockerd &
#
# # Activate venv
source .venv/bin/activate
#
# # Create logs directory and sync from S3
mkdir -p logs
aws s3 sync s3://codeclash/logs/ logs/
#
# # Set ulimit
ulimit -n 65536
#
# # Execute the command passed to container
exec "$@"
