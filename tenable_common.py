#!/usr/bin/env python
"""
Common classes and utilities for Tenable to Cribl HEC integration
Python 3.6.8+ compatible - No Redis dependency
"""

import os
import sys
import logging
import http_event_collector as hec


class CriblHECHandler:
    """Handles sending events to Cribl via HTTP Event Collector"""

    def __init__(self, host, port, token, index,
                 sourcetype, source, ssl_verify=True):
        """
        Initialize Cribl HEC handler

        Args:
            host: Cribl HEC host
            port: Cribl HEC port
            token: HEC token
            index: Target index
            sourcetype: Event sourcetype
            source: Event source
            ssl_verify: Verify SSL certificate
        """
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
        """
        Send event to Cribl HEC

        Args:
            event_data: Event data dictionary
            timestamp: Optional event timestamp
            sourcetype: Optional override sourcetype
            source: Optional override source

        Returns:
            True if successful
        """
        try:
            payload = {}
            payload['event'] = event_data
            payload['sourcetype'] = sourcetype or self.sourcetype
            payload['source'] = source or self.source
            payload['index'] = self.index

            if timestamp:
                payload['time'] = timestamp

            self.hec_handler.sendEvent(payload)
            return True
        except Exception as e:
            logging.error("Failed to send event to Cribl: {0}".format(e))
            return False

    def send_batch(self, events, sourcetype=None):
        """
        Send multiple events to Cribl in optimized batch mode

        Args:
            events: List of event dictionaries
            sourcetype: Optional override sourcetype for all events

        Returns:
            Number of successfully sent events
        """
        if not events:
            return 0

        success_count = 0
        batch_sourcetype = sourcetype or self.sourcetype

        for event in events:
            try:
                payload = {}
                payload['event'] = event
                payload['sourcetype'] = batch_sourcetype
                payload['source'] = self.source
                payload['index'] = self.index

                self.hec_handler.sendEvent(payload)
                success_count += 1
            except Exception as e:
                logging.error("Failed to add event to batch: {0}".format(e))

        # Flush the batch
        try:
            self.hec_handler.flushBatch()
            logging.debug(
                "Flushed batch of {0} events to Cribl".format(success_count))
        except Exception as e:
            logging.error("Error flushing batch: {0}".format(e))

        return success_count


def setup_logging(log_level='INFO', log_file='tenable_integration.log'):
    """
    Setup logging configuration

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Log file name (will be placed in logs/ directory)
    """
    # Ensure logs directory exists
    log_dir = 'logs'
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # Prepend logs/ directory to log file path
    log_path = os.path.join(log_dir, log_file)

    logging.basicConfig(
        level=getattr(logging, log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_path)
        ]
    )
