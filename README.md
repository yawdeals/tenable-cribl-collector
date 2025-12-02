# Tenable to Cribl HEC Integration

Collects security data from Tenable.io and sends it to Cribl via HTTP Event Collector (HEC).

## Features

- **10 Feed Types**: Assets, Vulnerabilities, Plugins, Compliance, and more
- **High Volume**: Batch processing (10,000 events per batch)
- **Checkpointing**: Tracks processed IDs to avoid duplicates
- **Overlap Prevention**: Process lock prevents concurrent runs
- **Disk Protection**: Auto-cleanup of old checkpoint data

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

Copy the example and edit with your values:

```bash
cp .env.example .env
```

Edit `.env`:

```bash
# Tenable.io API (Required)
TENABLE_ACCESS_KEY=your_access_key_here
TENABLE_SECRET_KEY=your_secret_key_here

# Cribl HEC (Required)
CRIBL_HEC_HOST=192.168.14.45
CRIBL_HEC_PORT=8088
CRIBL_HEC_TOKEN=your_hec_token_here

# Optional Settings
HEC_BATCH_SIZE=10000           # Events per HEC batch
CHECKPOINT_MAX_IDS=100000      # Max IDs per checkpoint file
CHECKPOINT_RETENTION_DAYS=30   # Days to keep checkpoint data
LOCK_TIMEOUT=600               # Stale lock timeout (seconds)
```

### 3. Run the Collector

```bash
python3 tenable_collector.py
```

## Scheduling with Cron

### Run Every 10 Minutes

```bash
crontab -e
```

Add this line:

```cron
*/10 * * * * cd /path/to/tenable-hec-integration && /usr/bin/python3 tenable_collector.py >> logs/collector.log 2>&1
```

### Run Every Hour

```cron
0 * * * * cd /path/to/tenable-hec-integration && /usr/bin/python3 tenable_collector.py >> logs/collector.log 2>&1
```

### Run Daily at 2 AM

```cron
0 2 * * * cd /path/to/tenable-hec-integration && /usr/bin/python3 tenable_collector.py >> logs/collector.log 2>&1
```

## File Structure

```
tenable-hec-integration/
├── tenable_collector.py    # Main entry point
├── tenable_common.py       # HEC handler
├── http_event_collector.py # HEC client
├── checkpoint_manager.py   # Checkpoint system
├── process_lock.py         # Overlap prevention
├── feeds/                  # Feed processors
│   ├── base.py             # Base class
│   ├── assets.py           # Asset feeds (4 types)
│   ├── vulnerabilities.py  # Vulnerability feeds (4 types)
│   └── plugins.py          # Plugin & Compliance feeds
├── checkpoints/            # Checkpoint data (auto-created)
├── locks/                  # Lock files (auto-created)
├── logs/                   # Log files (auto-created)
├── .env                    # Configuration
└── requirements.txt        # Python dependencies
```

## Feed Types

| Feed | Source | Description |
|------|--------|-------------|
| `asset` | exports.assets() | All assets |
| `asset_self_scan` | exports.assets() | Self-scan assets |
| `deleted_asset` | exports.assets() | Deleted assets |
| `terminated_asset` | exports.assets() | Terminated assets |
| `vuln` | exports.vulns() | All vulnerabilities |
| `vuln_no_info` | exports.vulns() | Vulnerabilities (no info severity) |
| `vuln_self_scan` | exports.vulns() | Self-scan vulnerabilities |
| `fixed_vuln` | exports.vulns() | Fixed vulnerabilities |
| `plugin` | plugins.families() | Plugin definitions |
| `compliance` | scans.list() | Compliance scan results |

## Logs

Logs are written to stdout and can be redirected:

```bash
# View live logs
python3 tenable_collector.py

# Save to file
python3 tenable_collector.py >> logs/collector.log 2>&1

# View recent logs
tail -f logs/collector.log
```

## Troubleshooting

### "Another process is already running"

The process lock prevents overlapping runs. Wait for the current run to finish, or if it's stale (>10 min), it will auto-release.

To manually clear:
```bash
rm locks/tenable_collector.lock
```

### "Authentication error"

Verify your Tenable API keys in `.env`:
```bash
TENABLE_ACCESS_KEY=your_key
TENABLE_SECRET_KEY=your_secret
```

### HEC Connection Failed

1. Check Cribl HEC is enabled and listening
2. Verify `CRIBL_HEC_HOST`, `CRIBL_HEC_PORT`, `CRIBL_HEC_TOKEN`
3. Check firewall allows connection

## Requirements

- Python 3.6+
- Tenable.io API access
- Cribl HEC endpoint
