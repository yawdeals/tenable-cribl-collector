# Tenable to Cribl HEC Integration

Collects security data from Tenable.io and sends it to Cribl via HTTP Event Collector (HEC).

## Features

- **10 Feed Types**: Assets, Vulnerabilities, Plugins, Compliance, and more
- **Feed Classification**: Each event includes `_tenable_feed` metadata for easy filtering
- **High Volume**: Batch processing (configurable, default 10,000 events per batch)
- **Event Limits**: Configurable max events per feed for large environments
- **Checkpointing**: Tracks processed IDs to avoid duplicates
- **Overlap Prevention**: Process lock prevents concurrent runs
- **Disk Protection**: Auto-cleanup of old checkpoint data
- **venv Support**: Works with virtual environments for restricted users

## Quick Start

### 1. Create Virtual Environment (Required for restricted users)

```bash
cd /path/to/tenable-hec-integration
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
deactivate
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
HEC_BATCH_SIZE=10000              # Events per HEC batch
MAX_EVENTS_PER_FEED=0             # 0=unlimited, or set limit (e.g., 50000)
CHECKPOINT_MAX_IDS=100000         # Max IDs per checkpoint file
CHECKPOINT_RETENTION_DAYS=30      # Days to keep checkpoint data
LOCK_TIMEOUT=600                  # Stale lock timeout (seconds)
```

### 3. Run the Collector

**Option A: Using wrapper script (recommended for venv)**
```bash
./run_tenable.sh --feed all
```

**Option B: Direct execution (if packages installed globally)**
```bash
python3 tenable_collector.py --feed all
```

## Command Line Options

```bash
# Collect all feeds
python3 tenable_collector.py --feed all

# Collect specific feeds
python3 tenable_collector.py --feed tenableio_asset tenableio_vulnerability

# Run in daemon mode (continuous)
python3 tenable_collector.py --feed all --daemon --interval 3600

# Available feed options:
#   all                              - All feeds
#   tenableio_asset                  - Asset inventory
#   tenableio_asset_self_scan        - Agent-based assets
#   tenableio_deleted_asset          - Deleted assets
#   tenableio_terminated_asset       - Terminated assets
#   tenableio_vulnerability          - Active vulnerabilities (medium, high, critical)
#   tenableio_vulnerability_no_info  - Informational vulnerabilities
#   tenableio_vulnerability_self_scan - Agent-based vulnerabilities
#   tenableio_fixed_vulnerability    - Fixed vulnerabilities
#   tenableio_plugin                 - Plugin metadata
#   tenableio_compliance             - Compliance findings
```

## Scheduling with Cron

### Recommended: Daily Run at 2 AM (Option 1 - Best for Large Environments)

```bash
crontab -e
```

Add:
```cron
0 2 * * * cd /path/to/tenable-hec-integration && ./run_tenable.sh --feed all >> logs/cron.log 2>&1
```

**Why daily?**
- First run: Backfills all historical data (may take hours)
- Subsequent runs: Only collects new/changed data via checkpoints (fast)
- The process lock prevents overlapping runs if one takes longer than 24 hours

### Alternative Schedules

```cron
# Every 6 hours
0 */6 * * * cd /path/to/tenable-hec-integration && ./run_tenable.sh --feed all >> logs/cron.log 2>&1

# Staggered feeds (for very large environments)
0 1 * * * cd /path/to/tenable-hec-integration && ./run_tenable.sh --feed tenableio_asset >> logs/cron.log 2>&1
0 3 * * * cd /path/to/tenable-hec-integration && ./run_tenable.sh --feed tenableio_vulnerability >> logs/cron.log 2>&1
0 5 * * 0 cd /path/to/tenable-hec-integration && ./run_tenable.sh --feed tenableio_plugin >> logs/cron.log 2>&1
```

## Event Classification

Every event sent to HEC includes a `_tenable_feed` field for easy filtering:

```json
{
  "_tenable_feed": {
    "feed_type": "vulnerability",
    "feed_name": "Active Vulnerabilities"
  },
  ... original Tenable event data ...
}
```

### Feed Types

| Feed Name | feed_type | feed_name | Sourcetype |
|-----------|-----------|-----------|------------|
| `tenableio_asset` | asset | Asset Inventory | tenable:io:asset |
| `tenableio_asset_self_scan` | asset_self_scan | Agent-Based Assets | tenable:io:asset:self_scan |
| `tenableio_deleted_asset` | deleted_asset | Deleted Assets | tenable:io:asset:deleted |
| `tenableio_terminated_asset` | terminated_asset | Terminated Assets | tenable:io:asset:terminated |
| `tenableio_vulnerability` | vulnerability | Active Vulnerabilities | tenable:io:vulnerability |
| `tenableio_vulnerability_no_info` | vulnerability_info | Informational Vulnerabilities | tenable:io:vulnerability:info |
| `tenableio_vulnerability_self_scan` | vulnerability_self_scan | Agent-Based Vulnerabilities | tenable:io:vulnerability:self_scan |
| `tenableio_fixed_vulnerability` | fixed_vulnerability | Fixed Vulnerabilities | tenable:io:vulnerability:fixed |
| `tenableio_plugin` | plugin | Plugin Metadata | tenable:io:plugin |
| `tenableio_compliance` | compliance | Compliance Findings | tenable:io:compliance |

## Sample Events (All 10 Feeds)

### 1. Asset Event (tenableio_asset)
```json
{
  "_tenable_feed": {
    "feed_type": "asset",
    "feed_name": "Asset Inventory"
  },
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "has_agent": true,
  "has_plugin_results": true,
  "created_at": "2025-01-15T10:30:00.000Z",
  "updated_at": "2025-12-01T08:15:00.000Z",
  "first_seen": "2025-01-15T10:30:00.000Z",
  "last_seen": "2025-12-01T08:15:00.000Z",
  "last_authenticated_scan_date": "2025-12-01T08:15:00.000Z",
  "fqdns": ["server01.example.com"],
  "hostnames": ["server01"],
  "ipv4s": ["192.168.1.100"],
  "ipv6s": [],
  "mac_addresses": ["00:1A:2B:3C:4D:5E"],
  "netbios_names": ["SERVER01"],
  "operating_systems": ["Microsoft Windows Server 2019 Standard"],
  "system_types": ["general-purpose"],
  "tags": [
    {"key": "Environment", "value": "Production"},
    {"key": "Owner", "value": "IT-Ops"}
  ],
  "network_id": "00000000-0000-0000-0000-000000000000",
  "agent_uuid": "b2c3d4e5-f6a7-8901-bcde-f23456789012",
  "sources": [
    {"name": "NESSUS_AGENT", "first_seen": "2025-01-15T10:30:00.000Z", "last_seen": "2025-12-01T08:15:00.000Z"}
  ]
}
```

### 2. Vulnerability Event (tenableio_vulnerability)
```json
{
  "_tenable_feed": {
    "feed_type": "vulnerability",
    "feed_name": "Active Vulnerabilities"
  },
  "asset": {
    "uuid": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "hostname": "server01.example.com",
    "ipv4": "192.168.1.100",
    "operating_system": "Microsoft Windows Server 2019 Standard",
    "fqdn": "server01.example.com",
    "device_type": "general-purpose"
  },
  "plugin": {
    "id": 156899,
    "name": "Microsoft Windows Security Update KB5001234",
    "family": "Windows : Microsoft Bulletins",
    "description": "The remote Windows host is missing a security update...",
    "solution": "Apply the KB5001234 security update.",
    "risk_factor": "High",
    "cvss_base_score": 8.8,
    "cvss3_base_score": 8.8,
    "cvss_vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:U/C:H/I:H/A:H",
    "see_also": ["https://support.microsoft.com/kb/5001234"]
  },
  "port": {
    "port": 0,
    "protocol": "tcp"
  },
  "scan": {
    "uuid": "c3d4e5f6-a7b8-9012-cdef-345678901234",
    "started_at": "2025-12-01T02:00:00.000Z",
    "completed_at": "2025-12-01T04:30:00.000Z"
  },
  "severity": "high",
  "severity_id": 3,
  "severity_default_id": 3,
  "severity_modification_type": "NONE",
  "first_found": "2025-11-15T10:00:00.000Z",
  "last_found": "2025-12-01T04:30:00.000Z",
  "state": "OPEN",
  "cve": ["CVE-2025-12345", "CVE-2025-12346"],
  "vpr": {
    "score": 7.4,
    "drivers": {
      "age_of_vuln": {"lower_bound": 30, "upper_bound": 60},
      "exploit_code_maturity": "PROOF_OF_CONCEPT",
      "threat_intensity_last_28": "LOW"
    }
  }
}
```

### 3. Plugin Event (tenableio_plugin)
```json
{
  "_tenable_feed": {
    "feed_type": "plugin",
    "feed_name": "Plugin Metadata"
  },
  "id": 156899,
  "name": "Microsoft Windows Security Update KB5001234",
  "family_name": "Windows : Microsoft Bulletins",
  "family_id": 10,
  "attributes": [
    {"attribute_name": "cpe", "attribute_value": "cpe:/o:microsoft:windows"},
    {"attribute_name": "cvss3_base_score", "attribute_value": "8.8"},
    {"attribute_name": "cvss3_vector", "attribute_value": "CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:U/C:H/I:H/A:H"},
    {"attribute_name": "exploitability_ease", "attribute_value": "Exploits are available"},
    {"attribute_name": "patch_publication_date", "attribute_value": "2025/11/10"},
    {"attribute_name": "plugin_modification_date", "attribute_value": "2025/11/15"},
    {"attribute_name": "plugin_publication_date", "attribute_value": "2025/11/12"},
    {"attribute_name": "risk_factor", "attribute_value": "High"},
    {"attribute_name": "solution", "attribute_value": "Apply the KB5001234 security update."},
    {"attribute_name": "synopsis", "attribute_value": "The remote Windows host is missing a security update."},
    {"attribute_name": "vuln_publication_date", "attribute_value": "2025/11/10"}
  ]
}
```

### 4. Compliance Event (tenableio_compliance)
```json
{
  "_tenable_feed": {
    "feed_type": "compliance",
    "feed_name": "Compliance Findings"
  },
  "scan_id": 12345,
  "scan_name": "CIS Windows Server 2019 Benchmark",
  "host_id": 67890,
  "hostname": "server01.example.com",
  "compliance_data": {
    "plugin_id": 21157,
    "plugin_name": "1.1.1 Ensure 'Enforce password history' is set to '24 or more password(s)'",
    "status": "FAILED",
    "severity": 2,
    "description": "This policy setting determines the number of renewed, unique passwords...",
    "solution": "Configure the 'Enforce password history' policy setting to 24 or more...",
    "see_also": "https://www.cisecurity.org/benchmark/windows_server",
    "reference": "CIS_MS_Windows_Server_2019_Benchmark_v1.3.0",
    "check_info": "Expected: 24, Actual: 12"
  }
}
```

### 5. Fixed Vulnerability Event (tenableio_fixed_vulnerability)
```json
{
  "_tenable_feed": {
    "feed_type": "fixed_vulnerability",
    "feed_name": "Fixed Vulnerabilities"
  },
  "asset_uuid": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "plugin_id": "156899",
  "port": "0",
  "protocol": "tcp",
  "status": "fixed",
  "fixed_at": "2025-12-01T19:58:36.000Z"
}
```

### 6. Deleted Asset Event (tenableio_deleted_asset)
```json
{
  "_tenable_feed": {
    "feed_type": "deleted_asset",
    "feed_name": "Deleted Assets"
  },
  "asset_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "deleted",
  "deleted_at": "2025-12-01T19:58:36.000Z"
}
```

### 7. Agent-Based Asset Event (tenableio_asset_self_scan)
```json
{
  "_tenable_feed": {
    "feed_type": "asset_self_scan",
    "feed_name": "Agent-Based Assets"
  },
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "has_agent": true,
  "agent_uuid": "b2c3d4e5-f6a7-8901-bcde-f23456789012",
  "agent_name": "server01-agent",
  "created_at": "2025-01-15T10:30:00.000Z",
  "updated_at": "2025-12-01T08:15:00.000Z",
  "first_seen": "2025-01-15T10:30:00.000Z",
  "last_seen": "2025-12-01T08:15:00.000Z",
  "last_authenticated_scan_date": "2025-12-01T08:15:00.000Z",
  "fqdns": ["server01.example.com"],
  "hostnames": ["server01"],
  "ipv4s": ["192.168.1.100"],
  "mac_addresses": ["00:1A:2B:3C:4D:5E"],
  "operating_systems": ["Microsoft Windows Server 2019 Standard"],
  "sources": [
    {"name": "NESSUS_AGENT", "first_seen": "2025-01-15T10:30:00.000Z", "last_seen": "2025-12-01T08:15:00.000Z"}
  ]
}
```

### 8. Terminated Asset Event (tenableio_terminated_asset)
```json
{
  "_tenable_feed": {
    "feed_type": "terminated_asset",
    "feed_name": "Terminated Assets"
  },
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "has_agent": true,
  "fqdns": ["old-server01.example.com"],
  "hostnames": ["old-server01"],
  "ipv4s": ["192.168.1.150"],
  "mac_addresses": ["00:1A:2B:3C:4D:99"],
  "operating_systems": ["Ubuntu 20.04 LTS"],
  "terminated_at": "2025-11-28T14:30:00.000Z",
  "terminated_by": "system",
  "first_seen": "2025-06-01T10:00:00.000Z",
  "last_seen": "2025-11-25T10:00:00.000Z"
}
```

### 9. Informational Vulnerability Event (tenableio_vulnerability_no_info)
```json
{
  "_tenable_feed": {
    "feed_type": "vulnerability_info",
    "feed_name": "Informational Vulnerabilities"
  },
  "asset": {
    "uuid": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "hostname": "server01.example.com",
    "ipv4": "192.168.1.100",
    "operating_system": "Microsoft Windows Server 2019 Standard",
    "fqdn": "server01.example.com"
  },
  "plugin": {
    "id": 19506,
    "name": "Nessus Scan Information",
    "family": "Settings",
    "description": "Information about the Nessus scan.",
    "risk_factor": "None"
  },
  "port": {
    "port": 0,
    "protocol": "tcp"
  },
  "severity": "info",
  "severity_id": 0,
  "state": "OPEN",
  "first_found": "2025-01-15T10:30:00.000Z",
  "last_found": "2025-12-01T04:30:00.000Z"
}
```

### 10. Agent-Based Vulnerability Event (tenableio_vulnerability_self_scan)
```json
{
  "_tenable_feed": {
    "feed_type": "vulnerability_self_scan",
    "feed_name": "Agent-Based Vulnerabilities"
  },
  "asset": {
    "uuid": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "hostname": "server01.example.com",
    "ipv4": "192.168.1.100",
    "operating_system": "Microsoft Windows Server 2019 Standard",
    "fqdn": "server01.example.com",
    "has_agent": true,
    "agent_uuid": "b2c3d4e5-f6a7-8901-bcde-f23456789012"
  },
  "plugin": {
    "id": 156899,
    "name": "Microsoft Windows Security Update KB5001234",
    "family": "Windows : Microsoft Bulletins",
    "description": "The remote Windows host is missing a security update...",
    "solution": "Apply the KB5001234 security update.",
    "risk_factor": "High",
    "cvss_base_score": 8.8,
    "cvss3_base_score": 8.8
  },
  "port": {
    "port": 0,
    "protocol": "tcp"
  },
  "severity": "high",
  "severity_id": 3,
  "state": "OPEN",
  "cve": ["CVE-2025-12345"],
  "first_found": "2025-11-15T10:00:00.000Z",
  "last_found": "2025-12-01T04:30:00.000Z"
}
```

## Filtering in Cribl/Splunk

```spl
# All vulnerability events
index=tenable sourcetype="tenable:io:vulnerability"

# Using _tenable_feed field
index=tenable | spath "_tenable_feed.feed_type" | search feed_type="vulnerability"

# High severity vulnerabilities
index=tenable sourcetype="tenable:io:vulnerability" severity="high" OR severity="critical"

# Specific asset
index=tenable | spath "asset.hostname" | search hostname="server01*"

# Fixed vulnerabilities in last 24 hours
index=tenable sourcetype="tenable:io:vulnerability:fixed" earliest=-24h
```

## File Structure

```
tenable-hec-integration/
├── run_tenable.sh          # Wrapper script (activates venv)
├── tenable_collector.py    # Main entry point
├── tenable_common.py       # HEC handler and logging setup
├── http_event_collector.py # HEC client
├── checkpoint_manager.py   # Checkpoint system
├── process_lock.py         # Overlap prevention
├── feeds/                  # Feed processors
│   ├── __init__.py         # Package init
│   ├── base.py             # Base class for all processors
│   ├── assets.py           # Asset feeds (4 types)
│   ├── vulnerabilities.py  # Vulnerability feeds (4 types)
│   └── plugins.py          # Plugin & Compliance feeds
├── venv/                   # Virtual environment (create this)
├── checkpoints/            # Checkpoint data (auto-created)
├── locks/                  # Lock files (auto-created)
├── logs/                   # Log files (auto-created)
├── .env                    # Configuration (create from .env.example)
├── .env.example            # Example configuration
└── requirements.txt        # Python dependencies
```

## How It Works

### 1. Initialization
- Loads configuration from `.env`
- Connects to Tenable.io API
- Initializes HEC handler for Cribl
- Loads checkpoint data from previous runs

### 2. Process Lock
- Creates lock file in `locks/` directory
- Prevents multiple instances from running simultaneously
- Auto-releases stale locks after `LOCK_TIMEOUT` seconds

### 3. Data Collection
For each enabled feed:
1. Query Tenable.io API for data (exports, plugins, etc.)
2. Check each item against checkpoint (skip already processed)
3. Add `_tenable_feed` classification metadata
4. Batch events (default: 10,000 per batch)
5. Send batch to Cribl HEC
6. Update checkpoint with processed IDs

### 4. Checkpointing
- Stores processed item IDs in `checkpoints/` directory
- Prevents duplicate event submission on subsequent runs
- Auto-purges data older than `CHECKPOINT_RETENTION_DAYS`
- First run collects all historical data; subsequent runs only collect new/changed items

### 5. Completion
- Logs summary of events collected per feed
- Releases process lock

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
| `HEC_BATCH_SIZE` | 5000 | Events per HEC batch |
| `MAX_EVENTS_PER_FEED` | 0 | Max events per feed (0=unlimited) |
| `CHECKPOINT_DIR` | checkpoints | Directory for checkpoint files |
| `CHECKPOINT_MAX_IDS` | 100000 | Max IDs per checkpoint file |
| `CHECKPOINT_RETENTION_DAYS` | 30 | Days to keep checkpoint data |
| `LOCK_DIR` | locks | Directory for lock files |
| `LOCK_TIMEOUT` | 600 | Seconds before lock considered stale |
| `LOG_LEVEL` | INFO | Logging level (DEBUG, INFO, WARNING, ERROR) |

## Logs

Logs are written to stdout and `logs/tenable_integration.log`:

```bash
# View live logs during manual run
python3 tenable_collector.py --feed all

# View log file
tail -f logs/tenable_integration.log

# View cron logs
tail -f logs/cron.log
```

## Troubleshooting

### "Another process is already running"

The process lock prevents overlapping runs. Wait for the current run to finish, or if it's stale (older than `LOCK_TIMEOUT`), it will auto-release.

To manually clear:
```bash
rm locks/tenable_collector.lock
```

### "Authentication error" / 401 Unauthorized

Verify your Tenable API keys in `.env`:
```bash
TENABLE_ACCESS_KEY=your_key
TENABLE_SECRET_KEY=your_secret
```

### HEC Connection Failed

1. Check Cribl HEC is enabled and listening
2. Verify `CRIBL_HEC_HOST`, `CRIBL_HEC_PORT`, `CRIBL_HEC_TOKEN`
3. Check firewall allows connection
4. If using SSL, ensure `CRIBL_HEC_SSL_VERIFY` is set correctly

### Script runs too long

For large environments with millions of assets/vulnerabilities:
1. Set `MAX_EVENTS_PER_FEED=50000` to limit events per run
2. Schedule more frequent runs to catch up incrementally
3. Use staggered feed collection (see cron examples above)

### No events collected after first run

This is expected! The checkpoint system tracks processed IDs, so subsequent runs only collect NEW or CHANGED data. Clear checkpoints to re-collect:
```bash
rm -rf checkpoints/*
```

## Requirements

- Python 3.6+
- Tenable.io API access (with appropriate permissions)
- Cribl HEC endpoint

## License

MIT
