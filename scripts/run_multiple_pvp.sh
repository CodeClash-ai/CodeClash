#!/bin/bash

# Check if argument is provided
if [ $# -eq 0 ]; then
    echo "Usage: $0 <config_file>"
    echo "Example: $0 configs/main/RobotRumble__gemini-2.5-pro__gpt-5-mini__r15__s1000.yaml"
    exit 1
fi

CONFIG_FILE="$1"

# optional second arg: number of times to run (default 10)
COUNT=${2:-10}
for ((i=1; i<=COUNT; i++)); do
    python main.py "$CONFIG_FILE"
done

# Replace RoboCode with CoreWar in config file path
COREWAR_CONFIG_FILE="${CONFIG_FILE//RoboCode/CoreWar}"

for ((i=1; i<=COUNT; i++)); do
    python main.py "$COREWAR_CONFIG_FILE"
done
