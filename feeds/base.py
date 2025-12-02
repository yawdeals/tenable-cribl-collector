#!/usr/bin/env python3
# Base class for all Tenable feed processors
import logging
import time


class BaseFeedProcessor(object):
    # Base processor with checkpointing, batching, and deduplication

    def __init__(self, tenable_client, checkpoint_mgr, hec_handler, feed_name,
                 checkpoint_key, sourcetype, feed_type, batch_size=5000, max_events=0):
        # Initialize processor with all required components
        self.tenable = tenable_client  # Tenable API client
        self.checkpoint = checkpoint_mgr  # Checkpoint manager for deduplication
        self.hec = hec_handler  # HEC handler for sending events
        self.feed_name = feed_name  # Human-readable feed name
        self.checkpoint_key = checkpoint_key  # Unique key for this feed
        self.sourcetype = sourcetype  # HEC sourcetype
        self.feed_type = feed_type  # Feed classification (asset, vulnerability, etc.)
        self.batch_size = batch_size  # Events per batch (default 5000)
        self.max_events = max_events  # Max events to process (0 = unlimited)
        self.logger = logging.getLogger(__name__)
        self._event_buffer = []  # Buffer for batching events
        self._buffer_ids = []  # IDs of buffered events for checkpointing
        self._start_time = None  # Track processing time

    def log_start(self):
        self._start_time = time.time()
        self.logger.info("=" * 80)
        self.logger.info("Processing {0} feed...".format(self.feed_name))
        if self.max_events > 0:
            self.logger.info("Max events limit: {0}".format(self.max_events))
        self.logger.info("=" * 80)

    def log_progress(self, count, interval=1000):
        if count > 0 and count % interval == 0:
            elapsed = time.time() - self._start_time
            rate = count / elapsed if elapsed > 0 else 0
            self.logger.info("[{0}] {1:,} events processed ({2:.0f}/sec, {3:.1f}min elapsed)".format(
                self.feed_name, count, rate, elapsed / 60))

    def should_stop(self, count):
        if self.max_events > 0 and count >= self.max_events:
            self.logger.info("Reached max_events limit ({0}), stopping {1} feed".format(
                self.max_events, self.feed_name))
            return True
        return False

    def log_completion(self, count):
        elapsed = time.time() - self._start_time if self._start_time else 0
        rate = count / elapsed if elapsed > 0 else 0
        self.logger.info("Completed {0} feed: {1:,} events in {2:.1f}min ({3:.0f}/sec)".format(
            self.feed_name, count, elapsed / 60, rate))

    def send_event(self, event_data, item_id=None):
        # Buffer event for batch sending (auto-flushes when batch size reached)
        try:
            # Copy event data (feed_type/feed_name added as HEC fields during flush)
            classified_event = dict(event_data)

            # Add to buffer
            self._event_buffer.append(classified_event)
            if item_id:
                self._buffer_ids.append(item_id)  # Track ID for checkpointing

            # Auto-flush when batch size reached
            if len(self._event_buffer) >= self.batch_size:
                return self.flush_events()

            return True
        except Exception as e:
            self.logger.error(
                "Failed to buffer {0} event: {1}".format(
                    self.feed_name, str(e)))
            return False

    def flush_events(self):
        # Send all buffered events to HEC and update checkpoints
        if not self._event_buffer:
            return True

        try:
            batch_size = len(self._event_buffer)
            self.logger.info("Sending batch of {0} {1} events to HEC...".format(
                batch_size, self.feed_name))

            # Send batch with feed classification
            success_count = self.hec.send_batch(
                self._event_buffer, 
                sourcetype=self.sourcetype,
                feed_type=self.feed_type,
                feed_name=self.feed_name
            )

            if success_count == batch_size:
                # Mark all buffered IDs as processed to prevent duplicates
                for item_id in self._buffer_ids:
                    self.mark_processed(item_id)

                # Clear buffers
                self._event_buffer = []
                self._buffer_ids = []
                return True
            else:
                self.logger.warning("Only {0}/{1} events sent successfully".format(
                    success_count, batch_size))
                return False
        except Exception as e:
            self.logger.error(
                "Failed to flush {0} events: {1}".format(
                    self.feed_name, str(e)))
            return False

    def is_processed(self, item_id):
        # Check if item has already been processed (deduplication)
        return self.checkpoint.is_processed(self.checkpoint_key, item_id)

    def mark_processed(self, item_id):
        # Mark item as processed to prevent future duplicates
        self.checkpoint.add_processed_id(self.checkpoint_key, item_id)

    def get_last_timestamp(self):
        # Get last processed timestamp for incremental processing
        return self.checkpoint.get_last_timestamp(self.checkpoint_key)

    def set_last_timestamp(self, timestamp):
        # Update last processed timestamp
        self.checkpoint.set_last_timestamp(self.checkpoint_key, timestamp)

    def get_processed_ids(self):
        # Get all processed IDs (used for detecting deletions)
        return self.checkpoint.get_processed_ids(self.checkpoint_key)

    def process(self):
        raise NotImplementedError("Subclasses must implement process() method")
