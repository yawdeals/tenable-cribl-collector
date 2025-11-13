#!/usr/bin/env python3
"""
Tenable Vulnerabilities to Cribl HEC Integration
Pulls vulnerability data from Tenable scans and sends to Cribl via HEC
Uses Redis for checkpointing to track processed vulnerabilities
"""

import os
import time
import logging
import argparse
from typing import Dict, List, Optional
from dotenv import load_dotenv
from tenable.io import TenableIO
from tenable_common import RedisCheckpoint, CriblHECHandler, setup_logging


class TenableVulnerabilitiesIntegration:
    """Integration class for Tenable Vulnerabilities to Cribl"""
    
    def __init__(self):
        """Initialize the integration with configuration from environment"""
        # Load environment variables
        load_dotenv()
        
        # Setup logging
        log_level = os.getenv('LOG_LEVEL', 'INFO')
        setup_logging(log_level, 'tenable_vulnerabilities.log')
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
    
    def get_scan_vulnerabilities(self, scan_id: int) -> List[Dict]:
        """
        Get vulnerabilities from a scan
        
        Args:
            scan_id: Tenable scan ID
            
        Returns:
            List of vulnerability dictionaries
        """
        try:
            vulnerabilities = []
            details = self.get_scan_details(scan_id)
            
            if not details:
                return []
            
            # Get hosts from scan
            hosts = details.get('hosts', [])
            
            for host in hosts:
                host_id = host.get('host_id')
                if not host_id:
                    continue
                
                # Get vulnerabilities for this host
                try:
                    host_details = self.tenable.scans.host_details(scan_id, host_id)
                    vulns = host_details.get('vulnerabilities', [])
                    
                    for vuln in vulns:
                        vuln_data = dict(vuln)
                        vuln_data['scan_id'] = scan_id
                        vuln_data['host_id'] = host_id
                        vuln_data['host_fqdn'] = host.get('fqdn', '')
                        vuln_data['host_ip'] = host.get('hostname', '')
                        vulnerabilities.append(vuln_data)
                except Exception as e:
                    self.logger.error(f"Error getting vulnerabilities for host {host_id}: {e}")
                    continue
            
            self.logger.info(f"Retrieved {len(vulnerabilities)} vulnerabilities from scan {scan_id}")
            return vulnerabilities
        except Exception as e:
            self.logger.error(f"Error retrieving vulnerabilities for scan {scan_id}: {e}")
            return []
    
    def process_vulnerabilities(self):
        """Process vulnerabilities and send to Cribl"""
        checkpoint_key = "vulnerabilities"
        last_timestamp = self.checkpoint.get_last_timestamp(checkpoint_key)
        
        self.logger.info(f"Processing vulnerabilities (last checkpoint: {last_timestamp})")
        
        # Get scans to extract vulnerabilities from
        scans = self.get_scans(last_modification_date=last_timestamp)
        
        if not scans:
            self.logger.info("No new scans to process for vulnerabilities")
            return
        
        max_timestamp = last_timestamp or 0
        events_sent = 0
        
        for scan in scans:
            scan_id = scan.get('id')
            scan_uuid = scan.get('uuid', str(scan_id))
            
            # Check if vulnerabilities from this scan were already processed
            vuln_key = f"{checkpoint_key}:{scan_uuid}"
            if self.checkpoint.is_processed(checkpoint_key, scan_uuid):
                self.logger.debug(f"Vulnerabilities from scan {scan_id} already processed, skipping")
                continue
            
            # Get and send vulnerabilities
            self.logger.info(f"Processing vulnerabilities from scan {scan_id}")
            vulns = self.get_scan_vulnerabilities(scan_id)
            
            for vuln in vulns:
                # Send vulnerability data directly as the event
                if self.cribl.send_event(vuln):
                    events_sent += 1
            
            # Mark this scan's vulnerabilities as processed
            self.checkpoint.add_processed_id(checkpoint_key, scan_uuid)
            
            # Update max timestamp
            mod_date = scan.get('last_modification_date', 0)
            if mod_date > max_timestamp:
                max_timestamp = mod_date
            
            self.logger.info(f"Sent {len(vulns)} vulnerabilities from scan {scan_id}")
        
        # Update checkpoint timestamp
        if max_timestamp > (last_timestamp or 0):
            self.checkpoint.set_last_timestamp(checkpoint_key, max_timestamp)
        
        self.logger.info(f"Processed vulnerabilities from {len(scans)} scans, sent {events_sent} events to Cribl")
    
    def run_once(self):
        """Run the integration once"""
        self.logger.info("=== Starting Tenable Vulnerabilities to Cribl integration ===")
        
        try:
            self.process_vulnerabilities()
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
    parser = argparse.ArgumentParser(description='Tenable Vulnerabilities to Cribl HEC Integration')
    parser.add_argument('--once', action='store_true', help='Run once and exit')
    parser.add_argument('--interval', type=int, default=3600, 
                        help='Interval in seconds for continuous mode (default: 3600)')
    
    args = parser.parse_args()
    
    # Initialize integration
    integration = TenableVulnerabilitiesIntegration()
    
    # Run based on mode
    if args.once:
        integration.run_once()
    else:
        integration.run_continuous(interval=args.interval)


if __name__ == '__main__':
    main()
