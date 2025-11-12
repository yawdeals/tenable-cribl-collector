#!/usr/bin/env python3
"""
Tenable Assets to Cribl HEC Integration
Pulls asset inventory data from Tenable and sends to Cribl via HEC
Uses Redis for checkpointing to track processed assets
"""

import os
import time
import logging
import argparse
from typing import Dict, Optional
from dotenv import load_dotenv
from tenable.io import TenableIO
from tenable_common import RedisCheckpoint, CriblHECHandler, setup_logging


class TenableAssetsIntegration:
    """Integration class for Tenable Assets to Cribl"""
    
    def __init__(self):
        """Initialize the integration with configuration from environment"""
        # Load environment variables
        load_dotenv()
        
        # Setup logging
        log_level = os.getenv('LOG_LEVEL', 'INFO')
        setup_logging(log_level, 'tenable_assets.log')
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
    
    def process_assets(self):
        """Process assets and send to Cribl"""
        checkpoint_key = "assets"
        
        try:
            self.logger.info("Processing assets")
            events_sent = 0
            assets_processed = 0
            
            for asset in self.tenable.assets.list():
                asset_dict = dict(asset)
                asset_id = asset_dict.get('id')
                
                # Check if already processed
                if self.checkpoint.is_processed(checkpoint_key, str(asset_id)):
                    continue
                
                # Send asset data directly as the event
                if self.cribl.send_event(asset_dict):
                    events_sent += 1
                    self.checkpoint.add_processed_id(checkpoint_key, str(asset_id))
                    assets_processed += 1
                    
                    if assets_processed % 100 == 0:
                        self.logger.info(f"Processed {assets_processed} assets so far...")
            
            self.logger.info(f"Processed {assets_processed} new assets, sent {events_sent} events to Cribl")
        except Exception as e:
            self.logger.error(f"Error processing assets: {e}", exc_info=True)
    
    def run_once(self):
        """Run the integration once"""
        self.logger.info("=== Starting Tenable Assets to Cribl integration ===")
        
        try:
            self.process_assets()
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
    parser = argparse.ArgumentParser(description='Tenable Assets to Cribl HEC Integration')
    parser.add_argument('--once', action='store_true', help='Run once and exit')
    parser.add_argument('--interval', type=int, default=3600, 
                        help='Interval in seconds for continuous mode (default: 3600)')
    
    args = parser.parse_args()
    
    # Initialize integration
    integration = TenableAssetsIntegration()
    
    # Run based on mode
    if args.once:
        integration.run_once()
    else:
        integration.run_continuous(interval=args.interval)


if __name__ == '__main__':
    main()
