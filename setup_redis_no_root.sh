#!/bin/bash
# Quick setup script for Redis without root access
# This script downloads, compiles, and runs Redis in your home directory

set -e

echo "==================================================================="
echo "  Redis Installation Without Root Access"
echo "==================================================================="
echo ""

# Set up directories
REDIS_HOME="$HOME/redis-local"
REDIS_VERSION="stable"

echo "Installing Redis to: $REDIS_HOME"
echo ""

# Create directory structure
mkdir -p "$REDIS_HOME"
cd "$REDIS_HOME"

# Download Redis
echo "1. Downloading Redis..."
if [ ! -f "redis-$REDIS_VERSION.tar.gz" ]; then
    wget https://download.redis.io/redis-$REDIS_VERSION.tar.gz
fi

# Extract
echo "2. Extracting Redis..."
tar -xzf redis-$REDIS_VERSION.tar.gz

# Compile
echo "3. Compiling Redis (this may take a minute)..."
cd redis-$REDIS_VERSION
make

# Create data and config directories
echo "4. Setting up directories..."
mkdir -p "$REDIS_HOME/data"
mkdir -p "$REDIS_HOME/config"
mkdir -p "$REDIS_HOME/logs"

# Create configuration file
echo "5. Creating configuration file..."
cat > "$REDIS_HOME/config/redis.conf" << EOF
# Bind to localhost only (secure)
bind 127.0.0.1

# Default Redis port
port 6379

# Directory for data files
dir $REDIS_HOME/data

# Log file
logfile $REDIS_HOME/logs/redis.log

# Run in background
daemonize yes

# PID file location
pidfile $REDIS_HOME/redis.pid

# No password for local use
# Uncomment the line below to set a password:
# requirepass your_secure_password_here

# Save database to disk
save 900 1
save 300 10
save 60 10000

# Maximum memory (adjust as needed)
maxmemory 256mb
maxmemory-policy allkeys-lru

# Logging
loglevel notice
EOF

echo "6. Starting Redis..."
"$REDIS_HOME/redis-$REDIS_VERSION/src/redis-server" "$REDIS_HOME/config/redis.conf"

# Wait a moment for Redis to start
sleep 2

# Test connection
echo "7. Testing Redis connection..."
if "$REDIS_HOME/redis-$REDIS_VERSION/src/redis-cli" ping | grep -q PONG; then
    echo ""
    echo "[SUCCESS] Redis is running!"
    echo ""
else
    echo ""
    echo "[ERROR] Redis did not start properly"
    echo "Check the log file: $REDIS_HOME/logs/redis.log"
    exit 1
fi

# Add to PATH suggestion
echo "==================================================================="
echo "  Installation Complete!"
echo "==================================================================="
echo ""
echo "Redis is now running in the background on port 6379"
echo ""
echo "Configuration file: $REDIS_HOME/config/redis.conf"
echo "Data directory:     $REDIS_HOME/data"
echo "Log file:           $REDIS_HOME/logs/redis.log"
echo ""
echo "Useful commands:"
echo ""
echo "  Start Redis:"
echo "    $REDIS_HOME/redis-$REDIS_VERSION/src/redis-server $REDIS_HOME/config/redis.conf"
echo ""
echo "  Stop Redis:"
echo "    $REDIS_HOME/redis-$REDIS_VERSION/src/redis-cli shutdown"
echo ""
echo "  Check if running:"
echo "    ps aux | grep redis-server"
echo ""
echo "  Access Redis CLI:"
echo "    $REDIS_HOME/redis-$REDIS_VERSION/src/redis-cli"
echo ""
echo "  Test connection:"
echo "    $REDIS_HOME/redis-$REDIS_VERSION/src/redis-cli ping"
echo ""
echo "==================================================================="
echo "  Optional: Add Redis to your PATH"
echo "==================================================================="
echo ""
echo "Run this command to add Redis to your PATH:"
echo ""
echo "  echo 'export PATH=\$PATH:$REDIS_HOME/redis-$REDIS_VERSION/src' >> ~/.bashrc"
echo "  source ~/.bashrc"
echo ""
echo "After that, you can use 'redis-cli' and 'redis-server' directly!"
echo ""
echo "==================================================================="
echo "  Auto-start on Login (Optional)"
echo "==================================================================="
echo ""
echo "To auto-start Redis when you login, add to ~/.bashrc:"
echo ""
echo "  if ! pgrep -x 'redis-server' > /dev/null; then"
echo "      $REDIS_HOME/redis-$REDIS_VERSION/src/redis-server $REDIS_HOME/config/redis.conf"
echo "  fi"
echo ""
echo "==================================================================="
echo "  Your .env Configuration"
echo "==================================================================="
echo ""
echo "Use these settings in your .env file:"
echo ""
echo "  REDIS_HOST=localhost"
echo "  REDIS_PORT=6379"
echo "  # REDIS_PASSWORD=  (leave empty - no password needed)"
echo ""
echo "==================================================================="
