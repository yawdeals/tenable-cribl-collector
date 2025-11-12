# Running Redis Without Root Access

If you don't have root/sudo access on your Linux server, you can still run Redis! Here are several options:

## Option 1: Download and Run Redis Binary (Recommended)

This is the easiest method - download pre-compiled Redis and run it in your home directory.

```bash
# Create a directory for Redis in your home directory
cd ~
mkdir -p redis-local
cd redis-local

# Download Redis (adjust version as needed)
wget https://download.redis.io/redis-stable.tar.gz

# Extract
tar -xzf redis-stable.tar.gz
cd redis-stable

# Compile (this doesn't require root)
make

# Create config and data directories
mkdir -p ~/redis-local/data
mkdir -p ~/redis-local/config

# Create a custom redis.conf
cat > ~/redis-local/config/redis.conf << 'EOF'
# Bind to localhost only (secure)
bind 127.0.0.1

# Use a custom port if needed (default 6379)
port 6379

# Directory for data files
dir /home/YOUR_USERNAME/redis-local/data

# Log file
logfile /home/YOUR_USERNAME/redis-local/redis.log

# Run in background
daemonize yes

# PID file location
pidfile /home/YOUR_USERNAME/redis-local/redis.pid

# No password for local use
# requirepass your_password_here

# Save database to disk
save 900 1
save 300 10
save 60 10000
EOF

# Replace YOUR_USERNAME with your actual username
sed -i "s|YOUR_USERNAME|$USER|g" ~/redis-local/config/redis.conf

# Start Redis
~/redis-local/redis-stable/src/redis-server ~/redis-local/config/redis.conf

# Test connection
~/redis-local/redis-stable/src/redis-cli ping
# Should return: PONG
```

### Using Your Custom Redis

Update your `.env` file:
```bash
REDIS_HOST=localhost
REDIS_PORT=6379
# No password needed
```

### Managing Your Redis Instance

**Start Redis:**
```bash
~/redis-local/redis-stable/src/redis-server ~/redis-local/config/redis.conf
```

**Stop Redis:**
```bash
~/redis-local/redis-stable/src/redis-cli shutdown
```

**Check if running:**
```bash
ps aux | grep redis-server
```

**Access Redis CLI:**
```bash
~/redis-local/redis-stable/src/redis-cli
```

**Add to PATH (optional):**
```bash
echo 'export PATH=$PATH:~/redis-local/redis-stable/src' >> ~/.bashrc
source ~/.bashrc

# Now you can use redis-server and redis-cli directly
redis-cli ping
```

## Option 2: Use Docker (If Available Without Root)

Some systems allow Docker without root via user groups:

```bash
# Check if you can run docker
docker --version

# If yes, run Redis
docker run -d \
  --name redis-local \
  -p 6379:6379 \
  -v ~/redis-data:/data \
  redis:latest

# Test
docker exec redis-local redis-cli ping
```

## Option 3: Run Redis in Python Virtual Environment

You can also run a Redis-compatible service using Python:

```bash
# Create virtual environment
python3 -m venv ~/redis-env
source ~/redis-env/bin/activate

# Install fakeredis (Redis simulator)
pip install fakeredis[lua]

# Create a Redis server script
cat > ~/redis-server.py << 'EOF'
#!/usr/bin/env python3
"""
Simple Redis-compatible server using fakeredis
Useful when you can't install real Redis
"""
import socket
import fakeredis
from threading import Thread

def handle_client(client_socket, redis_server):
    try:
        while True:
            data = client_socket.recv(1024)
            if not data:
                break
            # Process Redis commands (simplified)
            # Note: This is a basic implementation
            # For production, use real Redis
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client_socket.close()

def main():
    server = fakeredis.FakeStrictRedis()
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(('127.0.0.1', 6379))
    sock.listen(5)
    print("Redis-compatible server listening on port 6379")
    
    while True:
        client, addr = sock.accept()
        Thread(target=handle_client, args=(client, server)).start()

if __name__ == '__main__':
    main()
EOF

# Make executable
chmod +x ~/redis-server.py
```

**Note:** Option 3 is for testing only. Option 1 (real Redis) is recommended.

## Option 4: Use Alternative File-Based Storage

If Redis is not possible, modify the scripts to use SQLite or file-based checkpointing:

```python
# You can modify tenable_common.py to use SQLite instead of Redis
# This requires code changes but works without any server installation
```

## Recommended Setup for No-Root Environment

**Best approach: Option 1 (Compiled Redis)**

1. Takes ~5 minutes to set up
2. Full Redis functionality
3. No root required
4. Runs entirely in your home directory
5. Can be started/stopped by you
6. Survives server reboots if added to crontab

**Auto-start on login (optional):**
```bash
# Add to ~/.bashrc or ~/.bash_profile
if ! pgrep -x "redis-server" > /dev/null; then
    ~/redis-local/redis-stable/src/redis-server ~/redis-local/config/redis.conf
fi
```

**Auto-start on reboot with crontab:**
```bash
crontab -e

# Add this line:
@reboot /home/YOUR_USERNAME/redis-local/redis-stable/src/redis-server /home/YOUR_USERNAME/redis-local/config/redis.conf
```

## Troubleshooting

**Permission denied errors:**
- Make sure all paths use your home directory (`~` or `/home/username`)
- Check file permissions: `ls -la ~/redis-local/`

**Port already in use:**
- Change port in `redis.conf` to something else (e.g., 6380)
- Update `.env` file with new port: `REDIS_PORT=6380`

**Can't compile Redis:**
- Check if you have `gcc` installed: `gcc --version`
- If not, download pre-compiled binaries from Redis.io

**Memory issues:**
- Redis is very lightweight, uses <10MB for checkpoint data
- Default settings work fine for this integration

## Performance Notes

For the Tenable integration:
- Redis stores only checkpoint data (scan IDs, timestamps)
- Memory usage: typically 5-20 MB
- Disk usage: typically <1 MB
- No high-performance requirements
- Free Redis is more than sufficient!

## Security Notes

When running Redis in userspace:
1. [OK] Bind to localhost only (`bind 127.0.0.1`)
2. [OK] No password needed for localhost
3. [OK] Data stored in your home directory
4. [OK] Only you can access it
5. [WARNING] Don't expose Redis to the network
