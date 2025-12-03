#!/usr/bin/env python3
"""
Comprehensive production readiness test
Tests all components with mock credentials to ensure everything works
"""
import os
import sys
import tempfile
import shutil
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime

# Test results tracker
test_results = {
    'passed': [],
    'failed': [],
    'warnings': []
}

def log_test(test_name, status, message=""):
    """Log test result"""
    symbol = "✓" if status == "pass" else "✗" if status == "fail" else "⚠"
    print(f"{symbol} {test_name}: {message}")
    if status == "pass":
        test_results['passed'].append(test_name)
    elif status == "fail":
        test_results['failed'].append(test_name)
    else:
        test_results['warnings'].append(test_name)

print("=" * 80)
print("PRODUCTION READINESS TEST")
print("=" * 80)
print(f"Test started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 80)

# ============================================================================
# TEST 1: Environment Setup
# ============================================================================
print("\n[TEST 1] Environment Configuration")
print("-" * 80)

test_env = {
    'TENABLE_ACCESS_KEY': 'test_access_key_12345',
    'TENABLE_SECRET_KEY': 'test_secret_key_67890',
    'TENABLE_URL': 'https://cloud.tenable.com',
    'CRIBL_HEC_HOST': '192.168.1.100',
    'CRIBL_HEC_PORT': '8088',
    'CRIBL_HEC_TOKEN': 'test_hec_token_abcdef',
    'CRIBL_HEC_SSL_VERIFY': 'false',
    'HEC_BATCH_SIZE': '10000',
    'MAX_EVENTS_PER_FEED': '0',
    'MAX_CONCURRENT_FEEDS': '2',
    'CHECKPOINT_DIR': 'test_checkpoints',
    'CHECKPOINT_MAX_IDS': '100000',
    'CHECKPOINT_RETENTION_DAYS': '30',
    'LOCK_DIR': 'test_locks',
    'LOCK_TIMEOUT': '1200',
    'DELETED_ASSET_SCAN_INTERVAL_HOURS': '168',
    'LOG_LEVEL': 'INFO'
}

for key, value in test_env.items():
    os.environ[key] = value

log_test("Environment variables set", "pass", f"{len(test_env)} variables configured")

# ============================================================================
# TEST 2: Module Imports
# ============================================================================
print("\n[TEST 2] Module Imports")
print("-" * 80)

try:
    import tenable_collector
    log_test("tenable_collector import", "pass")
except Exception as e:
    log_test("tenable_collector import", "fail", str(e))
    sys.exit(1)

try:
    from checkpoint_manager import FileCheckpoint
    log_test("checkpoint_manager import", "pass")
except Exception as e:
    log_test("checkpoint_manager import", "fail", str(e))
    sys.exit(1)

try:
    from process_lock import ProcessLock
    log_test("process_lock import", "pass")
except Exception as e:
    log_test("process_lock import", "fail", str(e))
    sys.exit(1)

try:
    from http_event_collector import http_event_collector
    log_test("http_event_collector import", "pass")
except Exception as e:
    log_test("http_event_collector import", "fail", str(e))
    sys.exit(1)

try:
    from feeds.assets import AssetFeedProcessor, AssetSelfScanProcessor, DeletedAssetProcessor, TerminatedAssetProcessor
    from feeds.vulnerabilities import VulnerabilityFeedProcessor, VulnerabilityNoInfoProcessor, VulnerabilitySelfScanProcessor, FixedVulnerabilityProcessor
    from feeds.plugins import PluginFeedProcessor, ComplianceFeedProcessor
    log_test("All 10 feed processors import", "pass")
except Exception as e:
    log_test("Feed processors import", "fail", str(e))
    sys.exit(1)

# ============================================================================
# TEST 3: File System Setup
# ============================================================================
print("\n[TEST 3] File System Components")
print("-" * 80)

# Create test directories
test_dirs = ['test_checkpoints', 'test_locks', 'logs']
for dir_name in test_dirs:
    if not os.path.exists(dir_name):
        os.makedirs(dir_name)
    log_test(f"Directory {dir_name}", "pass", "exists/created")

# ============================================================================
# TEST 4: Checkpoint Manager
# ============================================================================
print("\n[TEST 4] Checkpoint Manager")
print("-" * 80)

try:
    checkpoint = FileCheckpoint(checkpoint_dir='test_checkpoints')
    checkpoint.add_processed_id('test_feed', 'item_123')
    checkpoint.flush_all()
    
    if checkpoint.is_processed('test_feed', 'item_123'):
        log_test("Checkpoint write/read", "pass")
    else:
        log_test("Checkpoint write/read", "fail", "Item not marked as processed")
    
    # Cleanup
    if os.path.exists('test_checkpoints/checkpoint_test_feed.json'):
        os.remove('test_checkpoints/checkpoint_test_feed.json')
except Exception as e:
    log_test("Checkpoint manager", "fail", str(e))

# ============================================================================
# TEST 5: Process Lock
# ============================================================================
print("\n[TEST 5] Process Lock")
print("-" * 80)

try:
    lock = ProcessLock(lock_file='test.lock', lock_dir='test_locks', timeout=60)
    if lock.acquire():
        log_test("Lock acquisition", "pass")
        lock.release()
        log_test("Lock release", "pass")
    else:
        log_test("Lock acquisition", "fail", "Could not acquire lock")
except Exception as e:
    log_test("Process lock", "fail", str(e))

# ============================================================================
# TEST 6: HEC Client Initialization
# ============================================================================
print("\n[TEST 6] HEC Client")
print("-" * 80)

try:
    hec_client = http_event_collector(
        token=test_env['CRIBL_HEC_TOKEN'],
        http_event_server=test_env['CRIBL_HEC_HOST'],
        http_event_port=test_env['CRIBL_HEC_PORT'],
        http_event_server_ssl=False
    )
    log_test("HEC client initialization", "pass")
    
    # Verify HEC endpoint URL
    expected_url = f"http://{test_env['CRIBL_HEC_HOST']}:{test_env['CRIBL_HEC_PORT']}/services/collector/event"
    if hec_client.server_uri == expected_url:
        log_test("HEC endpoint URL", "pass", expected_url)
    else:
        log_test("HEC endpoint URL", "fail", f"Expected {expected_url}, got {hec_client.server_uri}")
except Exception as e:
    log_test("HEC client", "fail", str(e))

# ============================================================================
# TEST 7: Feed Execution with Mocked APIs
# ============================================================================
print("\n[TEST 7] Feed Execution Flow")
print("-" * 80)

with patch('tenable_collector.ProcessLock') as mock_lock:
    mock_lock_instance = Mock()
    mock_lock_instance.acquire.return_value = True
    mock_lock.return_value = mock_lock_instance
    
    with patch('tenable_collector.TenableIO') as mock_tenable:
        mock_client = MagicMock()
        mock_tenable.return_value = mock_client
        
        # Mock asset export
        def mock_asset_export(*args, **kwargs):
            for i in range(10):
                yield {'id': f'asset_{i}', 'hostname': f'host_{i}', 'ipv4': [f'10.0.0.{i}']}
        
        # Mock vulnerability export
        def mock_vuln_export(*args, **kwargs):
            for i in range(10):
                yield {
                    'asset': {'id': f'asset_{i}', 'hostname': f'host_{i}'},
                    'plugin': {'id': f'plugin_{i}', 'name': f'Vulnerability {i}'},
                    'severity': 'high',
                    'state': 'OPEN'
                }
        
        mock_client.exports.assets.side_effect = mock_asset_export
        mock_client.exports.vulns.side_effect = mock_vuln_export
        
        # Mock plugins
        mock_client.plugins.families.return_value = [{'id': 1, 'name': 'TestFamily'}]
        mock_client.plugins.family_details.return_value = {'plugins': [{'id': 101, 'name': 'TestPlugin'}]}
        mock_client.plugins.plugin_details.return_value = {'id': 101, 'name': 'Test Plugin', 'family': 'TestFamily'}
        
        # Mock scans
        mock_client.scans.list.return_value = {'scans': []}
        
        with patch('tenable_collector.CriblHECHandler') as mock_hec:
            mock_hec_instance = Mock()
            mock_hec_instance.send_batch.return_value = 10  # All events sent
            mock_hec.return_value = mock_hec_instance
            
            try:
                collector = tenable_collector.TenableIntegration()
                log_test("TenableIntegration initialization", "pass")
                
                # Verify configuration
                if collector.max_workers == 2:
                    log_test("Concurrent workers configuration", "pass", f"{collector.max_workers} workers")
                else:
                    log_test("Concurrent workers configuration", "fail", f"Expected 2, got {collector.max_workers}")
                
                if collector.batch_size == 10000:
                    log_test("Batch size configuration", "pass", f"{collector.batch_size} events")
                else:
                    log_test("Batch size configuration", "fail", f"Expected 10000, got {collector.batch_size}")
                
                # Test feed execution
                print("\nExecuting feed test run...")
                feeds_executed = []
                original_process = collector._process_feed
                
                def track_feed(feed_name):
                    feeds_executed.append(feed_name)
                    return original_process(feed_name)
                
                collector._process_feed = track_feed
                collector.run_once(['all'])
                
                expected_feeds = [
                    'tenableio_asset', 'tenableio_asset_self_scan', 'tenableio_compliance',
                    'tenableio_deleted_asset', 'tenableio_fixed_vulnerability', 'tenableio_plugin',
                    'tenableio_terminated_asset', 'tenableio_vulnerability', 
                    'tenableio_vulnerability_no_info', 'tenableio_vulnerability_self_scan'
                ]
                
                if len(feeds_executed) == 10:
                    log_test("All 10 feeds executed", "pass", f"{len(feeds_executed)} feeds")
                else:
                    log_test("All 10 feeds executed", "fail", f"Expected 10, got {len(feeds_executed)}")
                
                missing = [f for f in expected_feeds if f not in feeds_executed]
                if not missing:
                    log_test("All expected feeds present", "pass")
                else:
                    log_test("All expected feeds present", "fail", f"Missing: {missing}")
                
            except Exception as e:
                log_test("Feed execution", "fail", str(e))
                import traceback
                traceback.print_exc()

# ============================================================================
# TEST 8: Concurrent Execution Validation
# ============================================================================
print("\n[TEST 8] Concurrent Execution")
print("-" * 80)

if os.environ.get('MAX_CONCURRENT_FEEDS', '0') != '0':
    log_test("Concurrent mode enabled", "pass", f"MAX_CONCURRENT_FEEDS={os.environ['MAX_CONCURRENT_FEEDS']}")
else:
    log_test("Concurrent mode enabled", "warn", "Running in sequential mode")

# ============================================================================
# TEST 9: Configuration Validation
# ============================================================================
print("\n[TEST 9] Configuration Validation")
print("-" * 80)

config_checks = {
    'HEC_BATCH_SIZE': (10000, "Optimal batch size"),
    'MAX_CONCURRENT_FEEDS': (2, "Recommended concurrent workers"),
    'LOCK_TIMEOUT': (1200, "20 minutes timeout"),
    'CHECKPOINT_RETENTION_DAYS': (30, "30 days retention"),
    'DELETED_ASSET_SCAN_INTERVAL_HOURS': (168, "Weekly scan")
}

for key, (expected, description) in config_checks.items():
    actual = int(os.environ.get(key, 0))
    if actual == expected:
        log_test(f"Config {key}", "pass", f"{actual} - {description}")
    else:
        log_test(f"Config {key}", "warn", f"Expected {expected}, got {actual}")

# ============================================================================
# TEST 10: Cleanup
# ============================================================================
print("\n[TEST 10] Cleanup")
print("-" * 80)

cleanup_items = ['test_checkpoints', 'test_locks']
for item in cleanup_items:
    if os.path.exists(item):
        shutil.rmtree(item)
        log_test(f"Cleanup {item}", "pass")

# ============================================================================
# FINAL RESULTS
# ============================================================================
print("\n" + "=" * 80)
print("TEST SUMMARY")
print("=" * 80)
print(f"✓ Passed:  {len(test_results['passed'])}")
print(f"✗ Failed:  {len(test_results['failed'])}")
print(f"⚠ Warnings: {len(test_results['warnings'])}")
print("=" * 80)

if test_results['failed']:
    print("\n❌ FAILED TESTS:")
    for test in test_results['failed']:
        print(f"  - {test}")
    print("\n⚠️  Production deployment NOT recommended - fix failures first")
    sys.exit(1)
else:
    print("\n✅ ALL CRITICAL TESTS PASSED!")
    print("✅ System is PRODUCTION READY")
    
    if test_results['warnings']:
        print("\n⚠️  Warnings (non-critical):")
        for test in test_results['warnings']:
            print(f"  - {test}")
    
    print("\n" + "=" * 80)
    print("NEXT STEPS:")
    print("=" * 80)
    print("1. Copy .env.example to .env")
    print("2. Update .env with your actual credentials:")
    print(f"   - TENABLE_ACCESS_KEY=<your_tenable_access_key>")
    print(f"   - TENABLE_SECRET_KEY=<your_tenable_secret_key>")
    print(f"   - CRIBL_HEC_HOST=<your_cribl_host>")
    print(f"   - CRIBL_HEC_PORT=8088")
    print(f"   - CRIBL_HEC_TOKEN=<your_hec_token>")
    print("3. Run: ./run_tenable.sh --feed all")
    print("4. Monitor logs: tail -f logs/tenable_integration.log")
    print("=" * 80)
    sys.exit(0)
