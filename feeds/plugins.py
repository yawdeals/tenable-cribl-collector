#!/usr/bin/env python3
# Plugin and compliance feed processors using direct API calls (not exports)
from feeds.base import BaseFeedProcessor
import time
import logging


def _safe_api_call_with_retry(
        api_func,
        *args,
        max_retries=3,
        initial_wait=30,
        **kwargs):
    # Retry wrapper for Tenable REST API calls (non-export endpoints)
    logger = logging.getLogger(__name__)

    for attempt in range(max_retries):
        try:
            return api_func(*args, **kwargs)
        except Exception as e:
            error_str = str(e)

            # Check for 429 rate limit error
            if '429' in error_str or 'rate limit' in error_str.lower():
                if attempt < max_retries - 1:
                    wait_time = initial_wait * (1.5 ** attempt)
                    logger.warning(
                        f"Rate limit (429) on API call, waiting {wait_time:.0f}s before retry {attempt + 1}/{max_retries}")
                    time.sleep(wait_time)
                    continue
                else:
                    logger.error(
                        f"Failed after {max_retries} retries due to rate limiting")
                    raise

            # For non-429 errors, raise immediately
            raise

    # Should not reach here, but if we do, raise the last exception
    raise Exception(f"API call failed after {max_retries} retries")


class PluginFeedProcessor(BaseFeedProcessor):

    def __init__(self, tenable_client, checkpoint_mgr,
                 hec_handler, batch_size=5000, max_events=0):
        super(
            PluginFeedProcessor,
            self).__init__(
            tenable_client,
            checkpoint_mgr,
            hec_handler,
            "Plugin Metadata",
            "tenableio_plugin",
            "tenable:io:plugin",
            "plugin",
            batch_size,
            max_events)

    def process(self):
        self.log_start()
        event_count = 0

        try:
            self.logger.info("Fetching plugin families...")
            families = _safe_api_call_with_retry(
                self.tenable.plugins.families)
            self.logger.info("Found {0} plugin families".format(len(families)))

            for family in families:
                family_id = family.get('id')
                family_name = family.get('name', 'Unknown')
                self.logger.info(
                    "Processing plugin family: {0}".format(family_name))

                try:
                    family_details = _safe_api_call_with_retry(
                        self.tenable.plugins.family_details, family_id)
                    plugins = family_details.get('plugins', [])

                    for plugin_summary in plugins:
                        plugin_id = plugin_summary.get('id')
                        if self.is_processed(str(plugin_id)):
                            continue

                        try:
                            plugin_details = _safe_api_call_with_retry(
                                self.tenable.plugins.plugin_details, plugin_id)
                            plugin_details['family_name'] = family_name
                            plugin_details['family_id'] = family_id

                            if self.send_event(
                                    plugin_details, item_id=str(plugin_id)):
                                event_count += 1
                                self.log_progress(event_count)

                            if self.should_stop(event_count):
                                break
                        except Exception as e:
                            self.logger.warning(
                                "Failed to fetch details for plugin {0}: {1}".format(
                                    plugin_id, str(e)))
                            continue

                    if self.should_stop(event_count):
                        break
                except Exception as e:
                    self.logger.warning(
                        "Failed to process family {0}: {1}".format(
                            family_name, str(e)))
                    continue

            self.flush_events()
            self.log_completion(event_count)
        except Exception as e:
            self.logger.error(
                "Error processing plugin feed: {0}".format(
                    str(e)))

        return event_count


class ComplianceFeedProcessor(BaseFeedProcessor):

    def __init__(self, tenable_client, checkpoint_mgr,
                 hec_handler, batch_size=5000, max_events=0):
        super(
            ComplianceFeedProcessor,
            self).__init__(
            tenable_client,
            checkpoint_mgr,
            hec_handler,
            "Compliance Findings",
            "tenableio_compliance",
            "tenable:io:compliance",
            "compliance",
            batch_size,
            max_events)

    def process(self):
        self.log_start()
        event_count = 0

        try:
            last_timestamp = self.get_last_timestamp()
            self.logger.info("Fetching scans since last run...")

            scans = _safe_api_call_with_retry(self.tenable.scans.list)
            scan_list = scans.get('scans', [])
            self.logger.info("Found {0} total scans".format(len(scan_list)))

            for scan in scan_list:
                scan_id = scan.get('id')
                scan_name = scan.get('name', 'Unknown')
                scan_status = scan.get('status')

                if scan_status != 'completed':
                    continue

                scan_timestamp = scan.get('last_modification_date', 0)
                if scan_timestamp <= last_timestamp:
                    continue

                self.logger.info(
                    "Processing compliance findings from scan: {0}".format(scan_name))

                try:
                    scan_details = _safe_api_call_with_retry(
                        self.tenable.scans.details, scan_id)
                    hosts = scan_details.get('hosts', [])

                    for host in hosts:
                        host_id = host.get('host_id')
                        hostname = host.get('hostname', 'unknown')

                        try:
                            host_details = _safe_api_call_with_retry(
                                self.tenable.scans.host_details, scan_id, host_id)
                            compliance_items = host_details.get(
                                'compliance', [])

                            for compliance in compliance_items:
                                compliance_key = "{0}_{1}_{2}".format(
                                    scan_id, host_id, compliance.get(
                                        'plugin_id', 'unknown')
                                )

                                if self.is_processed(compliance_key):
                                    continue

                                compliance_event = {
                                    'scan_id': scan_id,
                                    'scan_name': scan_name,
                                    'host_id': host_id,
                                    'hostname': hostname,
                                    'compliance_data': compliance
                                }

                                if self.send_event(
                                        compliance_event, item_id=compliance_key):
                                    event_count += 1
                                    self.log_progress(event_count)
                        except Exception as e:
                            self.logger.warning(
                                "Failed to get host details for {0}: {1}".format(
                                    hostname, str(e)))
                            continue

                    if scan_timestamp > last_timestamp:
                        self.set_last_timestamp(scan_timestamp)
                except Exception as e:
                    self.logger.warning(
                        "Failed to process scan {0}: {1}".format(
                            scan_name, str(e)))
                    continue

            self.flush_events()
            self.log_completion(event_count)
        except Exception as e:
            self.logger.error(
                "Error processing compliance feed: {0}".format(
                    str(e)))

        return event_count
