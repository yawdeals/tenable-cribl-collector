#!/bin/bash
# Cron Wrapper Script for Tenable to Cribl HEC Integration
# This script is designed to be run from cron
# It ensures proper environment setup and logging

# Set script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Load environment variables from .env file
if [ -f "$SCRIPT_DIR/.env" ]; then
    set -a
    source "$SCRIPT_DIR/.env"
    set +a
fi

# Setup log directory
LOG_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOG_DIR"

# Timestamp for logging
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

# Determine which script to run
SCRIPT_NAME="${1:-tenable_scans.py}"

# Log file for this run
CRON_LOG="$LOG_DIR/cron_$(basename $SCRIPT_NAME .py)_$(date '+%Y%m%d').log"

# Function to log messages
log() {
    echo "[$TIMESTAMP] $1" >> "$CRON_LOG"
}

# Start logging
log "========================================="
log "Starting $SCRIPT_NAME via cron"
log "========================================="

# Verify Python is available
if ! command -v python3 &> /dev/null; then
    log "ERROR: python3 not found in PATH"
    log "PATH: $PATH"
    exit 1
fi

# Verify script exists
if [ ! -f "$SCRIPT_DIR/$SCRIPT_NAME" ]; then
    log "ERROR: Script not found: $SCRIPT_DIR/$SCRIPT_NAME"
    exit 1
fi

# Verify .env exists
if [ ! -f "$SCRIPT_DIR/.env" ]; then
    log "WARNING: .env file not found. Using environment variables."
fi

# Run the Python script with --once flag
log "Executing: python3 $SCRIPT_DIR/$SCRIPT_NAME --once"
python3 "$SCRIPT_DIR/$SCRIPT_NAME" --once >> "$CRON_LOG" 2>&1
EXIT_CODE=$?

# Log completion
if [ $EXIT_CODE -eq 0 ]; then
    log "SUCCESS: $SCRIPT_NAME completed successfully"
else
    log "ERROR: $SCRIPT_NAME failed with exit code $EXIT_CODE"
fi

log "========================================="
log "Completed $SCRIPT_NAME"
log "========================================="

exit $EXIT_CODE
