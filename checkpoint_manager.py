#!/usr/bin/env python3
"""
File-Based Checkpoint Manager (Optimized for High Volume)
Manages checkpointing using JSON files to track processed items
Uses in-memory caching with periodic flushing for performance
"""

import os
import json
import logging
import time
import tempfile
import shutil
from typing import Optional, Set, Dict


class FileCheckpoint:
    """Manages checkpointing with in-memory caching and batch writes"""

    def __init__(self, checkpoint_dir="checkpoints", key_prefix="tenable",
                 max_ids=100000, retention_days=30, flush_interval=100):
        """
        Initialize file-based checkpoint manager

        Args:
            checkpoint_dir: Directory to store checkpoint files
            key_prefix: Prefix for checkpoint filenames
            max_ids: Maximum number of IDs to store per checkpoint (default: 100,000)
            retention_days: Days to retain IDs before auto-cleanup (default: 30)
            flush_interval: Number of IDs to accumulate before auto-flush (default: 100)
        """
        self.checkpoint_dir = checkpoint_dir
        self.key_prefix = key_prefix
        self.max_ids = max_ids
        self.retention_seconds = retention_days * 86400
        self.flush_interval = flush_interval

        # In-memory cache for performance
        self._cache: Dict[str, Dict] = {}
        self._dirty_keys: Set[str] = set()
        self._pending_count: Dict[str, int] = {}

        # Create checkpoint directory if it doesn't exist
        if not os.path.exists(self.checkpoint_dir):
            os.makedirs(self.checkpoint_dir)
            logging.info(
                "Created checkpoint directory: {}".format(
                    self.checkpoint_dir))

    def _get_checkpoint_file(self, key):
        """Get the full path to a checkpoint file"""
        filename = "{}_{}.json".format(self.key_prefix, key)
        return os.path.join(self.checkpoint_dir, filename)

    def _load_checkpoint(self, key):
        """
        Load checkpoint into memory cache (lazy loading)

        Args:
            key: Checkpoint key identifier
        """
        if key in self._cache:
            return

        filepath = self._get_checkpoint_file(key)
        data = {
            'id_tracking': {},
            'last_timestamp': None,
            'last_cleanup': None,
            'total_tracked': 0
        }

        try:
            if os.path.exists(filepath):
                with open(filepath, 'r') as f:
                    loaded_data = json.load(f)
                    data.update(loaded_data)

                    # Migrate old format if needed
                    if 'processed_ids' in loaded_data and 'id_tracking' not in loaded_data:
                        current_time = int(time.time())
                        data['id_tracking'] = {
                            str(pid): current_time
                            for pid in loaded_data.get('processed_ids', [])
                        }
        except Exception as e:
            logging.error(
                "Error loading checkpoint {}: {}".format(
                    filepath, e))

        self._cache[key] = data
        self._pending_count[key] = 0

    def _atomic_write(self, filepath, data):
        """
        Atomically write data to file (prevents corruption on crash)

        Args:
            filepath: Path to write to
            data: Data dictionary to write
        """
        # Write to temp file first
        dir_name = os.path.dirname(filepath)
        fd, temp_path = tempfile.mkstemp(dir=dir_name, suffix='.tmp')

        try:
            with os.fdopen(fd, 'w') as f:
                json.dump(data, f, indent=2)

            # Atomic rename (on POSIX systems)
            shutil.move(temp_path, filepath)
        except Exception as e:
            # Clean up temp file on error
            if os.path.exists(temp_path):
                os.remove(temp_path)
            raise e

    def flush(self, key=None):
        """
        Flush cached checkpoint data to disk

        Args:
            key: Specific key to flush, or None for all dirty keys
        """
        keys_to_flush = [key] if key else list(self._dirty_keys)

        for k in keys_to_flush:
            if k not in self._cache:
                continue

            filepath = self._get_checkpoint_file(k)
            data = self._cache[k]

            try:
                # Apply retention and size limits before write
                current_time = int(time.time())
                cutoff_time = current_time - self.retention_seconds
                id_tracking = data.get('id_tracking', {})

                # Remove expired IDs
                id_tracking = {
                    id_key: ts for id_key, ts in id_tracking.items()
                    if ts > cutoff_time
                }

                # Enforce max size (keep most recent)
                if len(id_tracking) > self.max_ids:
                    sorted_ids = sorted(
                        id_tracking.items(), key=lambda x: x[1], reverse=True)
                    id_tracking = dict(sorted_ids[:self.max_ids])
                    logging.warning(
                        "Checkpoint {} trimmed to {} IDs".format(
                            k, self.max_ids))

                # Update cache and write
                data['id_tracking'] = id_tracking
                data['processed_ids'] = list(id_tracking.keys())
                data['last_cleanup'] = current_time
                data['total_tracked'] = len(id_tracking)

                self._atomic_write(filepath, data)
                self._dirty_keys.discard(k)
                self._pending_count[k] = 0

                logging.debug(
                    "Flushed checkpoint {}: {} IDs".format(
                        k, len(id_tracking)))
            except Exception as e:
                logging.error("Error flushing checkpoint {}: {}".format(k, e))

    def flush_all(self):
        """Flush all dirty checkpoints to disk"""
        self.flush()

    def get_last_timestamp(self, key):
        """
        Get the last processed timestamp for a given key

        Args:
            key: Checkpoint key identifier

        Returns:
            Last timestamp or None if not found
        """
        self._load_checkpoint(key)
        return self._cache[key].get('last_timestamp')

    def set_last_timestamp(self, key, timestamp):
        """
        Set the last processed timestamp for a given key

        Args:
            key: Checkpoint key identifier
            timestamp: Timestamp value to store
        """
        self._load_checkpoint(key)
        self._cache[key]['last_timestamp'] = timestamp
        self._dirty_keys.add(key)
        # Timestamps are important - flush immediately
        self.flush(key)

    def get_processed_ids(self, key):
        """
        Get the set of processed IDs for a given key (from cache)

        Args:
            key: Checkpoint key identifier

        Returns:
            Set of processed IDs
        """
        self._load_checkpoint(key)

        current_time = int(time.time())
        cutoff_time = current_time - self.retention_seconds
        id_tracking = self._cache[key].get('id_tracking', {})

        # Return only non-expired IDs
        return {
            id_key for id_key, ts in id_tracking.items()
            if ts > cutoff_time
        }

    def add_processed_id(self, key, item_id):
        """
        Add an ID to the set of processed items (cached, batched writes)

        Args:
            key: Checkpoint key identifier
            item_id: ID to mark as processed
        """
        self._load_checkpoint(key)

        # Add to in-memory cache
        current_time = int(time.time())
        self._cache[key].setdefault('id_tracking', {})[
            str(item_id)] = current_time
        self._dirty_keys.add(key)
        self._pending_count[key] = self._pending_count.get(key, 0) + 1

        # Auto-flush after flush_interval IDs
        if self._pending_count[key] >= self.flush_interval:
            self.flush(key)

    def add_processed_ids_batch(self, key, item_ids):
        """
        Add multiple IDs at once (more efficient than individual adds)

        Args:
            key: Checkpoint key identifier
            item_ids: List of item IDs to mark as processed
        """
        if not item_ids:
            return

        self._load_checkpoint(key)

        current_time = int(time.time())
        id_tracking = self._cache[key].setdefault('id_tracking', {})

        for item_id in item_ids:
            id_tracking[str(item_id)] = current_time

        self._dirty_keys.add(key)
        self._pending_count[key] = self._pending_count.get(
            key, 0) + len(item_ids)

        # Always flush after batch add
        self.flush(key)

    def is_processed(self, key, item_id):
        """
        Check if an ID has been processed (O(1) lookup from cache)

        Args:
            key: Checkpoint key identifier
            item_id: ID to check

        Returns:
            True if already processed, False otherwise
        """
        self._load_checkpoint(key)

        id_tracking = self._cache[key].get('id_tracking', {})
        str_id = str(item_id)

        if str_id not in id_tracking:
            return False

        # Check if expired
        current_time = int(time.time())
        cutoff_time = current_time - self.retention_seconds
        return id_tracking[str_id] > cutoff_time

    def clear_checkpoint(self, key):
        """
        Clear all checkpoint data for a given key

        Args:
            key: Checkpoint key identifier
        """
        filepath = self._get_checkpoint_file(key)

        try:
            if os.path.exists(filepath):
                os.remove(filepath)
                logging.info("Cleared checkpoint: {}".format(key))
        except Exception as e:
            logging.error(
                "Error clearing checkpoint {}: {}".format(
                    filepath, e))

    def get_all_checkpoints(self):
        """
        Get a list of all checkpoint keys

        Returns:
            List of checkpoint key names
        """
        checkpoints = []

        try:
            for filename in os.listdir(self.checkpoint_dir):
                if filename.startswith(
                        self.key_prefix) and filename.endswith('.json'):
                    # Extract key from filename
                    key = filename.replace(
                        self.key_prefix + '_',
                        '').replace(
                        '.json',
                        '')
                    checkpoints.append(key)
        except Exception as e:
            logging.error("Error listing checkpoints: {}".format(e))

        return checkpoints

    def get_checkpoint_stats(self, key):
        """
        Get statistics about a checkpoint file

        Args:
            key: Checkpoint key identifier

        Returns:
            Dictionary with checkpoint stats
        """
        self._load_checkpoint(key)
        filepath = self._get_checkpoint_file(key)

        stats = {
            'exists': False,
            'file_size_bytes': 0,
            'total_ids': 0,
            'cached_ids': 0,
            'pending_writes': 0,
            'last_cleanup': None,
            'last_timestamp': None
        }

        try:
            if os.path.exists(filepath):
                stats['exists'] = True
                stats['file_size_bytes'] = os.path.getsize(filepath)

            data = self._cache.get(key, {})
            stats['total_ids'] = len(data.get('id_tracking', {}))
            stats['cached_ids'] = stats['total_ids']
            stats['pending_writes'] = self._pending_count.get(key, 0)
            stats['last_cleanup'] = data.get('last_cleanup')
            stats['last_timestamp'] = data.get('last_timestamp')
        except Exception as e:
            logging.error(
                "Error getting checkpoint stats for {}: {}".format(
                    key, e))

        return stats

    def cleanup_all_checkpoints(self):
        """
        Force cleanup of all checkpoint files (remove expired IDs)
        """
        for key in self.get_all_checkpoints():
            try:
                self._load_checkpoint(key)
                self._dirty_keys.add(key)
                self.flush(key)
                processed_ids = self.get_processed_ids(key)
                logging.info(
                    "Cleaned checkpoint {}: {} active IDs".format(
                        key, len(processed_ids)))
            except Exception as e:
                logging.error(
                    "Error cleaning checkpoint {}: {}".format(
                        key, e))

    def __del__(self):
        """Flush all dirty checkpoints on destruction"""
        try:
            self.flush_all()
        except Exception:
            pass  # Ignore errors during cleanup
