#!/usr/bin/env python
# Tenable to Cribl HEC integration - Common utilities
import os
import sys
import logging
import http_event_collector as hec


class CriblHECHandler:
    # Handles sending events to Cribl via HTTP Event Collector

    def __init__(self, host, port, token, index,
                 sourcetype, source, ssl_verify=True):
        # Initialize HEC client with connection parameters
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
        logging.info("Initialized Cribl HEC: {0}:{1}".format(host, port))

    def send_event(self, event_data, timestamp=None,
                   sourcetype=None, source=None):
        # Send a single event to Cribl HEC
        try:
            # Build HEC payload with event data and metadata
            payload = {}
            payload['event'] = event_data
            payload['sourcetype'] = sourcetype or self.sourcetype
            payload['source'] = source or self.source
            payload['index'] = self.index

            # Add timestamp if provided
            if timestamp:
                payload['time'] = timestamp

            self.hec_handler.sendEvent(payload)
            return True
        except Exception as e:
            logging.error("Failed to send event to Cribl: {0}".format(e))
            return False

    def send_batch(self, events, sourcetype=None, feed_type=None, feed_name=None):
        # Send multiple events in batch mode for better performance
        if not events:
            return 0

        success_count = 0
        batch_sourcetype = sourcetype or self.sourcetype

        # Add each event to the batch buffer
        for event in events:
            try:
                # Build HEC payload
                payload = {}
                payload['event'] = event
                payload['sourcetype'] = batch_sourcetype
                payload['source'] = self.source
                payload['index'] = self.index
                
                # Add feed classification as HEC fields for easy filtering
                if feed_type:
                    payload['fields'] = {
                        'feed_type': feed_type,
                        'feed_name': feed_name or ''
                    }

                self.hec_handler.sendEvent(payload)
                success_count += 1
            except Exception as e:
                logging.error("Failed to add event to batch: {0}".format(e))

        # Flush the batch to send all buffered events
        try:
            self.hec_handler.flushBatch()
            logging.info("HEC batch sent: {0} events | feed_type={1} | feed_name={2}".format(
                success_count, feed_type or 'n/a', feed_name or 'n/a'))
        except Exception as e:
            logging.error("Error flushing batch: {0}".format(e))

        return success_count


def setup_logging(log_level='INFO', log_file='tenable_integration.log'):
    # Configure logging to both console and file
    # Ensure logs directory exists
    log_dir = 'logs'
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # Prepend logs/ directory to log file path
    log_path = os.path.join(log_dir, log_file)

    # Set up dual logging (console + file)
    logging.basicConfig(
        level=getattr(logging, log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),  # Console output
            logging.FileHandler(log_path)  # File output
        ]
    )
