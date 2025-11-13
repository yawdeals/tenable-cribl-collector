#!/usr/bin/env python
"""
Comprehensive Tenable to Cribl Integration
Handles all Tenable data types in one production-ready script
Python 3.6.8+ compatible - No Redis dependency
"""

import os
import argparse
import logging
from dotenv import load_dotenv
from tenable.io import TenableIO
from checkpoint_manager import FileCheckpoint
from tenable_common import CriblHECHandler, setup_logging


class TenableIntegration:
    """Main integration class for all Tenable data types"""
    
    def __init__(self):
        """Initialize the integration with configuration from environment"""
        load_dotenv()
        
        # Setup logging
        log_level = os.getenv('LOG_LEVEL', 'INFO')
        setup_logging(log_level, 'tenable_integration.log')
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
        
        # Initialize file-based checkpoint
        self.checkpoint = FileCheckpoint(
            checkpoint_dir=os.getenv('CHECKPOINT_DIR', 'checkpoints'),
            key_prefix='tenable'
        )
        self.logger.info("Initialized file-based checkpointing")
    
    def process_assets(self):
        """Process asset inventory data"""
        self.logger.info("Starting asset collection")
        checkpoint_key = "assets"
        
        try:
            assets = list(self.tenable.assets.list())
            self.logger.info("Retrieved {} assets from Tenable".format(len(assets)))
            
            events_sent = 0
            for asset in assets:
                asset_id = asset.get('id')
                
                # Skip if already processed
                if self.checkpoint.is_processed(checkpoint_key, asset_id):
                    continue
                
                # Send to Cribl with sourcetype
                event_data = dict(asset)
                event_data['event_type'] = 'tenable_asset'
                
                if self.cribl.send_event(event_data, sourcetype='tenable:asset'):
                    events_sent += 1
                    self.checkpoint.add_processed_id(checkpoint_key, asset_id)
            
            self.logger.info("Sent {} asset events to Cribl".format(events_sent))
            return events_sent
            
        except Exception as e:
            self.logger.error("Error processing assets: {}".format(e))
            return 0
    
    def process_vulnerabilities(self, severity=None):
        """Process vulnerability data"""
        self.logger.info("Starting vulnerability collection")
        checkpoint_key = "vulnerabilities"
        
        try:
            # Get all scans first
            scans = list(self.tenable.scans.list())
            self.logger.info("Retrieved {} scans".format(len(scans)))
            
            events_sent = 0
            for scan in scans:
                scan_id = scan.get('id')
                
                try:
                    # Get scan details
                    scan_details = self.tenable.scans.details(scan_id)
                    hosts = scan_details.get('hosts', [])
                    
                    for host in hosts:
                        host_id = host.get('host_id')
                        
                        # Get vulnerabilities for this host
                        host_details = self.tenable.scans.host_details(scan_id, host_id)
                        vulns = host_details.get('vulnerabilities', [])
                        
                        for vuln in vulns:
                            # Filter by severity if specified
                            vuln_severity = vuln.get('severity', 0)
                            if severity is not None and vuln_severity != severity:
                                continue
                            
                            # Create unique ID
                            vuln_id = "{}_{}_{}_{}".format(
                                scan_id, host_id, 
                                vuln.get('plugin_id'), 
                                vuln.get('plugin_name', '').replace(' ', '_')
                            )
                            
                            # Skip if already processed
                            if self.checkpoint.is_processed(checkpoint_key, vuln_id):
                                continue
                            
                            # Prepare event data
                            event_data = {
                                'event_type': 'tenable_vulnerability',
                                'scan_id': scan_id,
                                'scan_name': scan.get('name'),
                                'host_id': host_id,
                                'hostname': host.get('hostname'),
                                'vulnerability': vuln
                            }
                            
                            if self.cribl.send_event(event_data, sourcetype='tenable:vulnerability'):
                                events_sent += 1
                                self.checkpoint.add_processed_id(checkpoint_key, vuln_id)
                
                except Exception as e:
                    self.logger.error("Error processing scan {}: {}".format(scan_id, e))
                    continue
            
            self.logger.info("Sent {} vulnerability events to Cribl".format(events_sent))
            return events_sent
            
        except Exception as e:
            self.logger.error("Error processing vulnerabilities: {}".format(e))
            return 0
    
    def process_plugins(self):
        """Process plugin information"""
        self.logger.info("Starting plugin collection")
        checkpoint_key = "plugins"
        
        try:
            # Get plugin families
            families_data = self.tenable.plugins.families()
            families = families_data.get('families', [])
            self.logger.info("Retrieved {} plugin families".format(len(families)))
            
            events_sent = 0
            for family in families:
                family_id = family.get('id')
                
                # Skip if already processed
                if self.checkpoint.is_processed(checkpoint_key, family_id):
                    continue
                
                event_data = dict(family)
                event_data['event_type'] = 'tenable_plugin_family'
                
                if self.cribl.send_event(event_data, sourcetype='tenable:plugin'):
                    events_sent += 1
                    self.checkpoint.add_processed_id(checkpoint_key, family_id)
            
            self.logger.info("Sent {} plugin events to Cribl".format(events_sent))
            return events_sent
            
        except Exception as e:
            self.logger.error("Error processing plugins: {}".format(e))
            return 0
    
    def process_scans(self):
        """Process scan summary data"""
        self.logger.info("Starting scan collection")
        checkpoint_key = "scans"
        last_timestamp = self.checkpoint.get_last_timestamp(checkpoint_key)
        
        self.logger.info("Processing scans (last checkpoint: {})".format(last_timestamp))
        
        try:
            scans = []
            for scan in self.tenable.scans.list():
                scan_dict = dict(scan)
                
                # Filter by last modification date if checkpoint exists
                if last_timestamp:
                    if scan_dict.get('last_modification_date', 0) <= last_timestamp:
                        continue
                
                scans.append(scan_dict)
            
            self.logger.info("Retrieved {} new scans from Tenable".format(len(scans)))
            
            if not scans:
                self.logger.info("No new scans to process")
                return 0
            
            max_timestamp = last_timestamp or 0
            events_sent = 0
            
            for scan in scans:
                scan_id = scan.get('id')
                scan_uuid = scan.get('uuid', str(scan_id))
                
                # Check if already processed
                if self.checkpoint.is_processed(checkpoint_key, scan_uuid):
                    continue
                
                # Get scan details
                try:
                    scan_details = self.tenable.scans.details(scan_id)
                    scan_details['event_type'] = 'tenable_scan'
                    
                    if self.cribl.send_event(scan_details, sourcetype='tenable:scan'):
                        events_sent += 1
                        self.logger.info("Sent scan {} to Cribl".format(scan_id))
                
                except Exception as e:
                    self.logger.error("Error getting scan details for {}: {}".format(scan_id, e))
                    continue
                
                # Mark as processed
                self.checkpoint.add_processed_id(checkpoint_key, scan_uuid)
                
                # Update max timestamp
                mod_date = scan.get('last_modification_date', 0)
                if mod_date > max_timestamp:
                    max_timestamp = mod_date
            
            # Update checkpoint timestamp
            if max_timestamp > (last_timestamp or 0):
                self.checkpoint.set_last_timestamp(checkpoint_key, max_timestamp)
            
            self.logger.info("Processed {} scans, sent {} events to Cribl".format(len(scans), events_sent))
            return events_sent
            
        except Exception as e:
            self.logger.error("Error processing scans: {}".format(e))
            return 0
    
    def run_once(self, data_types):
        """
        Run integration once for specified data types
        
        Args:
            data_types: List of data types to collect
        """
        self.logger.info("Starting Tenable to Cribl integration (one-time run)")
        self.logger.info("Data types: {}".format(', '.join(data_types)))
        
        total_events = 0
        
        try:
            if 'assets' in data_types or 'all' in data_types:
                total_events += self.process_assets()
            
            if 'vulnerabilities' in data_types or 'all' in data_types:
                total_events += self.process_vulnerabilities()
            
            if 'vulnerabilities_no_info' in data_types:
                # Vulnerabilities with severity 0 (informational)
                total_events += self.process_vulnerabilities(severity=0)
            
            if 'plugins' in data_types or 'all' in data_types:
                total_events += self.process_plugins()
            
            if 'scans' in data_types or 'all' in data_types:
                total_events += self.process_scans()
            
            self.logger.info("Integration completed - Total events sent: {}".format(total_events))
            
        except Exception as e:
            self.logger.error("Error during integration run: {}".format(e), exc_info=True)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Tenable to Cribl HEC Integration')
    parser.add_argument('--once', action='store_true', 
                       help='Run once and exit')
    parser.add_argument('--types', nargs='+', 
                       default=['all'],
                       choices=['all', 'assets', 'vulnerabilities', 'vulnerabilities_no_info', 
                               'plugins', 'scans'],
                       help='Data types to collect (default: all)')
    
    args = parser.parse_args()
    
    integration = TenableIntegration()
    
    if args.once:
        integration.run_once(args.types)
    else:
        print("Continuous mode not implemented. Use --once flag.")
        print("For scheduled runs, use cron or system scheduler.")


if __name__ == '__main__':
    main()
