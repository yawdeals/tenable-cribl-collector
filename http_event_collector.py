#!/usr/bin/env python
"""
Splunk HTTP Event Collector (HEC) Python Library
Based on georgestarcher's Splunk-Class-httpevent
https://github.com/georgestarcher/Splunk-Class-httpevent
"""

import requests
import json
import time
import socket
from datetime import datetime


class http_event_collector:
    """
    Splunk HTTP Event Collector class for sending events to Splunk
    """

    def __init__(
            self,
            token,
            http_event_server,
            host="",
            http_event_port='8088',
            http_event_server_ssl=True,
            max_bytes=1048576,
            index=""):
        """
        Initialize HEC event collector

        Args:
            token: HEC token from Splunk
            http_event_server: Splunk server hostname/IP
            host: Host field for events (default: current hostname)
            http_event_port: HEC port (default: 8088)
            http_event_server_ssl: Use SSL/TLS (default: True)
            max_bytes: Maximum batch size in bytes (default: 1MB)
            index: Default Splunk index
        """
        self.token = token
        self.batchEvents = []
        self.maxByteLength = max_bytes
        self.currentByteLength = 0
        self.server_uri = []

        # Set server protocol
        if http_event_server_ssl:
            protocol = 'https'
        else:
            protocol = 'http'

        # Build server URI
        self.server_uri = f'{protocol}://{http_event_server}:{http_event_port}/services/collector/event'

        # Set default host if not provided
        if host:
            self.host = host
        else:
            self.host = socket.gethostname()

        self.index = index

        # Disable SSL warnings if not verifying
        if not http_event_server_ssl:
            requests.packages.urllib3.disable_warnings()

    def sendEvent(self, payload, eventtime=""):
        """
        Send a single event or add to batch

        Args:
            payload: Event payload dictionary
            eventtime: Optional event time (epoch or formatted string)
        """
        # Add metadata to payload
        if 'host' not in payload:
            payload['host'] = self.host

        if 'index' not in payload and self.index:
            payload['index'] = self.index

        # Handle event time
        if eventtime:
            payload['time'] = eventtime
        else:
            if 'time' not in payload:
                payload['time'] = str(int(time.time()))

        # Convert payload to JSON
        payloadString = json.dumps(payload)
        payloadLength = len(payloadString)

        # Check if adding this event would exceed max batch size
        if (self.currentByteLength + payloadLength) > self.maxByteLength:
            self.flushBatch()

        # Add event to batch
        self.batchEvents.append(payloadString)
        self.currentByteLength += payloadLength

    def flushBatch(self):
        """
        Flush the current batch of events to Splunk
        """
        if len(self.batchEvents) == 0:
            return

        # Combine all events with newlines
        payload = '\n'.join(self.batchEvents)

        # Prepare headers
        headers = {
            'Authorization': f'Splunk {self.token}',
            'Content-Type': 'application/json'
        }

        # Send to Splunk (bypass proxy)
        try:
            response = requests.post(
                self.server_uri,
                data=payload,
                headers=headers,
                verify=False,
                proxies={'http': None, 'https': None}
            )

            # Check response
            if response.status_code != 200:
                print(
                    f"HEC Event Collector error: {response.status_code} - {response.text}")

            # Reset batch
            self.batchEvents = []
            self.currentByteLength = 0

            return response

        except Exception as e:
            print(f"HEC Event Collector exception: {e}")
            raise

    def __del__(self):
        """
        Destructor - flush any remaining events
        """
        try:
            self.flushBatch()
        except BaseException:
            pass


class http_event_collector_raw:
    """
    Splunk HTTP Event Collector class for raw endpoint
    """

    def __init__(self, token, http_event_server, http_event_port='8088',
                 http_event_server_ssl=True, channel=""):
        """
        Initialize HEC raw event collector

        Args:
            token: HEC token from Splunk
            http_event_server: Splunk server hostname/IP
            http_event_port: HEC port (default: 8088)
            http_event_server_ssl: Use SSL/TLS (default: True)
            channel: HEC channel GUID
        """
        self.token = token
        self.channel = channel

        # Set server protocol
        if http_event_server_ssl:
            protocol = 'https'
        else:
            protocol = 'http'

        # Build server URI
        self.server_uri = f'{protocol}://{http_event_server}:{http_event_port}/services/collector/raw'

        # Disable SSL warnings if not verifying
        if not http_event_server_ssl:
            requests.packages.urllib3.disable_warnings()

    def sendEvent(self, payload, source="", sourcetype="", index="", host=""):
        """
        Send raw event to Splunk

        Args:
            payload: Raw event data
            source: Event source
            sourcetype: Event sourcetype
            index: Splunk index
            host: Event host
        """
        # Prepare headers
        headers = {
            'Authorization': f'Splunk {self.token}'
        }

        if self.channel:
            headers['X-Splunk-Request-Channel'] = self.channel

        # Prepare query parameters
        params = {}
        if source:
            params['source'] = source
        if sourcetype:
            params['sourcetype'] = sourcetype
        if index:
            params['index'] = index
        if host:
            params['host'] = host

        # Send to Splunk
        try:
            response = requests.post(
                self.server_uri,
                params=params,
                data=payload,
                headers=headers,
                verify=False  # Consider making this configurable
            )

            # Check response
            if response.status_code != 200:
                print(
                    f"HEC Raw Event Collector error: {response.status_code} - {response.text}")

            return response

        except Exception as e:
            print(f"HEC Raw Event Collector exception: {e}")
            raise
