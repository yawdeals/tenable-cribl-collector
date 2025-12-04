#!/usr/bin/env python3
# Asset feed processors with retry logic and unique export filters for
# concurrent execution
import time
import logging
from feeds.base import BaseFeedProcessor


def _safe_export_with_retry(
        export_func,
        feed_name,
        max_retries=3,
        initial_wait=60):
    # Retry wrapper for Tenable exports with exponential backoff for 429 errors
    logger = logging.getLogger(__name__)
    wait_time = initial_wait

    for attempt in range(max_retries + 1):
        try:
            logger.info("Starting {0} export (attempt {1}/{2})...".format(
                feed_name, attempt + 1, max_retries + 1))

            export_started = False
            for item in export_func():
                export_started = True  # Track if export started successfully
                yield item

            # Export completed successfully
            return

        except Exception as e:
            error_msg = str(e).lower()

            # Only retry if export hasn't started (prevents duplicate items)
            if not export_started:
                # Check for 429 rate limit or duplicate export error
                if '429' in error_msg or 'duplicate export' in error_msg or 'export already running' in error_msg:
                    if attempt < max_retries:
                        logger.warning(
                            "Export already running or rate limited (429). "
                            "Waiting {0} seconds for existing export to complete... "
                            "(Attempt {1}/{2})".format(wait_time, attempt + 1, max_retries + 1))
                        logger.info(
                            "TIP: If you cancelled a previous run, Tenable's export may still be processing. "
                            "This can take 10-30 minutes to complete on Tenable's side.")

                        time.sleep(wait_time)
                        # Exponential backoff (max 5 min)
                        wait_time = min(wait_time * 1.5, 300)
                        continue
                    else:
                        logger.error(
                            "Max retries exceeded. An export is still running on Tenable's side. "
                            "Please wait 30-60 minutes and try again, or contact Tenable support.")
                        raise

            # For other errors or if export already started, raise immediately
            logger.error("Export error for {0}: {1}".format(feed_name, str(e)))
            raise


class AssetFeedProcessor(BaseFeedProcessor):

    def __init__(self, tenable_client, checkpoint_mgr,
                 hec_handler, batch_size=5000, max_events=0):
        super(
            AssetFeedProcessor,
            self).__init__(
            tenable_client,
            checkpoint_mgr,
            hec_handler,
            "Asset Inventory",
            "tenableio_asset",
            "tenable:io:asset",
            "asset",
            batch_size,
            max_events)

    def process(self):
        self.log_start()
        event_count = 0

        try:
            self.logger.info("Initiating asset export from Tenable.io...")
            self.logger.info(
                "(This may take several minutes for large environments)")

            # Use is_deleted=False to differentiate from deleted asset export
            for asset in _safe_export_with_retry(
                lambda: self.tenable.exports.assets(is_deleted=False),
                "Asset Inventory"
            ):
                asset_id = asset.get('id')
                if self.is_processed(asset_id):
                    continue

                if self.send_event(asset, item_id=asset_id):
                    event_count += 1
                    self.log_progress(event_count)

                # Check if we've hit the limit
                if self.should_stop(event_count):
                    break

            # Flush any remaining events
            self.flush_events()

            self.log_completion(event_count)
        except Exception as e:
            self.logger.error(
                "Error processing asset feed: {0}".format(
                    str(e)))

        return event_count


class AssetSelfScanProcessor(BaseFeedProcessor):

    def __init__(self, tenable_client, checkpoint_mgr,
                 hec_handler, batch_size=5000, max_events=0):
        super(
            AssetSelfScanProcessor,
            self).__init__(
            tenable_client,
            checkpoint_mgr,
            hec_handler,
            "Agent-Based Assets",
            "tenableio_asset_self_scan",
            "tenable:io:asset:self_scan",
            "asset_self_scan",
            batch_size,
            max_events)

    def process(self):
        self.log_start()
        event_count = 0

        try:
            self.logger.info("Initiating agent-based asset export...")
            # Note: Tenable API doesn't have has_agent filter, so we use sources filter
            # to differentiate this export from others (agents typically show
            # as 'NESSUS_AGENT')
            for asset in _safe_export_with_retry(
                lambda: self.tenable.exports.assets(sources=['NESSUS_AGENT']),
                "Agent-Based Assets"
            ):
                # Double-check has_agent flag (some agents may have different
                # sources)
                if not asset.get('has_agent', False):
                    continue

                asset_id = asset.get('id')
                if self.is_processed(asset_id):
                    continue

                if self.send_event(asset, item_id=asset_id):
                    event_count += 1
                    self.log_progress(event_count)

                if self.should_stop(event_count):
                    break

            self.flush_events()
            self.log_completion(event_count)
        except Exception as e:
            self.logger.error(
                "Error processing agent-based asset feed: {0}".format(str(e)))

        return event_count


class DeletedAssetProcessor(BaseFeedProcessor):

    def __init__(self, tenable_client, checkpoint_mgr,
                 hec_handler, batch_size=5000, max_events=0):
        super(
            DeletedAssetProcessor,
            self).__init__(
            tenable_client,
            checkpoint_mgr,
            hec_handler,
            "Deleted Assets",
            "tenableio_deleted_asset",
            "tenable:io:asset:deleted",
            "deleted_asset",
            batch_size,
            max_events)

        # Configure scan interval (default: only scan once per 24 hours)
        import os
        self.scan_interval_hours = int(
            os.getenv('DELETED_ASSET_SCAN_INTERVAL_HOURS', 24))

    def _should_run_full_scan(self):
        # Check if enough time has passed since last full scan
        # Load checkpoint first to ensure cache is populated
        self.checkpoint._load_checkpoint('deleted_asset')
        checkpoint_data = self.checkpoint._cache.get('deleted_asset', {})
        last_scan = checkpoint_data.get('last_full_scan', 0)
        current_time = int(time.time())
        time_since_scan = current_time - last_scan
        hours_since_scan = time_since_scan / 3600

        if hours_since_scan < self.scan_interval_hours:
            self.logger.info(
                "Skipping deleted asset scan - last scan was {0:.1f} hours ago (interval: {1} hours)".format(
                    hours_since_scan, self.scan_interval_hours))
            return False

        return True

    def process(self):
        self.log_start()
        event_count = 0

        try:
            # Check if we should run the expensive full scan
            if not self._should_run_full_scan():
                self.logger.info(
                    "Deleted asset detection skipped (run too recently)")
                return 0

            previous_assets = self.get_processed_ids()
            self.logger.info(
                "Found {0} assets in previous checkpoint".format(
                    len(previous_assets)))

            if not previous_assets:
                self.logger.info(
                    "No previous assets to compare - building baseline only")

            current_assets = set()
            self.logger.info("Fetching current assets from Tenable...")
            self.logger.info(
                "(This may take 1-2 hours for large environments - runs max once per {0} hours)".format(
                    self.scan_interval_hours))

            asset_count = 0
            start_time = time.time()
            # Use has_plugin_results=True to differentiate from other asset exports
            # and focus on assets that have actually been scanned
            for asset in _safe_export_with_retry(
                lambda: self.tenable.exports.assets(has_plugin_results=True),
                "Deleted Assets"
            ):
                current_assets.add(asset.get('id'))
                asset_count += 1

                # Log progress every 1000 assets with time estimate
                if asset_count % 1000 == 0:
                    elapsed = time.time() - start_time
                    rate = asset_count / elapsed if elapsed > 0 else 0
                    self.logger.info("Fetched {0} assets... ({1:.0f} assets/sec)".format(
                        asset_count, rate))

            elapsed_total = time.time() - start_time
            self.logger.info(
                "Found {0} current assets in {1:.1f} minutes".format(
                    len(current_assets), elapsed_total / 60))

            deleted_assets = previous_assets - current_assets

            if deleted_assets:
                self.logger.info(
                    "Detected {0} deleted assets".format(
                        len(deleted_assets)))
                for asset_id in deleted_assets:
                    deletion_event = {
                        'asset_id': asset_id,
                        'event_type': 'asset_deleted',
                        'detected_at': int(time.time())
                    }
                    if self.send_event(deletion_event):
                        event_count += 1
                        self.log_progress(event_count)
            else:
                self.logger.info("No deleted assets detected")

            # Update checkpoint with current assets
            for asset_id in current_assets:
                self.mark_processed(asset_id)

            # Record the scan time in checkpoint
            try:
                self.checkpoint._load_checkpoint('deleted_asset')
                checkpoint_data = self.checkpoint._cache.get(
                    'deleted_asset', {})
                checkpoint_data['last_full_scan'] = int(time.time())
                self.checkpoint._cache['deleted_asset'] = checkpoint_data
                self.checkpoint._dirty_keys.add('deleted_asset')
            except Exception as checkpoint_err:
                self.logger.warning(
                    "Failed to update scan timestamp: {0}".format(
                        str(checkpoint_err)))

            self.flush_events()

            self.log_completion(event_count)
        except Exception as e:
            self.logger.error(
                "Error processing deleted asset feed: {0}".format(
                    str(e)))

        return event_count


class TerminatedAssetProcessor(BaseFeedProcessor):

    def __init__(self, tenable_client, checkpoint_mgr,
                 hec_handler, batch_size=5000, max_events=0):
        super(
            TerminatedAssetProcessor,
            self).__init__(
            tenable_client,
            checkpoint_mgr,
            hec_handler,
            "Terminated Assets",
            "tenableio_terminated_asset",
            "tenable:io:asset:terminated",
            "terminated_asset",
            batch_size,
            max_events)

    def process(self):
        self.log_start()
        event_count = 0

        try:
            self.logger.info("Initiating terminated asset export...")
            # Use is_terminated=True filter to get only terminated assets
            # This makes the export unique and returns only relevant data
            for asset in _safe_export_with_retry(
                lambda: self.tenable.exports.assets(is_terminated=True),
                "Terminated Assets"
            ):
                if 'terminated_at' not in asset or asset.get(
                        'terminated_at') is None:
                    continue

                asset_id = asset.get('id')
                if self.is_processed(asset_id):
                    continue

                if self.send_event(asset, item_id=asset_id):
                    event_count += 1
                    self.log_progress(event_count)

                if self.should_stop(event_count):
                    break

            self.flush_events()

            self.log_completion(event_count)
        except Exception as e:
            self.logger.error(
                "Error processing terminated asset feed: {0}".format(
                    str(e)))

        return event_count
