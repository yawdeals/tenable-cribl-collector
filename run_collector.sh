#!/bin/bash
# Simple wrapper to run Tenable collection
# Production-ready - No dependencies required

# Set script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Load environment if .env exists
if [ -f ".env" ]; then
    set -a
    source .env
    set +a
fi

# Run the collector
python3 tenable_collector.py --once "$@"
