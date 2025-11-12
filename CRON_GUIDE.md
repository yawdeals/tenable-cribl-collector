# Running Tenable to Cribl Integration with Cron

This guide shows you how to schedule the Tenable to Cribl HEC integration scripts using cron.

### Why Use Cron for This Integration?

- Simple, built-in Linux scheduler
- No additional services needed
- Perfect for periodic data collection
- Works on any Linux system
- Easy to manage and troubleshoot

## Quick Start

### 1. Make Scripts Executable

```bash
chmod +x cron_wrapper.sh
chmod +x tenable_scans.py
chmod +x tenable_vulnerabilities.py
chmod +x tenable_assets.py
```

### 2. Test the Wrapper Script

```bash
# Test running scans
./cron_wrapper.sh tenable_scans.py

# Test running vulnerabilities
./cron_wrapper.sh tenable_vulnerabilities.py

# Test running assets
./cron_wrapper.sh tenable_assets.py
```

Check the logs in the `logs/` directory to verify everything works.

### 3. Edit Crontab

```bash
crontab -e
```

Add your schedule (examples below).

## Cron Schedule Examples

### Example 1: Run All Three Scripts at Different Times

```bash
# Run scans every hour
0 * * * * /path/to/tenable-hec-integration/cron_wrapper.sh tenable_scans.py

# Run vulnerabilities every 2 hours
0 */2 * * * /path/to/tenable-hec-integration/cron_wrapper.sh tenable_vulnerabilities.py

# Run assets once per day at 3 AM
0 3 * * * /path/to/tenable-hec-integration/cron_wrapper.sh tenable_assets.py
```

### Example 2: Run All Scripts Together Daily

```bash
# Run all scripts at 2 AM daily
0 2 * * * /path/to/tenable-hec-integration/run_all.sh --once
```

### Example 3: Business Hours Only

```bash
# Run scans every 30 minutes during business hours (9 AM - 5 PM, Monday-Friday)
*/30 9-17 * * 1-5 /path/to/tenable-hec-integration/cron_wrapper.sh tenable_scans.py

# Run vulnerabilities twice daily during business hours
0 10,15 * * 1-5 /path/to/tenable-hec-integration/cron_wrapper.sh tenable_vulnerabilities.py
```

### Example 4: High-Frequency Collection

```bash
# Run scans every 15 minutes
*/15 * * * * /path/to/tenable-hec-integration/cron_wrapper.sh tenable_scans.py

# Run vulnerabilities every 30 minutes
*/30 * * * * /path/to/tenable-hec-integration/cron_wrapper.sh tenable_vulnerabilities.py

# Run assets every 6 hours
0 */6 * * * /path/to/tenable-hec-integration/cron_wrapper.sh tenable_assets.py
```

### Example 5: Complete Crontab Setup

```bash
# Tenable to Cribl HEC Integration
# Logs are stored in /path/to/tenable-hec-integration/logs/

# Scans - every hour
0 * * * * /path/to/tenable-hec-integration/cron_wrapper.sh tenable_scans.py

# Vulnerabilities - every 2 hours
0 */2 * * * /path/to/tenable-hec-integration/cron_wrapper.sh tenable_vulnerabilities.py

# Assets - once per day at 2 AM
0 2 * * * /path/to/tenable-hec-integration/cron_wrapper.sh tenable_assets.py

# Optional: Clean old logs monthly (keep last 30 days)
0 0 1 * * find /path/to/tenable-hec-integration/logs -name "*.log" -mtime +30 -delete
```

## Cron Time Format

```
* * * * * command
│ │ │ │ │
│ │ │ │ └─── Day of week (0-7, 0 and 7 = Sunday)
│ │ │ └───── Month (1-12)
│ │ └─────── Day of month (1-31)
│ └───────── Hour (0-23)
└─────────── Minute (0-59)
```

### Common Patterns:

- `*/15 * * * *` - Every 15 minutes
- `0 * * * *` - Every hour
- `0 */2 * * *` - Every 2 hours
- `0 9-17 * * *` - Every hour from 9 AM to 5 PM
- `0 0 * * *` - Daily at midnight
- `0 2 * * *` - Daily at 2 AM
- `0 0 * * 0` - Weekly on Sunday at midnight
- `0 0 1 * *` - Monthly on the 1st at midnight

## Viewing Cron Jobs

```bash
# List your cron jobs
crontab -l

# List cron jobs for specific user (requires root)
sudo crontab -l -u username
```

## Logging

The `cron_wrapper.sh` script automatically creates logs in the `logs/` directory:

- `logs/cron_tenable_scans_YYYYMMDD.log` - Scans script output
- `logs/cron_tenable_vulnerabilities_YYYYMMDD.log` - Vulnerabilities output
- `logs/cron_tenable_assets_YYYYMMDD.log` - Assets output

Each script also creates its own detailed log:
- `tenable_scans.log`
- `tenable_vulnerabilities.log`
- `tenable_assets.log`

### View Recent Logs

```bash
# View today's cron logs
tail -f logs/cron_tenable_scans_$(date +%Y%m%d).log

# View detailed script logs
tail -f tenable_scans.log
```

## Troubleshooting Cron Issues

### 1. Script Not Running

**Check cron service:**
```bash
# Check if cron is running
sudo systemctl status cron    # Debian/Ubuntu
sudo systemctl status crond    # RHEL/CentOS

# Start cron if needed
sudo systemctl start cron
```

**Check cron logs:**
```bash
# System cron logs
sudo tail -f /var/log/cron
# or
sudo tail -f /var/log/syslog | grep CRON
```

### 2. Environment Variables Not Loaded

Cron has a minimal environment. The `cron_wrapper.sh` script handles this by sourcing `.env`.

**Verify .env is loaded:**
```bash
# Add to crontab for debugging
* * * * * /path/to/cron_wrapper.sh tenable_scans.py 2>&1 | logger -t tenable-cron
```

### 3. Permission Issues

```bash
# Ensure files are executable
chmod +x /path/to/tenable-hec-integration/cron_wrapper.sh
chmod +x /path/to/tenable-hec-integration/*.py

# Ensure .env is readable
chmod 600 /path/to/tenable-hec-integration/.env

# Ensure logs directory is writable
mkdir -p /path/to/tenable-hec-integration/logs
chmod 755 /path/to/tenable-hec-integration/logs
```

### 4. Python Not Found

Cron may not have Python in its PATH.

**Solution 1: Use full path to Python in cron_wrapper.sh**
```bash
# Edit cron_wrapper.sh to use full path
/usr/bin/python3 "$SCRIPT_DIR/$SCRIPT_NAME" --once
```

**Solution 2: Set PATH in crontab**
```bash
# Add at top of crontab
PATH=/usr/local/bin:/usr/bin:/bin

# Then your cron jobs
0 * * * * /path/to/cron_wrapper.sh tenable_scans.py
```

### 5. Redis Not Running

```bash
# Check Redis status
redis-cli ping

# For userspace Redis (no root)
~/redis-local/redis-stable/src/redis-cli ping

# Auto-start Redis in crontab if needed
@reboot ~/redis-local/redis-stable/src/redis-server ~/redis-local/config/redis.conf
```

## Email Notifications

Cron can email you on errors:

```bash
# Add to top of crontab
MAILTO=your-email@example.com

# Cron will email output/errors
0 * * * * /path/to/cron_wrapper.sh tenable_scans.py
```

To suppress emails for successful runs:
```bash
# Only email on errors (exit code != 0)
0 * * * * /path/to/cron_wrapper.sh tenable_scans.py || echo "Script failed!"
```

## Testing Your Cron Setup

```bash
# 1. Test wrapper script directly
./cron_wrapper.sh tenable_scans.py

# 2. Create a test cron job that runs every minute
# Edit crontab: crontab -e
# Add:
* * * * * /path/to/tenable-hec-integration/cron_wrapper.sh tenable_scans.py

# 3. Monitor logs
tail -f logs/cron_tenable_scans_*.log

# 4. After verifying, remove test job and set proper schedule
crontab -e
```

## Best Practices

1. **Use the wrapper script**: Always use `cron_wrapper.sh` - it handles environment variables and logging

2. **Stagger schedules**: Don't run all scripts at the same time
   ```bash
   0 * * * *   /path/to/cron_wrapper.sh tenable_scans.py
   15 * * * *  /path/to/cron_wrapper.sh tenable_vulnerabilities.py
   30 */6 * * * /path/to/cron_wrapper.sh tenable_assets.py
   ```

3. **Monitor logs**: Regularly check logs for errors
   ```bash
   # Create a log monitoring cron job
   0 8 * * * grep -i error /path/to/logs/cron_*.log | mail -s "Tenable Integration Errors" admin@example.com
   ```

4. **Clean old logs**: Prevent disk space issues
   ```bash
   0 0 * * 0 find /path/to/logs -name "*.log" -mtime +30 -delete
   ```

5. **Use absolute paths**: Always use full paths in crontab

6. **Test first**: Always test with `--once` flag before scheduling

## Cron vs Systemd vs Continuous Mode

| Method | Best For | Pros | Cons |
|--------|----------|------|------|
| **Cron** | Periodic collection (hourly, daily) | Simple, no daemon needed | Less precise timing |
| **Systemd** | Always-running service | Precise intervals, auto-restart | Requires root, more complex |
| **Continuous** | Real-time monitoring | Lowest latency | Uses more resources |

**Use Cron When:**

- Collecting data hourly or daily
- No root access for systemd
- Want simple, easy-to-understand scheduling
- Server resources are limited
- Don't need real-time data

**Use Systemd When:**

- Need exact timing (every 30 minutes on the dot)
- Want automatic restart on failure
- Have root access
- Running as a production service

### When to Use Continuous Mode:
- Need near real-time data
- Checking for updates very frequently (every few minutes)
- Have dedicated server resources

## Example: Production Cron Setup

```bash
# File: /etc/cron.d/tenable-splunk-integration
# This runs as the 'tenable' user

# Environment
SHELL=/bin/bash
PATH=/usr/local/bin:/usr/bin:/bin
MAILTO=admin@example.com

# Tenable to Cribl HEC Integration
# User: tenable

# Scans - every hour at 5 minutes past
5 * * * * tenable /opt/tenable-hec-integration/cron_wrapper.sh tenable_scans.py

# Vulnerabilities - every 2 hours at 15 minutes past
15 */2 * * * tenable /opt/tenable-hec-integration/cron_wrapper.sh tenable_vulnerabilities.py

# Assets - daily at 3:30 AM
30 3 * * * tenable /opt/tenable-hec-integration/cron_wrapper.sh tenable_assets.py

# Cleanup old logs weekly
0 0 * * 0 tenable find /opt/tenable-hec-integration/logs -name "*.log" -mtime +30 -delete
```

## Summary

Cron is perfect for running these scripts on a schedule! Just:

1. Use the provided `cron_wrapper.sh` script
2. Add entries to your crontab
3. Monitor the logs in `logs/` directory

The scripts are designed to be cron-friendly with:
- `--once` flag for single runs
- Proper exit codes
- Complete logging
- Redis checkpointing to prevent duplicates
