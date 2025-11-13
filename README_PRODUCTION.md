# Tenable to Cribl HEC Integration - Production Edition

## Overview
Production-ready integration for collecting Tenable.io data and forwarding to Cribl via HTTP Event Collector (HEC).

**Key Features:**
- Python 3.6.8+ compatible
- No Redis required - Uses file-based checkpointing
- No external dependencies to install on server
- Handles all Tenable data types in one script
- Production-tested and hardened

## Requirements

- **Python**: 3.6.8 or higher
- **Tenable.io**: Valid API keys
- **Cribl**: HEC endpoint with token
- **No root access required**
- **No Redis installation needed**

## Quick Start

### 1. Install Dependencies

```bash
pip install --user -r requirements.txt
```

### 2. Configure Environment

Copy and edit the configuration file:

```bash
cp .env.example .env
# Edit .env with your credentials
```

Required settings in `.env`:
```bash
# Tenable API
TENABLE_ACCESS_KEY=your_access_key_here
TENABLE_SECRET_KEY=your_secret_key_here

# Cribl HEC
CRIBL_HEC_HOST=your_cribl_host
CRIBL_HEC_PORT=8088
CRIBL_HEC_TOKEN=your_hec_token
```

### 3. Run Collection

**Collect all data types:**
```bash
python tenable_collector.py --once
```

**Collect specific data types:**
```bash
# Assets only
python tenable_collector.py --once --types assets

# Vulnerabilities only
python tenable_collector.py --once --types vulnerabilities

# Multiple types
python tenable_collector.py --once --types assets vulnerabilities scans
```

## Available Data Types

| Type | Description | Sourcetype |
|------|-------------|------------|
| `assets` | Asset inventory | `tenable:asset` |
| `vulnerabilities` | All vulnerabilities | `tenable:vulnerability` |
| `vulnerabilities_no_info` | Informational findings only | `tenable:vulnerability` |
| `plugins` | Plugin families | `tenable:plugin` |
| `scans` | Scan summaries | `tenable:scan` |
| `all` | All of the above | Multiple |

## Checkpointing

The integration uses file-based checkpointing in the `checkpoints/` directory:

- **No Redis required**
- Checkpoints stored as JSON files
- Prevents duplicate data collection
- Safe for production use

Checkpoint files are automatically created:
```
checkpoints/
├── tenable_assets.json
├── tenable_vulnerabilities.json
├── tenable_scans.json
└── tenable_plugins.json
```

To reset checkpoints and re-collect all data:
```bash
rm -rf checkpoints/
```

## Production Deployment

### Option 1: Cron Job (Recommended)

Add to your crontab:

```bash
# Collect assets daily at 2 AM
0 2 * * * cd /path/to/tenable-hec-integration && python tenable_collector.py --once --types assets >> logs/cron.log 2>&1

# Collect vulnerabilities every 6 hours
0 */6 * * * cd /path/to/tenable-hec-integration && python tenable_collector.py --once --types vulnerabilities >> logs/cron.log 2>&1

# Collect all data types daily at 1 AM
0 1 * * * cd /path/to/tenable-hec-integration && python tenable_collector.py --once >> logs/cron.log 2>&1
```

### Option 2: Manual Execution

Run as needed:
```bash
./run_collector.sh
```

## Logs

All logs are written to `logs/` directory:
- `logs/tenable_integration.log` - Main application log
- `logs/cron.log` - Cron execution log (if using cron)

## Troubleshooting

### Authentication Errors

**Error**: `401 Unauthorized` or `Missing authentication`

**Solution**:
1. Verify API keys in `.env`
2. Ensure keys are 64-character hexadecimal strings
3. Check keys have no spaces or special characters
4. Verify Tenable.io account has active scanners/data

### No Data Collected

**Error**: "No new scans to process" or similar

**Solution**:
1. Verify Tenable.io account has scan data
2. Check scanners are active in Tenable.io console
3. Delete checkpoints to force re-collection: `rm -rf checkpoints/`

### Cribl Connection Errors

**Error**: Cannot connect to Cribl HEC

**Solution**:
1. Verify `CRIBL_HEC_HOST` and `CRIBL_HEC_PORT` in `.env`
2. Test connectivity: `curl -k https://CRIBL_HOST:8088`
3. Verify HEC token is valid
4. Check firewall rules allow outbound connections

### Python Version Issues

**Error**: Syntax errors or import errors

**Solution**:
1. Check Python version: `python --version` (must be 3.6.8+)
2. Use correct Python binary: `python3` instead of `python`
3. Install dependencies: `pip install --user -r requirements.txt`

## File Structure

```
tenable-hec-integration/
├── checkpoint_manager.py      # File-based checkpointing
├── tenable_common.py          # Shared utilities
├── tenable_collector.py       # Main collection script
├── http_event_collector.py    # Cribl HEC client
├── .env                       # Configuration (not in git)
├── .env.example               # Configuration template
├── requirements.txt           # Python dependencies
├── checkpoints/               # Checkpoint data (auto-created)
└── logs/                      # Log files (auto-created)
```

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `TENABLE_ACCESS_KEY` | Yes | - | Tenable API access key |
| `TENABLE_SECRET_KEY` | Yes | - | Tenable API secret key |
| `TENABLE_URL` | No | `https://cloud.tenable.com` | Tenable API URL |
| `CRIBL_HEC_HOST` | Yes | - | Cribl HEC hostname/IP |
| `CRIBL_HEC_PORT` | No | `8088` | Cribl HEC port |
| `CRIBL_HEC_TOKEN` | Yes | - | Cribl HEC token |
| `CRIBL_HEC_SSL_VERIFY` | No | `true` | Verify SSL certificate |
| `CHECKPOINT_DIR` | No | `checkpoints` | Checkpoint directory |
| `LOG_LEVEL` | No | `INFO` | Logging level |

## Security Notes

- `.env` file is excluded from git via `.gitignore`
- Never commit credentials to version control
- Store API keys securely
- Use HTTPS for Cribl HEC connections
- Checkpoints contain only metadata, not sensitive data

## Support

For issues or questions:
1. Check logs in `logs/tenable_integration.log`
2. Review this README
3. Check GitHub Issues: https://github.com/yawdeals/tenable-hec-integration

## License

MIT License - See LICENSE file for details
