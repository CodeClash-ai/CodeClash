#!/bin/bash

SYNC_COMMAND="aws s3 sync s3://codeclash/logs/ $HOME/CodeClash/logs/ --exclude \"*/rounds/*\" --exclude \"*.tar.gz\" --delete"
LOG_FILE="$HOME/sync.log"

while true; do
    echo "$(date): Starting sync..." >> "$LOG_FILE"
    eval $SYNC_COMMAND >> "$LOG_FILE" 2>&1
    echo "$(date): Sync completed" >> "$LOG_FILE"
    sleep 60
done
