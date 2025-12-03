#!/usr/bin/env python3
# Main Tenable to Cribl collector
import os
import argparse
import logging
import time
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
from tenable.io import TenableIO
from checkpoint_manager import FileCheckpoint
from process_lock import ProcessLock
from tenable_common import CriblHECHandler, setup_logging
from feeds.assets import (AssetFeedProcessor, AssetSelfScanProcessor,
                          DeletedAssetProcessor, TerminatedAssetProcessor)
from feeds.vulnerabilities import (
    VulnerabilityFeedProcessor,
    VulnerabilityNoInfoProcessor,
    VulnerabilitySelfScanProcessor,
    FixedVulnerabilityProcessor)
from feeds.plugins import (PluginFeedProcessor, ComplianceFeedProcessor)


class TenableIntegration:
    # Main integration orchestrator for all Tenable feeds

    def __init__(self):
        # Load environment variables from .env file
        load_dotenv()

        # Set up logging
        log_level = os.getenv('LOG_LEVEL', 'INFO')
        setup_logging(log_level, 'tenable_integration.log')
        self.logger = logging.getLogger(__name__)

        # Initialize Tenable.io API client
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
            index='', sourcetype='', source='',
            ssl_verify=os.getenv(
                'CRIBL_HEC_SSL_VERIFY',
                'true').lower() == 'true'
        )

        # Initialize checkpoint manager for deduplication
        self.checkpoint = FileCheckpoint(
            checkpoint_dir=os.getenv('CHECKPOINT_DIR', 'checkpoints'),
            key_prefix='tenable',
            max_ids=int(os.getenv('CHECKPOINT_MAX_IDS', 100000)),
            retention_days=int(os.getenv('CHECKPOINT_RETENTION_DAYS', 30))
        )
        self.logger.info("Initialized file-based checkpointing")

        # Configure batch size for HEC sends
        self.batch_size = int(os.getenv('HEC_BATCH_SIZE', 5000))
        self.logger.info(
            "Batch size configured: {0} events".format(
                self.batch_size))

        # Configure max events per feed (0 = unlimited)
        self.max_events = int(os.getenv('MAX_EVENTS_PER_FEED', 0))
        if self.max_events > 0:
            self.logger.info(
                "Max events per feed: {0}".format(
                    self.max_events))
        else:
            self.logger.info("Max events per feed: unlimited")

        # Configure concurrent workers (0 = sequential, 1+ = parallel)
        self.max_workers = int(os.getenv('MAX_CONCURRENT_FEEDS', 0))
        if self.max_workers > 0:
            self.logger.info(
                "Concurrent execution enabled: {0} workers".format(
                    self.max_workers))
        else:
            self.logger.info("Sequential execution (default)")

        # Cache for feed processors (lazy initialization)
        self._feed_processors = {}

    def _get_processor(self, feed_name):
        if feed_name in self._feed_processors:
            return self._feed_processors[feed_name]

        processor_map = {
            'tenableio_asset': AssetFeedProcessor,
            'tenableio_asset_self_scan': AssetSelfScanProcessor,
            'tenableio_deleted_asset': DeletedAssetProcessor,
            'tenableio_terminated_asset': TerminatedAssetProcessor,
            'tenableio_vulnerability': VulnerabilityFeedProcessor,
            'tenableio_vulnerability_no_info': VulnerabilityNoInfoProcessor,
            'tenableio_vulnerability_self_scan': VulnerabilitySelfScanProcessor,
            'tenableio_fixed_vulnerability': FixedVulnerabilityProcessor,
            'tenableio_plugin': PluginFeedProcessor,
            'tenableio_compliance': ComplianceFeedProcessor}

        processor_class = processor_map.get(feed_name)
        if not processor_class:
            raise ValueError("Unknown feed type: {0}".format(feed_name))

        processor = processor_class(
            self.tenable,
            self.checkpoint,
            self.cribl,
            self.batch_size,
            self.max_events)
        self._feed_processors[feed_name] = processor
        return processor

    def _process_feed(self, feed_name):
        """Process a single feed (thread-safe for concurrent execution)"""
        try:
            processor = self._get_processor(feed_name)
            event_count = processor.process()
            # Flush checkpoint after processing
            self.checkpoint.flush_all()
            return event_count
        except Exception as e:
            self.logger.error(
                "Error processing feed {0}: {1}".format(
                    feed_name, str(e)), exc_info=True)
            return 0

    def run_once(self, data_types):
        # Run collection once for specified feed types
        # Acquire process lock to prevent overlapping runs
        lock = ProcessLock(
            lock_file='tenable_collector.lock',
            lock_dir=os.getenv('LOCK_DIR', 'locks'),
            timeout=int(os.getenv('LOCK_TIMEOUT', 600))
        )

        if not lock.acquire():
            self.logger.error("Another instance is already running. Exiting.")
            return

        try:
            self.logger.info("=" * 80)
            self.logger.info("STARTING TENABLE TO CRIBL INTEGRATION")
            self.logger.info("=" * 80)
            self.logger.info(
                "Selected feeds: {0}".format(
                    ', '.join(data_types)))
            self.logger.info("Batch size: {0} events".format(self.batch_size))
            self.logger.info(
                "Timestamp: {0}".format(
                    time.strftime('%Y-%m-%d %H:%M:%S')))
            self.logger.info("=" * 80)

            # All available feed types
            all_feeds = [
                'tenableio_asset',
                'tenableio_asset_self_scan',
                'tenableio_compliance',
                'tenableio_deleted_asset',
                'tenableio_fixed_vulnerability',
                'tenableio_plugin',
                'tenableio_terminated_asset',
                'tenableio_vulnerability',
                'tenableio_vulnerability_no_info',
                'tenableio_vulnerability_self_scan']

            # Determine which feeds to process
            feeds_to_process = all_feeds if 'all' in data_types else [
                f for f in data_types if f in all_feeds]
            total_events = 0
            feed_results = {}

            # Process feeds (sequential or concurrent based on max_workers)
            if self.max_workers > 0:
                # Concurrent execution with ThreadPoolExecutor
                self.logger.info(
                    "Processing {0} feeds concurrently with {1} workers".format(
                        len(feeds_to_process), self.max_workers))
                
                with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                    # Submit all feed processing jobs
                    future_to_feed = {
                        executor.submit(self._process_feed, feed_name): feed_name
                        for feed_name in feeds_to_process
                    }
                    
                    # Collect results as they complete
                    for future in as_completed(future_to_feed):
                        feed_name = future_to_feed[future]
                        try:
                            event_count = future.result()
                            total_events += event_count
                            feed_results[feed_name] = event_count
                            self.logger.info(
                                "Feed {0} completed: {1} events".format(
                                    feed_name, event_count))
                        except Exception as e:
                            self.logger.error(
                                "Failed to process feed {0}: {1}".format(
                                    feed_name, str(e)), exc_info=True)
                            feed_results[feed_name] = 0
            else:
                # Sequential execution (default)
                self.logger.info(
                    "Processing {0} feeds sequentially".format(
                        len(feeds_to_process)))
                
                for feed_name in feeds_to_process:
                    try:
                        # Get or create processor for this feed
                        processor = self._get_processor(feed_name)
                        event_count = processor.process()
                        total_events += event_count
                        feed_results[feed_name] = event_count
                        # Flush checkpoint after each feed to prevent duplicates on
                        # crash
                        self.checkpoint.flush_all()
                    except Exception as e:
                        self.logger.error(
                            "Failed to process feed {0}: {1}".format(
                                feed_name, str(e)), exc_info=True)
                        feed_results[feed_name] = 0

            self.logger.info("=" * 80)
            self.logger.info("INTEGRATION COMPLETED SUCCESSFULLY")
            self.logger.info("=" * 80)
            self.logger.info("Feed Collection Summary:")
            for feed_name in feeds_to_process:
                event_count = feed_results.get(feed_name, 0)
                self.logger.info(
                    "  {0}: {1} events".format(
                        feed_name, event_count))
            self.logger.info("-" * 80)
            self.logger.info(
                "Total events sent to Cribl: {0}".format(total_events))
            self.logger.info("=" * 80)

            # CRITICAL: Flush all checkpoints to disk to prevent duplicates
            self.logger.info("Flushing checkpoints to disk...")
            self.checkpoint.flush_all()
            self.logger.info("Checkpoints saved successfully")
        except Exception as e:
            self.logger.error(
                "ERROR during integration run: {0}".format(
                    str(e)), exc_info=True)
            raise
        finally:
            # Always try to flush checkpoints, even on error
            try:
                self.checkpoint.flush_all()
            except Exception:
                pass
            lock.release()

    def run_daemon(self, data_types, interval=3600):
        self.logger.info(
            "Starting daemon mode (interval: {0}s)...".format(interval))
        while True:
            try:
                self.run_once(data_types)
                self.logger.info(
                    "Sleeping for {0} seconds...".format(interval))
                time.sleep(interval)
            except KeyboardInterrupt:
                self.logger.info("Received shutdown signal, exiting...")
                break
            except Exception as e:
                self.logger.error(
                    "Error in daemon loop: {0}".format(
                        str(e)), exc_info=True)
                self.logger.info(
                    "Waiting {0} seconds before retry...".format(interval))
                time.sleep(interval)


def main():
    parser = argparse.ArgumentParser(
        description='Tenable to Cribl Collector',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Feed Types:
  tenableio_asset                   Asset inventory
  tenableio_asset_self_scan         Agent-based assets
  tenableio_compliance              Compliance findings
  tenableio_deleted_asset           Deleted assets
  tenableio_fixed_vulnerability     Fixed vulnerabilities
  tenableio_plugin                  Plugin metadata
  tenableio_terminated_asset        Terminated assets
  tenableio_vulnerability           Active vulnerabilities
  tenableio_vulnerability_no_info   Info-level vulnerabilities
  tenableio_vulnerability_self_scan Agent-based vulnerabilities
  all                               All feeds

Examples:
  python tenable_collector.py --feed all
  python tenable_collector.py --feed tenableio_asset tenableio_vulnerability
  python tenable_collector.py --feed all --daemon --interval 3600
        """
    )

    parser.add_argument(
        '--feed',
        nargs='+',
        default=['all'],
        dest='types',
        choices=[
            'all',
            'tenableio_asset',
            'tenableio_asset_self_scan',
            'tenableio_compliance',
            'tenableio_deleted_asset',
            'tenableio_fixed_vulnerability',
            'tenableio_plugin',
            'tenableio_terminated_asset',
            'tenableio_vulnerability',
            'tenableio_vulnerability_no_info',
            'tenableio_vulnerability_self_scan'],
        help='Feed types to collect (default: all)')

    parser.add_argument('--daemon', action='store_true',
                        help='Run in daemon mode (continuous collection)')

    parser.add_argument(
        '--interval',
        type=int,
        default=3600,
        help='Seconds between runs in daemon mode (default: 3600)')

    args = parser.parse_args()
    integration = TenableIntegration()

    if args.daemon:
        integration.run_daemon(args.types, args.interval)
    else:
        integration.run_once(args.types)


if __name__ == '__main__':
    main()
