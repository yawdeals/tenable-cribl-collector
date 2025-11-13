#!/usr/bin/env python3
"""
File-Based Checkpoint Manager
Manages checkpointing using JSON files to track processed items
No external dependencies required - works in restricted environments
"""

import os
import json
import logging
from typing import Optional, Set


class FileCheckpoint:
    """Manages checkpointing using local JSON files"""
    
    def __init__(self, checkpoint_dir="checkpoints", key_prefix="tenable"):
        """
        Initialize file-based checkpoint manager
        
        Args:
            checkpoint_dir: Directory to store checkpoint files
            key_prefix: Prefix for checkpoint filenames
        """
        self.checkpoint_dir = checkpoint_dir
        self.key_prefix = key_prefix
        
        # Create checkpoint directory if it doesn't exist
        if not os.path.exists(self.checkpoint_dir):
            os.makedirs(self.checkpoint_dir)
            logging.info("Created checkpoint directory: {}".format(self.checkpoint_dir))
    
    def _get_checkpoint_file(self, key):
        """Get the full path to a checkpoint file"""
        filename = "{}_{}.json".format(self.key_prefix, key)
        return os.path.join(self.checkpoint_dir, filename)
    
    def get_last_timestamp(self, key):
        """
        Get the last processed timestamp for a given key
        
        Args:
            key: Checkpoint key identifier
            
        Returns:
            Last timestamp or None if not found
        """
        filepath = self._get_checkpoint_file(key)
        
        try:
            if os.path.exists(filepath):
                with open(filepath, 'r') as f:
                    data = json.load(f)
                    return data.get('last_timestamp')
        except Exception as e:
            logging.error("Error reading timestamp from {}: {}".format(filepath, e))
        
        return None
    
    def set_last_timestamp(self, key, timestamp):
        """
        Set the last processed timestamp for a given key
        
        Args:
            key: Checkpoint key identifier
            timestamp: Timestamp value to store
        """
        filepath = self._get_checkpoint_file(key)
        
        try:
            # Read existing data
            data = {}
            if os.path.exists(filepath):
                with open(filepath, 'r') as f:
                    data = json.load(f)
            
            # Update timestamp
            data['last_timestamp'] = timestamp
            
            # Write back
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
                
            logging.debug("Updated timestamp for {}: {}".format(key, timestamp))
        except Exception as e:
            logging.error("Error writing timestamp to {}: {}".format(filepath, e))
    
    def get_processed_ids(self, key):
        """
        Get the set of processed IDs for a given key
        
        Args:
            key: Checkpoint key identifier
            
        Returns:
            Set of processed IDs
        """
        filepath = self._get_checkpoint_file(key)
        
        try:
            if os.path.exists(filepath):
                with open(filepath, 'r') as f:
                    data = json.load(f)
                    ids = data.get('processed_ids', [])
                    return set(ids)
        except Exception as e:
            logging.error("Error reading processed IDs from {}: {}".format(filepath, e))
        
        return set()
    
    def add_processed_id(self, key, item_id):
        """
        Add an ID to the set of processed items
        
        Args:
            key: Checkpoint key identifier
            item_id: ID to mark as processed
        """
        filepath = self._get_checkpoint_file(key)
        
        try:
            # Read existing data
            data = {}
            if os.path.exists(filepath):
                with open(filepath, 'r') as f:
                    data = json.load(f)
            
            # Get or create processed_ids set
            processed_ids = set(data.get('processed_ids', []))
            processed_ids.add(str(item_id))
            
            # Convert back to list for JSON serialization
            data['processed_ids'] = list(processed_ids)
            
            # Write back
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
                
        except Exception as e:
            logging.error("Error adding processed ID to {}: {}".format(filepath, e))
    
    def is_processed(self, key, item_id):
        """
        Check if an ID has been processed
        
        Args:
            key: Checkpoint key identifier
            item_id: ID to check
            
        Returns:
            True if already processed, False otherwise
        """
        processed_ids = self.get_processed_ids(key)
        return str(item_id) in processed_ids
    
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
            logging.error("Error clearing checkpoint {}: {}".format(filepath, e))
    
    def get_all_checkpoints(self):
        """
        Get a list of all checkpoint keys
        
        Returns:
            List of checkpoint key names
        """
        checkpoints = []
        
        try:
            for filename in os.listdir(self.checkpoint_dir):
                if filename.startswith(self.key_prefix) and filename.endswith('.json'):
                    # Extract key from filename
                    key = filename.replace(self.key_prefix + '_', '').replace('.json', '')
                    checkpoints.append(key)
        except Exception as e:
            logging.error("Error listing checkpoints: {}".format(e))
        
        return checkpoints
