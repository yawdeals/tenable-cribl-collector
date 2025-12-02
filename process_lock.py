#!/usr/bin/env python3
"""
Process lock manager to prevent overlapping script runs
"""
import os
import time
import logging


class ProcessLock:
    """Manages process lock file to prevent concurrent executions"""

    def __init__(self, lock_file='tenable_collector.lock',
                 lock_dir='locks', timeout=600):
        """
        Initialize process lock

        Args:
            lock_file: Name of the lock file
            lock_dir: Directory to store lock files
            timeout: Max age of stale lock in seconds (default: 10 minutes)
        """
        self.lock_dir = lock_dir
        self.lock_file = os.path.join(lock_dir, lock_file)
        self.timeout = timeout
        self.logger = logging.getLogger(__name__)

        # Create lock directory if needed
        if not os.path.exists(self.lock_dir):
            os.makedirs(self.lock_dir)

    def acquire(self):
        """
        Acquire the process lock

        Returns:
            True if lock acquired, False if another process is running
        """
        # Check if lock file exists
        if os.path.exists(self.lock_file):
            # Check if lock is stale
            lock_age = time.time() - os.path.getmtime(self.lock_file)

            if lock_age < self.timeout:
                # Active lock exists
                with open(self.lock_file, 'r') as f:
                    lock_data = f.read().strip()

                self.logger.warning("Another process is already running (PID: {0}, Age: {1:.0f}s)".format(
                    lock_data, lock_age))
                return False
            else:
                # Stale lock - remove it
                self.logger.warning(
                    "Removing stale lock file (Age: {0:.0f}s)".format(lock_age))
                try:
                    os.remove(self.lock_file)
                except Exception as e:
                    self.logger.error(
                        "Failed to remove stale lock: {0}".format(e))
                    return False

        # Create lock file
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
        """Release the process lock"""
        try:
            if os.path.exists(self.lock_file):
                os.remove(self.lock_file)
                self.logger.info("Process lock released")
        except Exception as e:
            self.logger.error("Failed to release lock: {0}".format(e))

    def __enter__(self):
        """Context manager entry"""
        if not self.acquire():
            raise RuntimeError(
                "Unable to acquire process lock - another instance is running")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.release()
        return False
