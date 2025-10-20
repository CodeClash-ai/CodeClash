#!/bin/bash

# Check if argument is provided
if [ $# -eq 0 ]; then
    echo "Usage: $0 <config_file>"
    echo "Example: $0 configs/main/RobotRumble__gemini-2.5-pro__gpt-5-mini__r15__s1000.yaml"
    exit 1
fi

CONFIG_FILE="$1"

for i in {1..2}; do
    AWS_PROFILE=swerl aws/run_job.py -y -- aws/docker_and_sync.sh python main.py "$CONFIG_FILE"
done
