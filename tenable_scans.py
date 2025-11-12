#!/usr/bin/env python3
"""
Tenable Scans to Cribl HEC Integration
Pulls scan summary data from Tenable and sends to Cribl via HEC
Uses Redis for checkpointing to track processed scans
"""

import os
import time
import logging
import argparse
from typing import Dict, List, Optional
from dotenv import load_dotenv
from tenable.io import TenableIO
from tenable_common import RedisCheckpoint, CriblHECHandler, setup_logging


class TenableScansIntegration:
    """Integration class for Tenable Scans to Cribl"""
    
    def __init__(self):
        """Initialize the integration with configuration from environment"""
        # Load environment variables
        load_dotenv()
        
        # Setup logging
        log_level = os.getenv('LOG_LEVEL', 'INFO')
        setup_logging(log_level, 'tenable_scans.log')
        self.logger = logging.getLogger(__name__)
        
        # Initialize Tenable client
        self.tenable = TenableIO(
            access_key=os.getenv('TENABLE_ACCESS_KEY'),
            secret_key=os.getenv('TENABLE_SECRET_KEY'),
            url=os.getenv('TENABLE_URL', 'https://cloud.tenable.com')
        )
        self.logger.info("Initialized Tenable.io client")
        
        # Initialize Cribl HEC handler
        self.cribl = CriblHECHandler(
            host=os.getenv('CRIBL_HEC_HOST'),
            port=int(os.getenv('CRIBL_HEC_PORT', 8088)),
            token=os.getenv('CRIBL_HEC_TOKEN'),
            index='',
            sourcetype='',
            source='',
            ssl_verify=os.getenv('CRIBL_HEC_SSL_VERIFY', 'true').lower() == 'true'
        )
        
        # Initialize Redis checkpoint
        redis_password = os.getenv('REDIS_PASSWORD')
        self.checkpoint = RedisCheckpoint(
            host=os.getenv('REDIS_HOST', 'localhost'),
            port=int(os.getenv('REDIS_PORT', 6379)),
            db=int(os.getenv('REDIS_DB', 0)),
            password=redis_password if redis_password else None,  # None for free Redis
            key_prefix=os.getenv('REDIS_KEY_PREFIX', 'tenable:checkpoint:')
        )
    
    def get_scans(self, last_modification_date: Optional[int] = None) -> List[Dict]:
        """
        Get scans from Tenable
        
        Args:
            last_modification_date: Only get scans modified after this timestamp
            
        Returns:
            List of scan dictionaries
        """
        try:
            scans = []
            for scan in self.tenable.scans.list():
                scan_dict = dict(scan)
                
                # Filter by last modification date if provided
                if last_modification_date:
                    if scan_dict.get('last_modification_date', 0) <= last_modification_date:
                        continue
                
                scans.append(scan_dict)
            
            self.logger.info(f"Retrieved {len(scans)} scans from Tenable")
            return scans
        except Exception as e:
            self.logger.error(f"Error retrieving scans: {e}")
            return []
    
    def get_scan_details(self, scan_id: int) -> Optional[Dict]:
        """
        Get detailed information about a specific scan
        
        Args:
            scan_id: Tenable scan ID
            
        Returns:
            Scan details dictionary or None
        """
        try:
            details = self.tenable.scans.details(scan_id)
            return dict(details)
        except Exception as e:
            self.logger.error(f"Error retrieving scan details for {scan_id}: {e}")
            return None
    
    def process_scans(self):
        """Process scans and send to Cribl"""
        checkpoint_key = "scans"
        last_timestamp = self.checkpoint.get_last_timestamp(checkpoint_key)
        
        self.logger.info(f"Processing scans (last checkpoint: {last_timestamp})")
        
        # Get scans
        scans = self.get_scans(last_modification_date=last_timestamp)
        
        if not scans:
            self.logger.info("No new scans to process")
            return
        
        max_timestamp = last_timestamp or 0
        events_sent = 0
        
        for scan in scans:
            scan_id = scan.get('id')
            scan_uuid = scan.get('uuid', str(scan_id))
            
            # Check if already processed
            if self.checkpoint.is_processed(checkpoint_key, scan_uuid):
                self.logger.debug(f"Scan {scan_id} already processed, skipping")
                continue
            
            # Get scan details
            scan_details = self.get_scan_details(scan_id)
            if scan_details:
                # Send scan summary event - send details directly as the event
                if self.cribl.send_event(scan_details):
                    events_sent += 1
                    self.logger.info(f"Sent scan {scan_id} to Cribl")
            
            # Mark as processed
            self.checkpoint.add_processed_id(checkpoint_key, scan_uuid)
            
            # Update max timestamp
            mod_date = scan.get('last_modification_date', 0)
            if mod_date > max_timestamp:
                max_timestamp = mod_date
        
        # Update checkpoint timestamp
        if max_timestamp > (last_timestamp or 0):
            self.checkpoint.set_last_timestamp(checkpoint_key, max_timestamp)
        
        self.logger.info(f"Processed {len(scans)} scans, sent {events_sent} events to Cribl")
    
    def run_once(self):
        """Run the integration once"""
        self.logger.info("=== Starting Tenable Scans to Cribl integration ===")
        
        try:
            self.process_scans()
            self.logger.info("=== Integration run completed ===")
        except Exception as e:
            self.logger.error(f"Error during integration run: {e}", exc_info=True)
    
    def run_continuous(self, interval: int = 3600):
        """
        Run the integration continuously
        
        Args:
            interval: Seconds between runs (default 3600 = 1 hour)
        """
        self.logger.info(f"Starting continuous integration (interval: {interval}s)")
        
        while True:
            try:
                self.run_once()
                self.logger.info(f"Sleeping for {interval} seconds...")
                time.sleep(interval)
            except KeyboardInterrupt:
                self.logger.info("Received interrupt signal, shutting down...")
                break
            except Exception as e:
                self.logger.error(f"Unexpected error: {e}", exc_info=True)
                self.logger.info(f"Retrying in {interval} seconds...")
                time.sleep(interval)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Tenable Scans to Cribl HEC Integration')
    parser.add_argument('--once', action='store_true', help='Run once and exit')
    parser.add_argument('--interval', type=int, default=3600, 
                        help='Interval in seconds for continuous mode (default: 3600)')
    
    args = parser.parse_args()
    
    # Initialize integration
    integration = TenableScansIntegration()
    
    # Run based on mode
    if args.once:
        integration.run_once()
    else:
        integration.run_continuous(interval=args.interval)


if __name__ == '__main__':
    main()
