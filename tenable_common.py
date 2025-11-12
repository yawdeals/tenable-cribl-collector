#!/usr/bin/env python3
"""
Common classes and utilities for Tenable to Cribl HEC integration
Shared across all integration scripts
"""

import os
import sys
import logging
from typing import Optional, Dict, List, Any
import redis
import http_event_collector as hec


class RedisCheckpoint:
    """Manages checkpointing using Redis to track processed scans"""
    
    def __init__(self, host: str, port: int, db: int = 0, password: Optional[str] = None, key_prefix: str = "tenable:checkpoint:"):
        """
        Initialize Redis connection for checkpointing
        
        Args:
            host: Redis host
            port: Redis port
            db: Redis database number
            password: Redis password (optional - not needed for free/local Redis)
            key_prefix: Prefix for checkpoint keys
        """
        self.key_prefix = key_prefix
        try:
            # Connect to Redis - password is None for free/local Redis
            redis_params = {
                'host': host,
                'port': port,
                'db': db,
                'decode_responses': True
            }
            
            # Only add password if provided (not needed for local Redis)
            if password:
                redis_params['password'] = password
            
            self.redis_client = redis.Redis(**redis_params)
            
            # Test connection
            self.redis_client.ping()
            logging.info(f"Connected to Redis at {host}:{port}")
        except Exception as e:
            logging.error(f"Failed to connect to Redis: {e}")
            raise
    
    def get_last_timestamp(self, key: str) -> Optional[int]:
        """
        Get the last processed timestamp for a given key
        
        Args:
            key: Checkpoint key identifier
            
        Returns:
            Last timestamp or None if not found
        """
        full_key = f"{self.key_prefix}{key}"
        value = self.redis_client.get(full_key)
        return int(value) if value else None
    
    def set_last_timestamp(self, key: str, timestamp: int):
        """
        Set the last processed timestamp for a given key
        
        Args:
            key: Checkpoint key identifier
            timestamp: Unix timestamp to save
        """
        full_key = f"{self.key_prefix}{key}"
        self.redis_client.set(full_key, timestamp)
        logging.debug(f"Checkpoint saved: {full_key} = {timestamp}")
    
    def get_processed_ids(self, key: str) -> set:
        """
        Get set of processed IDs
        
        Args:
            key: Checkpoint key identifier
            
        Returns:
            Set of processed IDs
        """
        full_key = f"{self.key_prefix}{key}:ids"
        return self.redis_client.smembers(full_key)
    
    def add_processed_id(self, key: str, item_id: str):
        """
        Add an ID to the processed set
        
        Args:
            key: Checkpoint key identifier
            item_id: ID to mark as processed
        """
        full_key = f"{self.key_prefix}{key}:ids"
        self.redis_client.sadd(full_key, item_id)
    
    def is_processed(self, key: str, item_id: str) -> bool:
        """
        Check if an ID has been processed
        
        Args:
            key: Checkpoint key identifier
            item_id: ID to check
            
        Returns:
            True if already processed
        """
        full_key = f"{self.key_prefix}{key}:ids"
        return self.redis_client.sismember(full_key, item_id)


class CriblHECHandler:
    """Handles sending events to Cribl via HTTP Event Collector"""
    
    def __init__(self, host: str, port: int, token: str, index: str, 
                 sourcetype: str, source: str, ssl_verify: bool = True):
        """
        Initialize Cribl HEC handler
        
        Args:
            host: Cribl HEC host
            port: Cribl HEC port
            token: HEC token
            index: Target index
            sourcetype: Event sourcetype
            source: Event source
            ssl_verify: Verify SSL certificate
        """
        self.hec_handler = hec.http_event_collector(
            token=token,
            http_event_server=host,
            http_event_port=str(port),
            http_event_server_ssl=ssl_verify,
            index=index
        )
        self.sourcetype = sourcetype
        self.source = source
        self.index = index
        logging.info(f"Initialized Cribl HEC: {host}:{port}")
    
    def send_event(self, event_data: Dict[str, Any], 
                   timestamp: Optional[int] = None,
                   sourcetype: Optional[str] = None,
                   source: Optional[str] = None) -> bool:
        """
        Send event to Cribl HEC
        
        Args:
            event_data: Event data dictionary
            timestamp: Optional event timestamp
            sourcetype: Optional override sourcetype
            source: Optional override source
            
        Returns:
            True if successful
        """
        try:
            payload = {}
            payload['event'] = event_data
            payload['sourcetype'] = sourcetype or self.sourcetype
            payload['source'] = source or self.source
            payload['index'] = self.index
            
            if timestamp:
                payload['time'] = timestamp
            
            self.hec_handler.sendEvent(payload)
            return True
        except Exception as e:
            logging.error(f"Failed to send event to Cribl: {e}")
            return False
    
    def send_batch(self, events: List[Dict[str, Any]]) -> int:
        """
        Send multiple events to Cribl
        
        Args:
            events: List of event dictionaries
            
        Returns:
            Number of successfully sent events
        """
        success_count = 0
        for event in events:
            if self.send_event(event):
                success_count += 1
        
        # Flush the batch
        try:
            self.hec_handler.flushBatch()
            logging.info(f"Flushed batch of {success_count} events to Cribl")
        except Exception as e:
            logging.error(f"Error flushing batch: {e}")
        
        return success_count


def setup_logging(log_level: str = 'INFO', log_file: str = 'tenable_integration.log'):
    """
    Setup logging configuration
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Log file name (will be placed in logs/ directory)
    """
    # Ensure logs directory exists
    log_dir = 'logs'
    os.makedirs(log_dir, exist_ok=True)
    
    # Prepend logs/ directory to log file path
    log_path = os.path.join(log_dir, log_file)
    
    logging.basicConfig(
        level=getattr(logging, log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_path)
        ]
    )
