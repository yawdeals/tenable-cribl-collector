#!/usr/bin/env python3
import logging


class BaseFeedProcessor(object):
    
    def __init__(self, tenable_client, checkpoint_mgr, hec_handler, feed_name, checkpoint_key, sourcetype, batch_size=5000):
        self.tenable = tenable_client
        self.checkpoint = checkpoint_mgr
        self.hec = hec_handler
        self.feed_name = feed_name
        self.checkpoint_key = checkpoint_key
        self.sourcetype = sourcetype
        self.batch_size = batch_size
        self.logger = logging.getLogger(__name__)
        self._event_buffer = []
        self._buffer_ids = []
    
    def log_start(self):
        self.logger.info("=" * 80)
        self.logger.info("Processing {0} feed...".format(self.feed_name))
        self.logger.info("=" * 80)
    
    def log_progress(self, count, interval=100):
        if count > 0 and count % interval == 0:
            self.logger.info("Processed {0} {1} events so far...".format(count, self.feed_name))
    
    def log_completion(self, count):
        self.logger.info("Completed {0} feed: {1} events processed".format(self.feed_name, count))
    
    def send_event(self, event_data, item_id=None):
        """
        Buffer event for batch sending
        
        Args:
            event_data: Event data dictionary
            item_id: Optional item ID for checkpoint tracking
            
        Returns:
            True if buffered successfully
        """
        try:
            self._event_buffer.append(event_data)
            if item_id:
                self._buffer_ids.append(item_id)
            
            # Auto-flush when batch size reached
            if len(self._event_buffer) >= self.batch_size:
                return self.flush_events()
            
            return True
        except Exception as e:
            self.logger.error("Failed to buffer {0} event: {1}".format(self.feed_name, str(e)))
            return False
    
    def flush_events(self):
        """
        Flush buffered events to HEC
        
        Returns:
            True if successful
        """
        if not self._event_buffer:
            return True
        
        try:
            batch_size = len(self._event_buffer)
            self.logger.info("Sending batch of {0} {1} events to HEC...".format(
                batch_size, self.feed_name))
            
            success_count = self.hec.send_batch(self._event_buffer, sourcetype=self.sourcetype)
            
            if success_count == batch_size:
                # Mark all buffered IDs as processed on successful send
                for item_id in self._buffer_ids:
                    self.mark_processed(item_id)
                
                self._event_buffer = []
                self._buffer_ids = []
                return True
            else:
                self.logger.warning("Only {0}/{1} events sent successfully".format(
                    success_count, batch_size))
                return False
        except Exception as e:
            self.logger.error("Failed to flush {0} events: {1}".format(self.feed_name, str(e)))
            return False
    
    def is_processed(self, item_id):
        return self.checkpoint.is_processed(self.checkpoint_key, item_id)
    
    def mark_processed(self, item_id):
        self.checkpoint.add_processed_id(self.checkpoint_key, item_id)
    
    def get_last_timestamp(self):
        return self.checkpoint.get_last_timestamp(self.checkpoint_key)
    
    def set_last_timestamp(self, timestamp):
        self.checkpoint.set_last_timestamp(self.checkpoint_key, timestamp)
    
    def get_processed_ids(self):
        return self.checkpoint.get_processed_ids(self.checkpoint_key)
    
    def process(self):
        raise NotImplementedError("Subclasses must implement process() method")
