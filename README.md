# Tenable to Cribl HEC Collector

A production-ready Python 3.11 script that collects security data from Tenable.io and sends it to Cribl via HTTP Event Collector (HEC).

## Architecture Overview

```
+------------------+         +----------------------+         +------------------+
|                  |         |                      |         |                  |
|   Tenable.io     |  API    |  Tenable Collector   |   HEC   |   Cribl Stream   |
|   Cloud API      +-------->+  (Python 3.11)       +-------->+   / Splunk       |
|                  |         |                      |         |                  |
+------------------+         +----------+-----------+         +------------------+
                                        |
                                        v
                             +----------+-----------+
                             |     Checkpoints      |
                             |   (File-based)       |
                             +----------------------+
```

## Data Flow Diagram

```
                           START
                             |
                             v
                    +--------+--------+
                    | Load .env config |
                    | Initialize APIs  |
                    +--------+--------+
                             |
                             v
              +--------------+--------------+
              |     Smart Feed Grouping     |
              |   (3 parallel groups)       |
              +--------------+--------------+
                             |
         +-------------------+-------------------+
         |                   |                   |
         v                   v                   v
   +-----------+       +-----------+       +-----------+
   |  Assets   |       |   Vulns   |       |  Plugins  |
   |  Group    |       |   Group   |       |  Group    |
   +-----------+       +-----------+       +-----------+
         |                   |                   |
   (sequential)        (sequential)        (sequential)
         |                   |                   |
         v                   v                   v
   +-----+-----+       +-----+-----+       +-----+-----+
   | Export 1  |       | Export 1  |       | REST API  |
   | wait 60s  |       | wait 60s  |       | calls     |
   | Export 2  |       | Export 2  |       +-----+-----+
   | wait 60s  |       | wait 60s  |             |
   | Export 3  |       | Export 3  |             |
   | wait 60s  |       | wait 60s  |             |
   | Export 4  |       | Export 4  |             |
   +-----+-----+       +-----+-----+             |
         |                   |                   |
         +-------------------+-------------------+
                             |
                             v
                    +--------+--------+
                    | Flush checkpoints|
                    | Log summary      |
                    +--------+--------+
                             |
                             v
                            END
```

## Feed Processing Pipeline

```
For each feed:

  +------------------+
  | Start Feed       |
  +--------+---------+
           |
           v
  +--------+---------+
  | Check checkpoint |
  | Get last run     |
  +--------+---------+
           |
           v
  +--------+---------+
  | Call Tenable API |
  | (Export or REST) |
  +--------+---------+
           |
           v
  +--------+---------+
  | For each record: |
  +--------+---------+
           |
     +-----+-----+
     |           |
     v           v
  +--+--+     +--+--+
  | New |     | Dup |
  +--+--+     +--+--+
     |           |
     v           |
  +--+-------+   |
  | Add to   |   |
  | batch    |   |
  | buffer   |   |
  +--+-------+   |
     |           |
     v           |
  +--+-------+   |
  | Batch    |   |
  | full?    |   |
  +--+---+---+   |
     |   |       |
    Yes  No      |
     |   |       |
     v   +-------+
  +--+-------+
  | Send to  |
  | Cribl HEC|
  | (gzip)   |
  +--+-------+
     |
     v
  +--+-------+
  | Update   |
  | checkpoint|
  +--+-------+
     |
     v
  +--+-------+
  | Log      |
  | progress |
  +----------+
```

## HEC Batch Processing with Adaptive Rate Limiting

```
                    +------------------+
                    | Events buffered  |
                    | (batch_size=5000)|
                    +--------+---------+
                             |
                             v
                    +--------+---------+
                    | Compress with    |
                    | gzip (10x smaller)|
                    +--------+---------+
                             |
                             v
                    +--------+---------+
                    | POST to HEC      |
                    | endpoint         |
                    +--------+---------+
                             |
              +--------------+--------------+
              |              |              |
              v              v              v
         +----+----+    +----+----+    +----+----+
         | 200 OK  |    |   429   |    | Timeout |
         +---------+    | or 503  |    +---------+
              |              |              |
              v              v              v
         +----+----+    +----+----+    +----+----+
         | Speed up|    | Slow    |    | Slow    |
         | (0.9x)  |    | down 2x |    | down 2x |
         +---------+    +---------+    +---------+
              |              |              |
              +-------+------+------+------+
                      |
                      v
               +------+------+
               | Next batch  |
               +-------------+
```

## Checkpoint System

```
checkpoints/
    |
    +-- tenable_asset.json
    |       |
    |       +-- processed_ids: [id1, id2, id3, ...]
    |       +-- last_timestamp: 1733500000
    |
    +-- tenable_vulnerability.json
    |       |
    |       +-- processed_ids: [key1, key2, ...]
    |       +-- last_timestamp: 1733500000
    |
    +-- tenable_plugin.json
    |       |
    |       +-- processed_ids: [plugin1, plugin2, ...]
    |
    +-- ... (one file per feed)

Purpose:
  - Prevents duplicate events on subsequent runs
  - Enables incremental exports (only new data)
  - Auto-cleanup after CHECKPOINT_RETENTION_DAYS
```

## Quick Start

### 1. Install Requirements

```bash
cd /path/to/tenable-cribl-collector
pip3.11 install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your values:

```bash
# Required - Tenable.io API
TENABLE_ACCESS_KEY=your_access_key
TENABLE_SECRET_KEY=your_secret_key

# Required - Cribl HEC
CRIBL_HEC_HOST=cribl-server.company.com
CRIBL_HEC_PORT=8088
CRIBL_HEC_TOKEN=your_hec_token
```

### 3. Run the Collector

```bash
# Run all feeds
./run_tenable.sh --feed all

# Run specific feeds
./run_tenable.sh --feed tenableio_asset tenableio_vulnerability

# Run in daemon mode (continuous every 6 hours)
./run_tenable.sh --feed all --daemon --interval 21600
```

## Command Reference

```
Usage: ./run_tenable.sh [OPTIONS]

Options:
  --feed FEED [FEED ...]    Feeds to collect (required)
  --daemon                  Run continuously
  --interval SECONDS        Sleep between runs in daemon mode (default: 3600)
  --help                    Show help message

Feed Options:
  all                              All feeds
  tenableio_asset                  Asset inventory
  tenableio_asset_self_scan        Agent-based assets
  tenableio_deleted_asset          Deleted assets
  tenableio_terminated_asset       Terminated assets
  tenableio_vulnerability          Vulnerabilities (medium, high, critical)
  tenableio_vulnerability_no_info  Informational vulnerabilities
  tenableio_vulnerability_self_scan Agent-based vulnerabilities
  tenableio_fixed_vulnerability    Fixed vulnerabilities
  tenableio_plugin                 Plugin metadata
  tenableio_compliance             Compliance findings
```

## Examples

### Collect All Data (First Run)

```bash
./run_tenable.sh --feed all
```

Output:
```
Using Python 3.11
[2025-12-06 14:00:00] Starting Tenable collector...
================================================================================
STARTING TENABLE TO CRIBL INTEGRATION
================================================================================
Selected feeds: all
Batch size: 5000 events
Execution mode: SMART GROUPING (parallel groups, sequential within)
================================================================================
[assets] Processing feed 1/4: tenableio_asset
  [Asset Inventory] 10,000 events (500/sec)
  [Asset Inventory] 20,000 events (520/sec)
  Completed Asset Inventory: 25,432 events processed, 25,432 sent to HEC in 0.8min
[assets] Waiting 60s for Tenable export lock to release...
...
================================================================================
COLLECTION COMPLETE
================================================================================
Total events: 142,567
Total time: 12.5 minutes
HEC throughput: 190 events/sec
================================================================================
[2025-12-06 14:12:30] Collector finished with exit code 0
```

### Collect Specific Feeds

```bash
# Only assets
./run_tenable.sh --feed tenableio_asset

# Assets and vulnerabilities
./run_tenable.sh --feed tenableio_asset tenableio_vulnerability
```

### Daemon Mode (Background)

```bash
# Run every 6 hours in background
nohup ./run_tenable.sh --feed all --daemon --interval 21600 > logs/daemon.log 2>&1 &

# Check if running
ps aux | grep tenable_collector

# Stop daemon
pkill -f tenable_collector
```

### Schedule with Cron

```bash
# Edit crontab
crontab -e

# Add: Run daily at 2 AM
0 2 * * * cd /path/to/tenable-cribl-collector && ./run_tenable.sh --feed all >> logs/cron.log 2>&1

# Add: Run every 6 hours
0 */6 * * * cd /path/to/tenable-cribl-collector && ./run_tenable.sh --feed all >> logs/cron.log 2>&1
```

## Configuration Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `TENABLE_ACCESS_KEY` | (required) | Tenable.io API access key |
| `TENABLE_SECRET_KEY` | (required) | Tenable.io API secret key |
| `TENABLE_URL` | https://cloud.tenable.com | Tenable.io API URL |
| `CRIBL_HEC_HOST` | (required) | Cribl HEC hostname/IP |
| `CRIBL_HEC_PORT` | 8088 | Cribl HEC port |
| `CRIBL_HEC_TOKEN` | (required) | Cribl HEC authentication token |
| `CRIBL_HEC_SSL_VERIFY` | true | Verify SSL certificates |
| `CRIBL_HEC_CA_CERT` | (none) | Path to CA certificate file |
| `HEC_BATCH_SIZE` | 5000 | Events per HEC batch |
| `HEC_BATCH_DELAY` | 0.01 | Seconds between batches (adaptive) |
| `HEC_POOL_CONNECTIONS` | 10 | HTTP connection pool size |
| `MAX_EVENTS_PER_FEED` | 0 | Max events per feed (0=unlimited) |
| `MAX_CONCURRENT_FEEDS` | 1 | Concurrent feed workers |
| `SMART_FEED_GROUPING` | true | Enable parallel group execution |
| `FULLY_SEQUENTIAL` | false | Run all feeds one at a time |
| `INTER_FEED_DELAY` | 60 | Seconds between feeds in same group |
| `CHECKPOINT_DIR` | checkpoints | Directory for checkpoint files |
| `CHECKPOINT_MAX_IDS` | 500000 | Max IDs per checkpoint file |
| `CHECKPOINT_RETENTION_DAYS` | 7 | Days to keep checkpoint data |
| `DELETED_ASSET_SCAN_INTERVAL_HOURS` | 24 | Hours between deleted asset scans |
| `LOG_LEVEL` | INFO | Logging level |

## Feed Groups and Execution

The script uses smart grouping to maximize throughput while avoiding Tenable API rate limits:

```
Group 1: Assets (sequential, 60s delay between)
  - tenableio_asset
  - tenableio_asset_self_scan
  - tenableio_deleted_asset
  - tenableio_terminated_asset

Group 2: Vulnerabilities (sequential, 60s delay between)
  - tenableio_vulnerability
  - tenableio_vulnerability_no_info
  - tenableio_vulnerability_self_scan
  - tenableio_fixed_vulnerability

Group 3: Plugins (sequential)
  - tenableio_plugin
  - tenableio_compliance

All 3 groups run IN PARALLEL.
Feeds within each group run SEQUENTIALLY with 60-second delays.
```

## Tenable API Rate Limits and Compliance

The script is designed to fully comply with Tenable.io API rate limits:

```
Tenable.io Export API Rules:
+------------------------------------------------------------------+
|                                                                  |
|  Asset Exports:    Only 1 active export at a time                |
|  Vuln Exports:     Only 1 active export at a time                |
|  Compliance:       Only 1 active export at a time                |
|                                                                  |
|  HOWEVER: Different export TYPES can run in parallel             |
|           (1 asset export + 1 vuln export + REST API = OK)       |
|                                                                  |
|  If you start a 2nd export of the SAME TYPE:                     |
|  --> HTTP 429 "Too Many Requests"                                |
|  --> "Duplicate export cannot run"                               |
|                                                                  |
+------------------------------------------------------------------+
```

### How the Script Complies

```
ALLOWED (Different types in parallel):
+------------------+     +------------------+     +------------------+
|  Asset Export    |     |  Vuln Export     |     |  REST API Call   |
|  (type: assets)  |     |  (type: vulns)   |     |  (plugins/scans) |
+------------------+     +------------------+     +------------------+
        |                        |                        |
        +-------------- RUN TOGETHER (3 streams) ---------+
                                OK


NOT ALLOWED (Same type in parallel):
+------------------+     +------------------+
|  Asset Export 1  |     |  Asset Export 2  |
|  (type: assets)  |     |  (type: assets)  |
+------------------+     +------------------+
        |                        |
        +---- RUN TOGETHER ------+
               429 ERROR
```

### Compliance Verification

```
Tenable Rule                          Script Behavior                    Compliant?
------------------------------------- ---------------------------------- ----------
Asset Exports: 1 at a time            Group 1 runs sequentially          YES
                                      (60s wait between each)

Vuln Exports: 1 at a time             Group 2 runs sequentially          YES
                                      (60s wait between each)

REST API calls                        Group 3 runs sequentially          YES
                                      (no export lock conflicts)

Different types can run together      Groups 1, 2, 3 run in parallel     YES
                                      (max 3 concurrent streams)
```

The 60-second delay between feeds in the same group provides safety margin to ensure Tenable fully releases the export lock on their backend before the next export starts.

## Event Format

Every event includes classification metadata:

```json
{
  "_tenable_feed": {
    "feed_type": "vulnerability",
    "feed_name": "Active Vulnerabilities"
  },
  "asset": {
    "uuid": "abc-123",
    "hostname": "server01.example.com"
  },
  "plugin": {
    "id": 12345,
    "name": "SSL Certificate Expired"
  },
  "severity_id": 4,
  "severity": "critical"
}
```

## Sourcetypes

| Feed | Sourcetype |
|------|------------|
| Asset Inventory | tenable:io:asset |
| Agent-Based Assets | tenable:io:asset:self_scan |
| Deleted Assets | tenable:io:asset:deleted |
| Terminated Assets | tenable:io:asset:terminated |
| Active Vulnerabilities | tenable:io:vulnerability |
| Informational Vulnerabilities | tenable:io:vulnerability:info |
| Agent-Based Vulnerabilities | tenable:io:vulnerability:self_scan |
| Fixed Vulnerabilities | tenable:io:vulnerability:fixed |
| Plugin Metadata | tenable:io:plugin |
| Compliance Findings | tenable:io:compliance |

## File Structure

```
tenable-cribl-collector/
|-- run_tenable.sh           # Main runner script (uses Python 3.11)
|-- tenable_collector.py     # Orchestrator
|-- tenable_common.py        # HEC handler, logging
|-- http_event_collector.py  # HEC client with retry/gzip
|-- checkpoint_manager.py    # File-based checkpointing
|-- feeds/
|   |-- __init__.py
|   |-- base.py              # Base processor class
|   |-- assets.py            # 4 asset feed processors
|   |-- vulnerabilities.py   # 4 vulnerability feed processors
|   |-- plugins.py           # Plugin and compliance processors
|-- checkpoints/             # Checkpoint data (auto-created)
|-- logs/                    # Log files (auto-created)
|-- .env                     # Configuration (create from .env.example)
|-- .env.example             # Example configuration
|-- requirements.txt         # Python dependencies
```

## Logs

```bash
# Main log (all activity)
tail -f logs/tenable_integration.log

# Per-feed logs
tail -f logs/asset.log
tail -f logs/vulnerability.log
tail -f logs/plugin.log

# All logs at once
tail -f logs/*.log
```

## Troubleshooting

### Error 429 / Rate Limit

The script automatically retries with exponential backoff:
- Retry 1: Wait 120 seconds
- Retry 2: Wait 180 seconds
- Retry 3: Wait 270 seconds
- Retry 4: Wait 405 seconds
- Retry 5: Wait 607 seconds

If retries fail, wait 30 minutes and try again.

### No Events After First Run

This is expected. The checkpoint system prevents duplicates. Only new or changed data is collected on subsequent runs. To re-collect all data:

```bash
rm -rf checkpoints/*
./run_tenable.sh --feed all
```

### HEC Connection Failed

1. Verify Cribl HEC is enabled and listening
2. Check firewall allows connection to port 8088
3. Verify token is correct
4. Check SSL settings match your Cribl configuration

### Script Runs Too Long

For very large environments:
1. Set `MAX_EVENTS_PER_FEED=100000` to limit events per run
2. Use staggered cron schedules for different feeds
3. Increase `HEC_BATCH_SIZE` to 10000 for faster throughput

## Requirements

- Python 3.11+
- pytenable >= 1.9.0
- requests >= 2.31.0
- python-dotenv >= 1.0.0
- orjson >= 3.9.0 (optional, 10x faster JSON)

## License

MIT
