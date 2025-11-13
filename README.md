# Tenable to Cribl HEC Integration

Production-ready Python script that collects data from Tenable.io and sends it to Cribl via HTTP Event Collector (HEC). Features file-based checkpointing with no external dependencies required.

## Features

- **Unified Collection Script**: Single `tenable_collector.py` handles all Tenable data types
- **No Redis Required**: File-based JSON checkpointing - works in restricted environments
- **Python 3.6.8+ Compatible**: Works on older production systems
- **Multiple Data Types**: Collect assets, vulnerabilities, plugins, and scans
- **Flexible Execution**: Run once or continuously with configurable intervals
- **Production Hardened**: Clean logging, error handling, and checkpoint management

## Prerequisites

- Python 3.6.8 or higher
- Tenable.io account with API access keys
- Cribl instance with HTTP Event Collector enabled
- **No root/sudo access required**
- **No Redis or external database needed**

## Quick Start

1. **Install dependencies** (user-level, no root needed):
   ```bash
   pip install --user -r requirements.txt
   ```

2. **Configure environment**:
   ```bash
   cp .env.example .env
   # Edit .env and add your credentials
   ```

3. **Run data collection**:
   ```bash
   # Collect all data types once
   ./run_collector.sh --types all

   # Collect specific data types
   ./run_collector.sh --types assets,vulnerabilities

   # Run continuously (default 1 hour interval)
   python tenable_collector.py --types all
   ```

## Installation

### Step 1: Install Python Dependencies

No root access required - install to user directory:

```bash
pip install --user -r requirements.txt
```

Dependencies:
- `pytenable==1.3.4` - Tenable.io API client (Python 3.6.8 compatible)
- `python-dotenv==0.19.2` - Environment variable management
- `requests==2.27.1` - HTTP library

### Step 2: Configure Environment Variables

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```bash
# Tenable API Configuration
TENABLE_ACCESS_KEY=your_access_key_here
TENABLE_SECRET_KEY=your_secret_key_here
TENABLE_URL=https://cloud.tenable.com

# Cribl HEC Configuration
CRIBL_HEC_HOST=192.168.14.45
CRIBL_HEC_PORT=8088
CRIBL_HEC_TOKEN=your_hec_token_here
CRIBL_HEC_SSL_VERIFY=false

# Checkpoint Configuration
CHECKPOINT_DIR=checkpoints

# Script Configuration
LOG_LEVEL=INFO
SCAN_INTERVAL=3600
```

**Get Tenable API Keys**:
1. Log in to Tenable.io
2. Go to Settings → My Account → API Keys
3. Generate new access and secret keys

**Get Cribl HEC Token**:
1. Configure HTTP Event Collector source in Cribl
2. Generate HEC token
3. Note the endpoint host and port

## Usage

### Run Once (Recommended for Cron Jobs)

Collect all data types:
```bash
./run_collector.sh --types all
```

Collect specific data types:
```bash
./run_collector.sh --types assets,vulnerabilities,plugins
```

Direct Python execution:
```bash
python tenable_collector.py --once --types all
```

### Run Continuously

Default interval (1 hour):
```bash
python tenable_collector.py --types all
```

Custom interval (30 minutes):
```bash
python tenable_collector.py --types all --interval 1800
```

### Available Data Types

| Type | Description |
|------|-------------|
| `assets` | Asset inventory from Tenable |
| `vulnerabilities` | High/Critical/Medium severity vulnerabilities |
| `vulnerabilities_no_info` | Info severity vulnerabilities only |
| `plugins` | Vulnerability plugin information |
| `scans` | Scan summary data |
| `all` | All of the above |

**Examples**:
```bash
# Collect only assets and high-severity vulnerabilities
python tenable_collector.py --once --types assets,vulnerabilities

# Collect everything except info-level findings
python tenable_collector.py --once --types assets,vulnerabilities,plugins,scans

# Collect only scan summaries
python tenable_collector.py --once --types scans
```

## Scheduling with Cron

Add to crontab (`crontab -e`):

```bash
# Run all data types every hour
0 * * * * cd /path/to/tenable-hec-integration && ./run_collector.sh --types all >> logs/cron.log 2>&1

# Run assets and vulnerabilities every 4 hours
0 */4 * * * cd /path/to/tenable-hec-integration && ./run_collector.sh --types assets,vulnerabilities >> logs/cron.log 2>&1

# Run daily at 3 AM
0 3 * * * cd /path/to/tenable-hec-integration && ./run_collector.sh --types all >> logs/cron.log 2>&1
```

**Important**: Always use absolute paths in cron and redirect output to logs.

## Checkpointing

Checkpoints are stored as JSON files in the `checkpoints/` directory:

```
checkpoints/
├── tenable_assets.json
├── tenable_vulnerabilities.json
├── tenable_plugins.json
└── tenable_scans.json
```

Each checkpoint file tracks:
- **last_timestamp**: Last processed modification time
- **processed_ids**: Set of already-processed item IDs

### Reset Checkpoints

To reprocess all data:
```bash
rm -rf checkpoints/
```

To reset specific data type:
```bash
rm checkpoints/tenable_assets.json
```

## Logging

Logs are written to `logs/` directory:
- **tenable_integration.log**: Main application log
- **cron.log**: Cron execution log (if using cron)

Log level configured via `LOG_LEVEL` in `.env`:
- `DEBUG`: Verbose debugging information
- `INFO`: General informational messages (default)
- `WARNING`: Warning messages
- `ERROR`: Error messages
- `CRITICAL`: Critical errors

View recent logs:
```bash
tail -f logs/tenable_integration.log
```

## Troubleshooting

### Test Tenable Connection

```bash
python test_tenable_access.py
```

### Test Cribl HEC Endpoint

```bash
curl -k http://192.168.14.45:8088/services/collector/event \
  -H "Authorization: Splunk YOUR_HEC_TOKEN" \
  -d '{"event": "test", "sourcetype": "manual"}'
```

### Common Issues

**Import Errors**:
```bash
# Reinstall dependencies
pip install --user -r requirements.txt
```

**Permission Denied on run_collector.sh**:
```bash
chmod +x run_collector.sh
```

**No Data Collected**:
- Check `.env` credentials are correct
- Verify Tenable API keys have proper permissions
- Check HEC token is valid
- Review logs: `tail -f logs/tenable_integration.log`

**Python 3.6.8 Compatibility**:
- Script uses `.format()` instead of f-strings
- No type annotations in runtime code
- Compatible package versions specified in requirements.txt

### Verify Compatibility

Run compatibility tests:
```bash
python test_compatibility.py
```

Expected output:
```
============================================================
Python 3.6.8 Compatibility Test
============================================================
Python Version: PASS
Imports: PASS
Checkpoint Manager: PASS
String Formatting: PASS
============================================================
SUCCESS: All compatibility tests passed!
```

## File Structure

```
tenable-hec-integration/
├── tenable_collector.py          # Main unified collection script
├── checkpoint_manager.py         # File-based checkpoint system
├── tenable_common.py             # Shared utilities (HEC handler, logging)
├── http_event_collector.py       # Cribl HEC client library
├── run_collector.sh              # Convenience wrapper script
├── test_compatibility.py         # Python 3.6.8 compatibility tests
├── test_tenable_access.py        # Tenable API connection test
├── requirements.txt              # Python dependencies
├── .env.example                  # Environment template
├── .env                          # Your configuration (git-ignored)
├── README.md                     # This file
├── README_PRODUCTION.md          # Detailed production guide
├── checkpoints/                  # Checkpoint JSON files (created at runtime)
├── logs/                         # Log files (created at runtime)
└── deprecated/                   # Old Redis-based scripts (archived)
```

## Architecture

### No Redis Required

Previous versions used Redis for checkpointing. This version uses simple JSON files:

**Benefits**:
- No external service installation needed
- Works in restricted environments
- Simpler deployment and maintenance
- No network dependency
- Easy to backup and inspect

### Python 3.6.8 Compatibility

Designed to work on older production systems:
- Uses `.format()` string formatting instead of f-strings
- No type annotations in runtime code
- Compatible dependency versions
- Tested on Python 3.6.8+

## Security Best Practices

- **Never commit `.env`**: Already in `.gitignore`
- **Restrict file permissions**: `chmod 600 .env`
- **Use dedicated API keys**: Create Tenable API keys specifically for this integration
- **Enable HEC SSL in production**: Set `CRIBL_HEC_SSL_VERIFY=true` with valid certificates
- **Rotate credentials regularly**: Update API keys and HEC tokens periodically
- **Run with minimal privileges**: No root/sudo required

## Migration from Redis Version

If migrating from the Redis-based version:

1. **Backup existing checkpoints** (optional):
   ```bash
   redis-cli KEYS "tenable:checkpoint:*" > redis_backup.txt
   ```

2. **Install new version**:
   ```bash
   git pull
   pip install --user -r requirements.txt
   ```

3. **Update `.env`**:
   - Remove `REDIS_*` variables
   - Add `CHECKPOINT_DIR=checkpoints`

4. **Run new version**:
   ```bash
   ./run_collector.sh --types all
   ```

Checkpoints will start fresh. The script will only collect new/modified data going forward.

## Advanced Usage

### Custom Checkpoint Directory

```bash
export CHECKPOINT_DIR=/var/lib/tenable/checkpoints
python tenable_collector.py --once --types all
```

### Run Specific Severity Vulnerabilities

The script automatically filters vulnerabilities:
- `vulnerabilities`: High, Critical, Medium severity
- `vulnerabilities_no_info`: Info severity only

### Parallel Execution

Different data types can run in parallel:
```bash
python tenable_collector.py --once --types assets &
python tenable_collector.py --once --types vulnerabilities &
python tenable_collector.py --once --types scans &
wait
```

## Support

- **Documentation**: See `README_PRODUCTION.md` for detailed production deployment guide
- **Issues**: Open an issue on GitHub
- **Tenable API**: https://developer.tenable.com/
- **Cribl Docs**: https://docs.cribl.io/

## License

This project uses the following open-source libraries:
- [pyTenable](https://github.com/tenable/pyTenable) - MIT License
- [Splunk-Class-httpevent](https://github.com/georgestarcher/Splunk-Class-httpevent) - Apache License 2.0
