#!/usr/bin/env python3
# Process lock manager to prevent concurrent script runs
import os
import time
import logging


class ProcessLock:
    # Manages lock file to prevent overlapping executions

    def __init__(self, lock_file='tenable_collector.lock',
                 lock_dir='locks', timeout=600):
        # Initialize lock with file path and timeout
        self.lock_dir = lock_dir
        self.lock_file = os.path.join(lock_dir, lock_file)
        self.timeout = timeout  # Stale lock timeout in seconds (default 10 min)
        self.logger = logging.getLogger(__name__)

        # Create lock directory if needed
        if not os.path.exists(self.lock_dir):
            os.makedirs(self.lock_dir)

    def acquire(self):
        # Attempt to acquire the process lock (returns True if successful)
        # Check if lock file exists
        if os.path.exists(self.lock_file):
            # Check if lock is stale (older than timeout)
            lock_age = time.time() - os.path.getmtime(self.lock_file)

            if lock_age < self.timeout:
                # Active lock exists - another process is running
                with open(self.lock_file, 'r') as f:
                    lock_data = f.read().strip()

                self.logger.warning("Another process is already running (PID: {0}, Age: {1:.0f}s)".format(
                    lock_data, lock_age))
                return False
            else:
                # Stale lock - previous process crashed or timed out
                self.logger.warning(
                    "Removing stale lock file (Age: {0:.0f}s)".format(lock_age))
                try:
                    os.remove(self.lock_file)
                except Exception as e:
                    self.logger.error(
                        "Failed to remove stale lock: {0}".format(e))
                    return False

        # Create lock file with current process ID
        try:
            with open(self.lock_file, 'w') as f:
                f.write(str(os.getpid()))

            self.logger.info(
                "Process lock acquired (PID: {0})".format(
                    os.getpid()))
            return True
        except Exception as e:
            self.logger.error("Failed to create lock file: {0}".format(e))
            return False

    def release(self):
        try:
            if os.path.exists(self.lock_file):
                os.remove(self.lock_file)
                self.logger.info("Process lock released")
        except Exception as e:
            self.logger.error("Failed to release lock: {0}".format(e))

    def __enter__(self):
        if not self.acquire():
            raise RuntimeError(
                "Unable to acquire process lock - another instance is running")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
        return False
