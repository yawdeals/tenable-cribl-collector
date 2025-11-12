# Tenable to Cribl HEC Integration

A set of Python scripts that pull scan data, vulnerabilities, and assets from Tenable.io and send them to Cribl via HTTP Event Collector (HEC) with Redis-based checkpointing to avoid duplicate events.

## Features

- **Tenable.io Integration**: Pulls scans, vulnerabilities, and asset data using pyTenable
- **Cribl HEC**: Sends events to Cribl using HTTP Event Collector
- **Redis Checkpointing**: Tracks processed scans and assets to prevent duplicates
- **Modular Scripts**: Separate scripts for scans, vulnerabilities, and assets - run independently
- **Continuous Mode**: Can run continuously with configurable intervals
- **Comprehensive Logging**: Detailed logging to file and console
- **Free Redis Support**: Works with local Redis without password authentication

## Prerequisites

- Python 3.7 or higher
- Tenable.io account with API access keys
- Cribl instance with HTTP Event Collector enabled
- Redis server (local or remote) - **Free version works perfectly, no password needed**

## Installation

1. **Clone or download this repository**

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up Redis** (if not already running):
   
   The **free version of Redis works perfectly** - no password or premium features needed!
   
   #### Redis Setup

   **NOTE: NO ROOT ACCESS? See [redis_no_root.md](redis_no_root.md) for detailed instructions on running Redis without root!**
   
   **On Linux (Debian/Ubuntu) - With Root:**
   ```bash
   sudo apt-get update
   sudo apt-get install redis-server
   sudo systemctl start redis-server
   sudo systemctl enable redis-server
   
   # Verify Redis is running
   redis-cli ping
   # Should respond with: PONG
   ```
   
   **On Linux (RHEL/CentOS) - With Root:**
   ```bash
   sudo yum install redis
   sudo systemctl start redis
   sudo systemctl enable redis
   
   # Verify Redis is running
   redis-cli ping
   # Should respond with: PONG
   ```
   
   **Using Docker:**
   ```bash
   docker run -d -p 6379:6379 --name redis redis:latest
   
   # Verify Redis is running
   docker exec redis redis-cli ping
   # Should respond with: PONG
   ```
   
   **Without Root Access (Quick Method):**
   ```bash
   # Option 1: Use our automated setup script
   ./setup_redis_no_root.sh
   
   # Option 2: Manual setup
   # Download and compile Redis in your home directory
   cd ~
   wget https://download.redis.io/redis-stable.tar.gz
   tar -xzf redis-stable.tar.gz
   cd redis-stable
   make
   
   # Run Redis
   src/redis-server --daemonize yes --dir ~/redis-data
   
   # Test
   src/redis-cli ping
   # Should respond with: PONG
   ```
   
   **👉 For complete no-root installation guide, see [redis_no_root.md](redis_no_root.md)**
   
   **Note**: For local Redis installations, **NO PASSWORD is required**. Leave the `REDIS_PASSWORD` field empty in your `.env` file.

4. **Configure environment variables**:
   ```bash
   cp .env.example .env
   ```
   
   Edit `.env` and fill in your credentials:
   - `TENABLE_ACCESS_KEY`: Your Tenable.io access key
   - `TENABLE_SECRET_KEY`: Your Tenable.io secret key
   - `CRIBL_HEC_HOST`: Your Cribl server hostname/IP
   - `CRIBL_HEC_TOKEN`: Your HEC token
   - `REDIS_HOST`: Redis server host (default: localhost)
   - `REDIS_PORT`: Redis port (default: 6379)
   - Leave `REDIS_PASSWORD` empty for local/free Redis

## Configuration

### Tenable Configuration

Get your API keys from Tenable.io:
1. Log in to Tenable.io
2. Go to Settings → My Account → API Keys
3. Generate new access and secret keys
4. Add them to `.env`

### Cribl HEC Configuration

Configure HEC in Cribl:
1. Set up an HTTP Event Collector source in Cribl
2. Configure the HEC endpoint and generate a token
3. Note the host, port, and token for your `.env` file
4. Add the HEC endpoint details to `.env`

### Redis Configuration

For **local/free Redis** (default setup):
- Use default settings: `REDIS_HOST=localhost` and `REDIS_PORT=6379`
- **Leave `REDIS_PASSWORD` empty or commented out** - no password needed!
- No authentication or premium features required
- **No root access?** See [redis_no_root.md](redis_no_root.md) for installation guide

For **remote or managed Redis** with authentication:
- Set `REDIS_HOST` and `REDIS_PORT` to your remote server
- Set `REDIS_PASSWORD` only if your Redis instance requires authentication
- Adjust `REDIS_DB` if using a specific database number

**Free Redis is perfectly suitable for this integration!**

## Usage

The integration is split into **three separate scripts** that can be run independently:

1. **`tenable_scans.py`** - Processes scan summaries
2. **`tenable_vulnerabilities.py`** - Processes vulnerability findings
3. **`tenable_assets.py`** - Processes asset inventory

You can run all three together or just the ones you need!

### Run Individual Scripts Once

**Process scans only**:
```bash
python tenable_scans.py --once
```

**Process vulnerabilities only**:
```bash
python tenable_vulnerabilities.py --once
```

**Process assets only**:
```bash
python tenable_assets.py --once
```

**Run all three at once**:
```bash
python tenable_scans.py --once && \
python tenable_vulnerabilities.py --once && \
python tenable_assets.py --once
```

**Or use the convenience script**:
```bash
./run_all.sh --once
```

### Run Continuously

Each script can run continuously with configurable intervals:

**Scans (default 1 hour interval)**:
```bash
python tenable_scans.py
```

**Vulnerabilities (custom 30-minute interval)**:
```bash
python tenable_vulnerabilities.py --interval 1800
```

**Assets (custom 6-hour interval)**:
```bash
python tenable_assets.py --interval 21600
```

**Run all three continuously with helper script**:
```bash
./run_all.sh --interval 3600
```

### Run as Scheduled Jobs

**Using cron (Recommended)**:

See **[CRON_GUIDE.md](CRON_GUIDE.md)** for complete cron setup instructions and troubleshooting.

**Quick cron setup:**
```bash
# Edit crontab
crontab -e

# Add your schedule (examples):

# Run scans every hour
0 * * * * /path/to/tenable-hec-integration/cron_wrapper.sh tenable_scans.py

# Run vulnerabilities every 2 hours
0 */2 * * * /path/to/tenable-hec-integration/cron_wrapper.sh tenable_vulnerabilities.py

# Run assets once daily at 3 AM
0 3 * * * /path/to/tenable-hec-integration/cron_wrapper.sh tenable_assets.py
```

The `cron_wrapper.sh` script handles:
- Loading environment variables from `.env`
- Creating and managing log files
- Running the Python scripts with proper error handling
- Logging execution results with timestamps

## Event Types

The scripts send events to Cribl in JSON format: `{"event": {...}}`

All Tenable data is sent directly as the event payload without additional wrappers.

### 1. Scan Summary Events (`tenable_scans.py`)
- **Log file**: `tenable_scans.log`
- Contains complete scan metadata, status, and summary information from Tenable
- Format: `{"event": {scan_data}}`

### 2. Vulnerability Events (`tenable_vulnerabilities.py`)
- **Log file**: `tenable_vulnerabilities.log`
- Contains individual vulnerability findings from scans
- Includes host information and vulnerability details
- Format: `{"event": {vulnerability_data}}`

### 3. Asset Events (`tenable_assets.py`)
- **Log file**: `tenable_assets.log`
- Contains asset inventory information from Tenable
- Format: `{"event": {asset_data}}`

## Checkpointing

The script uses Redis to maintain checkpoints:
- **Timestamps**: Tracks the last modification date of processed scans
- **Processed IDs**: Maintains sets of processed scan and asset IDs
- **Key Prefix**: All checkpoint keys use the prefix defined in `REDIS_KEY_PREFIX`

To reset checkpoints and reprocess all data:
```bash
redis-cli
> KEYS tenable:checkpoint:*
> DEL tenable:checkpoint:scans
> DEL tenable:checkpoint:scans:ids
> DEL tenable:checkpoint:assets:ids
```

## Logging

Each script writes logs to its own file:
- **Scans**: `tenable_scans.log`
- **Vulnerabilities**: `tenable_vulnerabilities.log`
- **Assets**: `tenable_assets.log`
- **Console**: All scripts also output to standard output

Log level can be adjusted via `LOG_LEVEL` in `.env` (DEBUG, INFO, WARNING, ERROR, CRITICAL)

## Troubleshooting

### Connection Issues

**Tenable API**:
```bash
# Test connectivity
curl -H "X-ApiKeys: accessKey=YOUR_ACCESS_KEY; secretKey=YOUR_SECRET_KEY" \
  https://cloud.tenable.com/scans
```

**Cribl HEC**:
```bash
# Test HEC endpoint
curl -k https://YOUR_CRIBL_HOST:8088/services/collector/event \
  -H "Authorization: Splunk YOUR_HEC_TOKEN" \
  -d '{"event": "test event", "sourcetype": "manual"}'
```

**Redis**:
```bash
# Test Redis connection (should work without password for local setup)
redis-cli ping
# Should return: PONG

# Check Redis is listening
redis-cli info server
```

### Common Issues

1. **Import errors**: Make sure all dependencies are installed: `pip install -r requirements.txt`
2. **Redis connection refused**: Ensure Redis is running: `sudo systemctl status redis` or `docker ps | grep redis`
3. **Redis authentication error**: For local Redis, make sure `REDIS_PASSWORD` is empty or commented out in `.env`
4. **HEC SSL errors**: Set `CRIBL_HEC_SSL_VERIFY=false` for self-signed certificates
5. **No events in Cribl**: Check HEC token permissions and index configuration
6. **Module not found (tenable_common)**: Make sure all scripts are in the same directory

## Security Considerations

- Store `.env` file securely and never commit it to version control
- Use `.gitignore` to exclude `.env` files (already configured)
- Restrict file permissions: `chmod 600 .env`
- **For local Redis**: No password is needed, but ensure Redis only listens on localhost (default)
- **For production Redis**: Enable authentication with `requirepass` in `redis.conf` and use strong passwords
- Enable SSL/TLS for Cribl HEC in production
- Rotate API keys and tokens regularly
- Run scripts with minimal required privileges

## Dependencies

- **pytenable**: Tenable.io API client
- **python-dotenv**: Environment variable management
- **redis**: Redis client for checkpointing
- **requests**: HTTP library (used by HEC client)

## File Structure

```
tenable-hec-integration/
├── tenable_common.py             # Shared classes (Redis, HEC handler)
├── tenable_scans.py              # Scans integration script
├── tenable_vulnerabilities.py    # Vulnerabilities integration script
├── tenable_assets.py             # Assets integration script
├── run_all.sh                    # Helper script to run all three scripts
├── cron_wrapper.sh               # Wrapper script for running via cron
├── crontab.example               # Example crontab configuration
├── http_event_collector.py       # Cribl HEC client library
├── requirements.txt               # Python dependencies
├── .env.example                  # Environment template
├── .env                          # Your configuration (git-ignored)
├── .gitignore                    # Git ignore rules
├── redis_no_root.md              # Guide: Running Redis without root access
├── setup_redis_no_root.sh        # Automated Redis setup without root
├── CRON_GUIDE.md                 # Complete guide for cron scheduling
└── README.md                     # This file
```

## Which Scripts to Run?

- **For scan summaries only**: Run `tenable_scans.py`
- **For vulnerability data only**: Run `tenable_vulnerabilities.py`
- **For asset inventory only**: Run `tenable_assets.py`
- **For everything**: Run all three scripts using `run_all.sh`

**Recommendation**: Run the separate scripts as they give you more control and better resource management!

## Scheduling Options

### Cron (Recommended for Periodic Collection)
Best for hourly, daily, or weekly data collection. **No root access required.**

**Pros:**
- Simple and built-in to Linux
- No daemon required
- Easy to manage and troubleshoot
- Perfect for periodic collection
- Works without root access

**Example:**
```bash
# Run scans every hour
0 * * * * /path/to/tenable-hec-integration/cron_wrapper.sh tenable_scans.py
```

See **[CRON_GUIDE.md](CRON_GUIDE.md)** for complete setup instructions.

### Continuous Mode (For Real-Time Monitoring)
Best for near real-time data collection with frequent checks.

**Pros:**
- Lowest latency
- Immediate data collection
- No additional setup required

**Cons:**
- Uses more resources
- Requires process to stay running
- Need to manage restarts manually

**Example:**
```bash
python tenable_scans.py --interval 300  # Check every 5 minutes
```

## License

This project uses the following open-source libraries:
- [pyTenable](https://github.com/tenable/pyTenable) - MIT License
- [Splunk-Class-httpevent](https://github.com/georgestarcher/Splunk-Class-httpevent) - Apache License 2.0

## Support

For issues related to:
- **pyTenable**: https://github.com/tenable/pyTenable/issues
- **Cribl**: https://docs.cribl.io/
- **This script**: Create an issue in this repository
