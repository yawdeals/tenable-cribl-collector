#!/bin/bash
# Run all Tenable to Cribl HEC integration scripts
# Usage: ./run_all.sh [--once] [--interval SECONDS]

echo "=== Tenable to Cribl HEC Integration - Running All Scripts ==="
echo ""

# Parse arguments
ONCE_FLAG=""
INTERVAL_FLAG=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --once)
            ONCE_FLAG="--once"
            shift
            ;;
        --interval)
            INTERVAL_FLAG="--interval $2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--once] [--interval SECONDS]"
            exit 1
            ;;
    esac
done

# Check if running in once mode or continuous mode
if [ -n "$ONCE_FLAG" ]; then
    echo "Running in ONE-TIME mode..."
    echo ""
    
    echo "1. Processing Scans..."
    python3 tenable_scans.py --once
    echo ""
    
    echo "2. Processing Vulnerabilities..."
    python3 tenable_vulnerabilities.py --once
    echo ""
    
    echo "3. Processing Assets..."
    python3 tenable_assets.py --once
    echo ""
    
    echo "=== All scripts completed ==="
else
    echo "Running in CONTINUOUS mode..."
    echo "Starting all scripts in background..."
    echo ""
    
    # Ensure logs directory exists
    mkdir -p logs
    
    # Start scans script
    echo "Starting tenable_scans.py..."
    nohup python3 tenable_scans.py $INTERVAL_FLAG > logs/tenable_scans_bg.log 2>&1 &
    SCANS_PID=$!
    echo "  PID: $SCANS_PID"
    
    # Start vulnerabilities script
    echo "Starting tenable_vulnerabilities.py..."
    nohup python3 tenable_vulnerabilities.py $INTERVAL_FLAG > logs/tenable_vulnerabilities_bg.log 2>&1 &
    VULNS_PID=$!
    echo "  PID: $VULNS_PID"
    
    # Start assets script
    echo "Starting tenable_assets.py..."
    nohup python3 tenable_assets.py $INTERVAL_FLAG > logs/tenable_assets_bg.log 2>&1 &
    ASSETS_PID=$!
    echo "  PID: $ASSETS_PID"
    
    echo ""
    echo "=== All scripts started in background ==="
    echo ""
    echo "Process IDs:"
    echo "  Scans:           $SCANS_PID"
    echo "  Vulnerabilities: $VULNS_PID"
    echo "  Assets:          $ASSETS_PID"
    echo ""
    echo "Log files:"
    echo "  Scans:           logs/tenable_scans_bg.log"
    echo "  Vulnerabilities: logs/tenable_vulnerabilities_bg.log"
    echo "  Assets:          logs/tenable_assets_bg.log"
    echo ""
    echo "To stop all scripts:"
    echo "  kill $SCANS_PID $VULNS_PID $ASSETS_PID"
    echo ""
    echo "To view logs in real-time:"
    echo "  tail -f logs/tenable_scans_bg.log"
    echo "  tail -f logs/tenable_vulnerabilities_bg.log"
    echo "  tail -f logs/tenable_assets_bg.log"
fi
