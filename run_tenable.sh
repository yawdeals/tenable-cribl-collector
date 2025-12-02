#!/bin/bash
# Tenable HEC Collector Runner
# Activates virtual environment and runs the collector

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Virtual environment path (change if different)
VENV_PATH="${SCRIPT_DIR}/venv"

# Check if venv exists
if [ ! -d "$VENV_PATH" ]; then
    echo "ERROR: Virtual environment not found at $VENV_PATH"
    echo "Create it with: python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

# Activate virtual environment
source "${VENV_PATH}/bin/activate"

# Create logs directory if needed
mkdir -p logs

# Run the collector
python3 tenable_collector.py "$@"

# Capture exit code
EXIT_CODE=$?

# Deactivate venv
deactivate 2>/dev/null

exit $EXIT_CODE
