#!/usr/bin/env python3
# Main Tenable to Cribl collector
from feeds.plugins import (PluginFeedProcessor, ComplianceFeedProcessor)
from feeds.vulnerabilities import (
    VulnerabilityFeedProcessor,
    VulnerabilityNoInfoProcessor,
    VulnerabilitySelfScanProcessor,
    FixedVulnerabilityProcessor)
from feeds.assets import (AssetFeedProcessor, AssetSelfScanProcessor,
                          DeletedAssetProcessor, TerminatedAssetProcessor)
from tenable_common import CriblHECHandler, setup_logging, validate_environment, CollectorMetrics
from checkpoint_manager import FileCheckpoint
from tenable.io import TenableIO
import os
import argparse
import logging
import time
import sys
import signal
import threading
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv

# Suppress urllib3 connection pool warnings for concurrent execution
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
# Suppress other threading-related warnings
warnings.filterwarnings('ignore', message='.*connection pool.*')
warnings.filterwarnings('ignore', category=ResourceWarning)


# Global shutdown event for graceful termination
_shutdown_event = threading.Event()


class TenableIntegration:
    # Main integration orchestrator for all Tenable feeds

    def __init__(self):
        # Load environment variables from .env file
        load_dotenv()

        # Validate required environment variables (fail fast)
        validate_environment()

        # Set up logging
        log_level = os.getenv('LOG_LEVEL', 'INFO')
        setup_logging(log_level, 'tenable_integration.log')
        self.logger = logging.getLogger(__name__)

        # Initialize metrics tracker
        self.metrics = CollectorMetrics()

        # Reference to global shutdown event
        self._shutdown_event = _shutdown_event

        # Initialize Tenable.io API client
        self.tenable = TenableIO(
            access_key=os.getenv('TENABLE_ACCESS_KEY'),
            secret_key=os.getenv('TENABLE_SECRET_KEY'),
            url=os.getenv('TENABLE_URL', 'https://cloud.tenable.com')
        )
        self.logger.info("Initialized Tenable.io client")

        # Initialize Cribl HEC handler with retry and pool settings
        # Get optional CA cert path - expand environment variables like
        # $CRIBL_HOME
        ca_cert_raw = os.getenv('CRIBL_HEC_CA_CERT', '').strip()
        if ca_cert_raw:
            # Expand environment variables in the path (e.g., $CRIBL_HOME)
            ca_cert_path = os.path.expandvars(ca_cert_raw)
            # Also expand ~ for home directory
            ca_cert_path = os.path.expanduser(ca_cert_path)
            self.logger.info("Using CA cert: {0}".format(ca_cert_path))
            if not os.path.exists(ca_cert_path):
                self.logger.error(
                    "CA cert file not found: {0} - check CRIBL_HEC_CA_CERT path".format(ca_cert_path))
                raise FileNotFoundError(
                    "CA cert file not found: {0}".format(ca_cert_path))
        else:
            ca_cert_path = None

        self.cribl = CriblHECHandler(
            host=os.getenv('CRIBL_HEC_HOST'),
            port=int(os.getenv('CRIBL_HEC_PORT', 8088)),
            token=os.getenv('CRIBL_HEC_TOKEN'),
            index='', sourcetype='', source='',
            ssl_verify=os.getenv(
                'CRIBL_HEC_SSL_VERIFY',
                'true').lower() == 'true',
            ssl_ca_cert=ca_cert_path,
            max_retries=int(os.getenv('HEC_MAX_RETRIES', 3)),
            backoff_factor=float(os.getenv('HEC_BACKOFF_FACTOR', 0.5)),
            pool_connections=int(os.getenv('HEC_POOL_CONNECTIONS', 10)),
            pool_maxsize=int(os.getenv('HEC_POOL_MAXSIZE', 10)),
            batch_delay=float(os.getenv('HEC_BATCH_DELAY', 0.01)),
            request_timeout=int(os.getenv('HEC_REQUEST_TIMEOUT', 30))
        )

        # Initialize checkpoint manager for deduplication
        self.checkpoint = FileCheckpoint(
            checkpoint_dir=os.getenv('CHECKPOINT_DIR', 'checkpoints'),
            key_prefix='tenable',
            max_ids=int(os.getenv('CHECKPOINT_MAX_IDS', 500000)),
            retention_days=int(os.getenv('CHECKPOINT_RETENTION_DAYS', 7))
        )
        self.logger.info("Initialized file-based checkpointing")

        # Configure batch size for HEC sends (larger = faster throughput)
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

        # Configure concurrent workers
        self.max_workers = int(os.getenv('MAX_CONCURRENT_FEEDS', 1))

        # Fully sequential mode - ALL feeds run one at a time (disabled by
        # default)
        self.fully_sequential = os.getenv(
            'FULLY_SEQUENTIAL', 'false').lower() == 'true'

        # Smart feed grouping - runs feeds by API type to avoid 429 errors (ENABLED by default)
        # This is the RECOMMENDED mode: groups run in parallel, feeds within
        # groups run sequentially
        self.smart_grouping = os.getenv(
            'SMART_FEED_GROUPING', 'true').lower() == 'true'

        # Delay between feeds in same group (gives Tenable time to release export locks)
        # Tenable exports can take time to fully complete on their side even after data is received
        # This delay PREVENTS 429 errors by waiting before starting the next
        # export
        self.inter_feed_delay = float(os.getenv('INTER_FEED_DELAY', 60))

        if self.fully_sequential:
            self.logger.info(
                "Execution mode: FULLY SEQUENTIAL (safest, {0}s delay between feeds)".format(
                    self.inter_feed_delay))
        elif self.smart_grouping:
            self.logger.info(
                "Execution mode: SMART GROUPING (parallel groups, sequential within)")
        elif self.max_workers > 1:
            self.logger.info(
                "Execution mode: CONCURRENT ({0} workers)".format(
                    self.max_workers))
        else:
            self.logger.info("Execution mode: SEQUENTIAL (1 feed at a time)")

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
        # Process a single feed (thread-safe for concurrent execution)
        # Check for shutdown before processing
        if self._shutdown_event.is_set():
            self.logger.warning(
                "Shutdown requested, skipping feed: {0}".format(feed_name))
            return 0

        try:
            start_time = time.time()
            processor = self._get_processor(feed_name)
            event_count = processor.process()

            # Track metrics
            elapsed = time.time() - start_time
            self.metrics.record_feed(feed_name, event_count, elapsed)

            # Flush checkpoint after processing
            self.checkpoint.flush_all()
            return event_count
        except Exception as e:
            self.metrics.record_error(feed_name, str(e))
            self.logger.error(
                "Error processing feed {0}: {1}".format(
                    feed_name, str(e)), exc_info=True)
            return 0

    def _process_group_sequentially(self, group_name, group_feeds):
        # Process all feeds in a group sequentially (one at a time)
        # This is used when smart grouping is enabled
        # CRITICAL: Tenable only allows 1 export per type at a time
        # The inter-feed delay PREVENTS 429 errors by waiting for exports to fully complete
        # Returns (total_events, feed_results_dict)
        self.logger.info(
            "[{0}] Starting group with {1} feeds (sequential, {2}s delay between)".format(
                group_name, len(group_feeds), self.inter_feed_delay))

        total_events = 0
        feed_results = {}

        for idx, feed_name in enumerate(group_feeds):
            if self._shutdown_event.is_set():
                self.logger.warning(
                    "[{0}] Shutdown requested, stopping group".format(group_name))
                break

            self.logger.info("[{0}] Processing feed {1}/{2}: {3}".format(
                group_name, idx + 1, len(group_feeds), feed_name))
            event_count = self._process_feed(feed_name)
            total_events += event_count
            feed_results[feed_name] = event_count
            self.logger.info(
                "[{0}] {1}: {2} events".format(
                    group_name, feed_name, event_count))

            # CRITICAL: Wait between feeds in the same group to prevent 429 errors
            # Tenable needs time to fully release the export lock on their side
            if idx < len(group_feeds) - 1 and self.inter_feed_delay > 0:
                self.logger.info(
                    "[{0}] Waiting {1}s for Tenable export lock to release...".format(
                        group_name, self.inter_feed_delay))
                time.sleep(self.inter_feed_delay)

        self.logger.info(
            "[{0}] Group complete: {1} total events from {2} feeds".format(
                group_name, total_events, len(feed_results)))
        return total_events, feed_results

    def run_once(self, data_types):
        # Run collection once for specified feed types
        # Smart grouping: groups run in PARALLEL, feeds within groups run SEQUENTIALLY
        # This prevents Tenable 429 errors (only 1 export per type allowed)
        try:
            # Reset metrics for this run
            self.metrics.reset()
            run_start = time.time()

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

            # Define feed groups by Tenable API type
            # Tenable only allows 1 export per type at a time
            # So feeds within a group must run sequentially
            # But different groups CAN run in parallel (up to 3 streams)
            feed_groups = {
                'assets': [  # Asset export API - 1 at a time
                    'tenableio_asset',
                    'tenableio_asset_self_scan',
                    'tenableio_deleted_asset',
                    'tenableio_terminated_asset',
                ],
                'vulnerabilities': [  # Vuln export API - 1 at a time
                    'tenableio_vulnerability',
                    'tenableio_vulnerability_no_info',
                    'tenableio_vulnerability_self_scan',
                    'tenableio_fixed_vulnerability',
                ],
                'plugins': [  # REST API - can run with exports
                    'tenableio_plugin',
                    'tenableio_compliance',
                ],
            }

            # All available feed types (flattened)
            all_feeds = []
            for group_feeds in feed_groups.values():
                all_feeds.extend(group_feeds)

            # Determine which feeds to process
            feeds_to_process = all_feeds if 'all' in data_types else [
                f for f in data_types if f in all_feeds]
            total_events = 0
            feed_results = {}

            # Build groups to run
            groups_to_run = []
            for group_name, group_feeds in feed_groups.items():
                feeds_in_group = [
                    f for f in group_feeds if f in feeds_to_process]
                if feeds_in_group:
                    groups_to_run.append((group_name, feeds_in_group))

            if self.fully_sequential:
                # FULLY SEQUENTIAL MODE: Run ALL feeds one at a time with delay
                self.logger.info(
                    "FULLY SEQUENTIAL MODE: {0} feeds, {1}s delay between feeds".format(
                        len(feeds_to_process), self.inter_feed_delay))

                for idx, feed_name in enumerate(feeds_to_process):
                    if self._shutdown_event.is_set():
                        self.logger.warning("Shutdown requested, stopping")
                        break

                    self.logger.info("Processing feed {0}/{1}: {2}".format(
                        idx + 1, len(feeds_to_process), feed_name))
                    event_count = self._process_feed(feed_name)
                    total_events += event_count
                    feed_results[feed_name] = event_count
                    self.logger.info(
                        "  {0}: {1} events".format(
                            feed_name, event_count))

                    # Delay between feeds (except after last feed)
                    if idx < len(feeds_to_process) - \
                            1 and self.inter_feed_delay > 0:
                        self.logger.info(
                            "  Waiting {0}s before next feed...".format(
                                self.inter_feed_delay))
                        time.sleep(self.inter_feed_delay)

            elif self.smart_grouping and len(groups_to_run) > 1:
                # SMART MODE: Run groups in parallel, feeds within groups
                # sequentially
                self.logger.info(
                    "SMART GROUPING: {0} groups running in PARALLEL".format(
                        len(groups_to_run)))
                for group_name, group_feeds in groups_to_run:
                    self.logger.info(
                        "  {0}: {1} feeds (sequential within)".format(
                            group_name, len(group_feeds)))

                # Run all groups in parallel
                with ThreadPoolExecutor(max_workers=len(groups_to_run)) as executor:
                    future_to_group = {}
                    for group_name, group_feeds in groups_to_run:
                        future = executor.submit(
                            self._process_group_sequentially,
                            group_name, group_feeds)
                        future_to_group[future] = group_name

                    for future in as_completed(future_to_group):
                        group_name = future_to_group[future]
                        try:
                            group_events, group_results = future.result()
                            total_events += group_events
                            feed_results.update(group_results)
                            self.logger.info(
                                "Group {0} complete: {1} total events".format(
                                    group_name, group_events))
                        except Exception as e:
                            self.logger.error(
                                "Group {0} FAILED: {1}".format(
                                    group_name, str(e)))
            else:
                # SEQUENTIAL MODE: Run all feeds one at a time (no delay)
                self.logger.info(
                    "SEQUENTIAL MODE: {0} feeds running one at a time".format(
                        len(feeds_to_process)))

                for feed_name in feeds_to_process:
                    if self._shutdown_event.is_set():
                        self.logger.warning("Shutdown requested, stopping")
                        break

                    event_count = self._process_feed(feed_name)
                    total_events += event_count
                    feed_results[feed_name] = event_count
                    self.logger.info(
                        "  {0}: {1} events".format(
                            feed_name, event_count))

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

            # Log HEC adaptive rate status
            try:
                hec_status = self.cribl.hec_handler.get_throughput_status()
                self.logger.info("HEC Throughput: {0}".format(hec_status))
            except Exception:
                pass  # Ignore if method not available

            # Log metrics summary
            run_elapsed = time.time() - run_start
            self.metrics.log_summary(self.logger, run_elapsed)
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

    def run_daemon(self, data_types, interval=3600):
        self.logger.info(
            "Starting daemon mode (interval: {0}s)...".format(interval))
        while not self._shutdown_event.is_set():
            try:
                self.run_once(data_types)
                self.logger.info(
                    "Sleeping for {0} seconds (Ctrl+C to stop)...".format(interval))
                # Use event wait instead of sleep for responsive shutdown
                if self._shutdown_event.wait(timeout=interval):
                    self.logger.info("Shutdown event received during sleep")
                    break
            except Exception as e:
                self.logger.error(
                    "Error in daemon loop: {0}".format(
                        str(e)), exc_info=True)
                self.logger.info(
                    "Waiting {0} seconds before retry...".format(interval))
                if self._shutdown_event.wait(timeout=interval):
                    break

        self.logger.info("Daemon mode exiting, performing cleanup...")
        self._graceful_shutdown()

    def _graceful_shutdown(self):
        """Perform graceful shutdown: flush checkpoints and log final metrics."""
        self.logger.info("Initiating graceful shutdown...")
        try:
            # Flush all pending checkpoints
            self.checkpoint.flush_all()
            self.logger.info("Checkpoints flushed successfully")
        except Exception as e:
            self.logger.error("Error flushing checkpoints: {0}".format(e))

        try:
            # Flush any pending HEC events
            self.cribl.flush()
            self.logger.info("HEC buffer flushed successfully")
        except Exception as e:
            self.logger.error("Error flushing HEC buffer: {0}".format(e))

        # Log final metrics
        self.metrics.log_summary(self.logger, 0)
        self.logger.info("Graceful shutdown complete")


def _signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    sig_name = signal.Signals(signum).name
    logging.getLogger(__name__).info(
        "Received signal {0}, initiating graceful shutdown...".format(sig_name))
    _shutdown_event.set()


def main():
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)

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
