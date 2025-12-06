#!/usr/bin/env python3
"""
Splunk HTTP Event Collector (HEC) Python Library
Based on georgestarcher's Splunk-Class-httpevent
https://github.com/georgestarcher/Splunk-Class-httpevent

Enhanced with:
- Exponential backoff retry logic
- Connection pool tuning
- Better error handling
"""

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import time
import socket
import os
import logging
import gzip
from datetime import datetime

# Use orjson for faster JSON serialization if available (10x faster than
# stdlib)
try:
    import orjson

    def json_dumps(obj):
        return orjson.dumps(obj).decode('utf-8')
    JSON_LIBRARY = 'orjson'
except ImportError:
    import json

    def json_dumps(obj):
        return json.dumps(obj, separators=(',', ':'))  # Compact output
    JSON_LIBRARY = 'json'


class http_event_collector:
    """
    Splunk HTTP Event Collector class for sending events to Splunk
    """

    # Default retry configuration
    DEFAULT_MAX_RETRIES = 3
    DEFAULT_BACKOFF_FACTOR = 1.0  # 1s, 2s, 4s with exponential backoff
    DEFAULT_RETRY_STATUS_CODES = [429, 500, 502, 503, 504]

    # Default connection pool configuration (increased for higher throughput)
    DEFAULT_POOL_CONNECTIONS = 10
    DEFAULT_POOL_MAXSIZE = 10

    # Rate limiting defaults (optimized for speed without overwhelming HEC)
    DEFAULT_BATCH_DELAY = 0.005  # 5ms delay between batches (production fast)
    DEFAULT_REQUEST_TIMEOUT = 30  # Lower timeout for faster failure detection
    DEFAULT_MAX_BATCH_SIZE = 5242880  # 5MB default batch size for faster throughput

    def __init__(
            self,
            token,
            http_event_server,
            host="",
            http_event_port='8088',
            http_event_server_ssl=True,
            ssl_verify_cert=True,
            ssl_ca_cert=None,
            max_bytes=1048576,
            index="",
            max_retries=None,
            backoff_factor=None,
            pool_connections=None,
            pool_maxsize=None,
            batch_delay=None,
            request_timeout=None):
        """
        Initialize HEC event collector

        Args:
            token: HEC token from Splunk
            http_event_server: Splunk server hostname/IP
            host: Host field for events (default: current hostname)
            http_event_port: HEC port (default: 8088)
            http_event_server_ssl: Use HTTPS (default: True)
            ssl_verify_cert: Verify SSL certificates (default: True, set False for self-signed)
            max_bytes: Maximum batch size in bytes (default: 1MB)
            index: Default Splunk index
            max_retries: Maximum retry attempts (default: 3)
            backoff_factor: Exponential backoff factor in seconds (default: 1.0)
            pool_connections: Number of connection pools (default: 5)
            pool_maxsize: Max connections per pool (default: 5)
            ssl_ca_cert: Path to CA certificate file for SSL verification (default: None)
            batch_delay: Delay between batches in seconds (default: 0.1)
            request_timeout: Request timeout in seconds (default: 60)
        """
        self.token = token
        self.ssl_ca_cert = ssl_ca_cert
        self.ssl_verify = ssl_verify_cert  # Whether to verify certificates
        self.use_ssl = http_event_server_ssl  # Whether to use HTTPS
        self.batchEvents = []
        self.maxByteLength = max_bytes
        self.currentByteLength = 0
        self.server_uri = []

        # Retry configuration
        self.max_retries = max_retries if max_retries is not None else self.DEFAULT_MAX_RETRIES
        self.backoff_factor = backoff_factor if backoff_factor is not None else self.DEFAULT_BACKOFF_FACTOR

        # Connection pool configuration
        self.pool_connections = pool_connections if pool_connections is not None else self.DEFAULT_POOL_CONNECTIONS
        self.pool_maxsize = pool_maxsize if pool_maxsize is not None else self.DEFAULT_POOL_MAXSIZE

        # Rate limiting configuration
        self.batch_delay = batch_delay if batch_delay is not None else self.DEFAULT_BATCH_DELAY
        self.request_timeout = request_timeout if request_timeout is not None else self.DEFAULT_REQUEST_TIMEOUT

        # Adaptive rate limiting - automatically adjusts speed based on HEC
        # response
        self._initial_batch_delay = self.batch_delay  # Remember starting delay
        self._min_batch_delay = 0.001  # 1ms minimum (very fast)
        self._max_batch_delay = 1.0    # 1 second maximum (very slow)
        self._throttle_factor = 2.0    # How much to slow down on error
        # How much to speed up on success (gradual)
        self._speedup_factor = 0.9
        self._consecutive_successes = 0  # Track success streak for speedup
        self._speedup_threshold = 10   # Speed up after N consecutive successes

        # Metrics tracking
        self.retry_count = 0
        self.send_count = 0
        self.error_count = 0
        self.throttle_count = 0  # Track how many times we throttled

        # Set server protocol (always HTTPS for HEC unless explicitly disabled)
        if self.use_ssl:
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

        # Logger for this module
        self.logger = logging.getLogger(__name__)

        # Log JSON library being used and SSL settings
        self.logger.debug(
            f"HEC using JSON library: {JSON_LIBRARY} (orjson is 10x faster)")
        self.logger.info(
            f"HEC SSL: use_ssl={self.use_ssl}, verify_cert={self.ssl_verify}, ca_cert={self.ssl_ca_cert}")

        # Create persistent session with connection pooling and retry logic
        self._session = self._create_session()

    def _create_session(self):
        """
        Create a requests session with connection pooling and retry strategy.

        Returns:
            Configured requests.Session object
        """
        session = requests.Session()

        # Configure retry strategy with exponential backoff
        retry_strategy = Retry(
            total=self.max_retries,
            backoff_factor=self.backoff_factor,
            status_forcelist=self.DEFAULT_RETRY_STATUS_CODES,
            allowed_methods=["POST"],  # Only retry POST requests
            raise_on_status=False  # Don't raise, we handle status ourselves
        )

        # Configure HTTP adapter with connection pooling
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=self.pool_connections,
            pool_maxsize=self.pool_maxsize
        )

        # Mount adapter for both http and https
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        # Disable SSL warnings if not verifying certificates
        if not self.ssl_verify:
            requests.packages.urllib3.disable_warnings()

        return session

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

        # Convert payload to JSON (uses orjson if available for 10x speed)
        payloadString = json_dumps(payload)
        payloadLength = len(payloadString)

        # Check if adding this event would exceed max batch size
        if (self.currentByteLength + payloadLength) > self.maxByteLength:
            self.flushBatch()

        # Add event to batch
        self.batchEvents.append(payloadString)
        self.currentByteLength += payloadLength

    def flushBatch(self):
        """
        Flush the current batch of events to Splunk with retry logic.
        """
        if len(self.batchEvents) == 0:
            return

        # Combine all events with newlines
        payload = '\n'.join(self.batchEvents)
        event_count = len(self.batchEvents)

        # Compress payload for faster network transfer (typically 10x smaller)
        compressed_payload = gzip.compress(
            payload.encode('utf-8'), compresslevel=6)

        # Prepare headers with gzip encoding
        headers = {
            'Authorization': f'Splunk {self.token}',
            'Content-Type': 'application/json',
            'Content-Encoding': 'gzip'
        }

        # Send via persistent session with connection pooling
        # Retry strategy is built into the session adapter
        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                # Determine SSL verification setting
                if self.ssl_verify:
                    verify_param = self.ssl_ca_cert if self.ssl_ca_cert else True
                else:
                    verify_param = False

                response = self._session.post(
                    self.server_uri,
                    data=compressed_payload,
                    headers=headers,
                    verify=verify_param,
                    proxies={'http': None, 'https': None},
                    timeout=self.request_timeout
                )

                # Check response
                if response.status_code == 200:
                    self.send_count += event_count
                    # Reset batch on success
                    self.batchEvents = []
                    self.currentByteLength = 0

                    # Adaptive rate limiting: speed up gradually after
                    # consecutive successes
                    self._consecutive_successes += 1
                    if self._consecutive_successes >= self._speedup_threshold:
                        old_delay = self.batch_delay
                        self.batch_delay = max(
                            self._min_batch_delay,
                            self.batch_delay * self._speedup_factor
                        )
                        if self.batch_delay < old_delay:
                            self.logger.debug(
                                f"HEC adaptive: speeding up, delay {old_delay*1000:.1f}ms -> {self.batch_delay*1000:.1f}ms"
                            )
                        self._consecutive_successes = 0  # Reset counter

                    # Apply current batch delay
                    if self.batch_delay > 0:
                        time.sleep(self.batch_delay)
                    return response

                # Handle specific error codes
                if response.status_code in self.DEFAULT_RETRY_STATUS_CODES:
                    self.retry_count += 1
                    self._consecutive_successes = 0  # Reset success streak

                    # Adaptive rate limiting: slow down on HEC overload (429,
                    # 503, etc)
                    if response.status_code in [429, 503]:
                        old_delay = self.batch_delay
                        self.batch_delay = min(
                            self._max_batch_delay,
                            self.batch_delay * self._throttle_factor
                        )
                        self.throttle_count += 1
                        self.logger.warning(
                            f"HEC overloaded ({response.status_code}): throttling down, "
                            f"delay {old_delay*1000:.1f}ms -> {self.batch_delay*1000:.1f}ms "
                            f"(throttle #{self.throttle_count})")

                    wait_time = self.backoff_factor * (2 ** attempt)
                    self.logger.warning(
                        f"HEC returned {response.status_code}, retrying in {wait_time:.1f}s "
                        f"(attempt {attempt + 1}/{self.max_retries + 1})")
                    time.sleep(wait_time)
                    continue

                # Non-retryable error
                self.error_count += 1
                self.logger.error(
                    f"HEC Event Collector error: {response.status_code} - {response.text}")
                # Reset batch even on error to prevent stuck data
                self.batchEvents = []
                self.currentByteLength = 0
                return response

            except requests.exceptions.Timeout:
                self.retry_count += 1
                self._consecutive_successes = 0  # Reset success streak
                last_error = "Request timeout"

                # Adaptive: slow down on timeout (HEC may be overloaded)
                old_delay = self.batch_delay
                self.batch_delay = min(
                    self._max_batch_delay,
                    self.batch_delay *
                    self._throttle_factor)
                if self.batch_delay > old_delay:
                    self.throttle_count += 1
                    self.logger.info(
                        f"HEC timeout: throttling, delay -> {self.batch_delay*1000:.1f}ms")

                wait_time = self.backoff_factor * (2 ** attempt)
                self.logger.warning(
                    f"HEC request timeout, retrying in {wait_time:.1f}s "
                    f"(attempt {attempt + 1}/{self.max_retries + 1})"
                )
                time.sleep(wait_time)

            except requests.exceptions.ConnectionError as e:
                self.retry_count += 1
                last_error = str(e)
                wait_time = self.backoff_factor * (2 ** attempt)
                self.logger.warning(
                    f"HEC connection error, retrying in {wait_time:.1f}s "
                    f"(attempt {attempt + 1}/{self.max_retries + 1}): {e}"
                )
                time.sleep(wait_time)

            except Exception as e:
                self.error_count += 1
                self.logger.error(f"HEC Event Collector exception: {e}")
                # Reset batch on exception
                self.batchEvents = []
                self.currentByteLength = 0
                raise

        # All retries exhausted
        self.error_count += 1
        self.logger.error(
            f"HEC request failed after {self.max_retries + 1} attempts: {last_error}")
        # Reset batch to prevent stuck state
        self.batchEvents = []
        self.currentByteLength = 0
        # Return False to indicate failure (no response object)
        return False

    def __del__(self):
        """
        Destructor - flush any remaining events
        """
        try:
            self.flushBatch()
        except BaseException:
            pass

    def get_metrics(self):
        """
        Get current metrics for monitoring.

        Returns:
            dict with send_count, retry_count, error_count, throttle_count, current_delay
        """
        return {
            'send_count': self.send_count,
            'retry_count': self.retry_count,
            'error_count': self.error_count,
            'throttle_count': self.throttle_count,
            'current_delay_ms': round(self.batch_delay * 1000, 2),
            'initial_delay_ms': round(self._initial_batch_delay * 1000, 2),
            'max_batches_per_sec': round(1.0 / max(self.batch_delay, 0.001), 1)
        }

    def get_throughput_status(self):
        """
        Get human-readable throughput status for logging.

        Returns:
            str describing current adaptive rate state
        """
        if self.batch_delay <= self._initial_batch_delay:
            status = "FAST"
        elif self.batch_delay >= self._max_batch_delay * 0.5:
            status = "THROTTLED"
        else:
            status = "ADAPTIVE"

        return (
            f"{status}: {self.batch_delay*1000:.1f}ms delay, "
            f"~{1.0/max(self.batch_delay, 0.001):.0f} batches/sec max, "
            f"{self.throttle_count} throttles"
        )


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
