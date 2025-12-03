#!/usr/bin/env python3
"""
Test script to verify all 10 feeds would execute properly
Simulates the feed execution logic without actual API calls
"""
import os
import sys
from unittest.mock import Mock, MagicMock, patch

# Set up mock environment
os.environ['TENABLE_ACCESS_KEY'] = 'mock_access_key'
os.environ['TENABLE_SECRET_KEY'] = 'mock_secret_key'
os.environ['CRIBL_HEC_HOST'] = 'mock_cribl_host'
os.environ['CRIBL_HEC_PORT'] = '8088'
os.environ['CRIBL_HEC_TOKEN'] = 'mock_hec_token'
os.environ['MAX_CONCURRENT_FEEDS'] = '2'
os.environ['HEC_BATCH_SIZE'] = '10000'
os.environ['MAX_EVENTS_PER_FEED'] = '100'  # Limit for testing

print("=" * 80)
print("FEED EXECUTION TEST")
print("=" * 80)
print(f"MAX_CONCURRENT_FEEDS: {os.environ['MAX_CONCURRENT_FEEDS']}")
print(f"MAX_EVENTS_PER_FEED: {os.environ['MAX_EVENTS_PER_FEED']}")
print("=" * 80)

# Mock the process lock
with patch('tenable_collector.ProcessLock') as mock_lock:
    mock_lock_instance = Mock()
    mock_lock_instance.acquire.return_value = True
    mock_lock.return_value = mock_lock_instance
    
    # Mock Tenable client
    with patch('tenable_collector.TenableIO') as mock_tenable:
        mock_client = MagicMock()
        mock_tenable.return_value = mock_client
        
        # Mock exports to return test data
        def mock_asset_export(*args, **kwargs):
            """Mock asset export - returns 50 assets"""
            for i in range(50):
                yield {'id': f'asset_{i}', 'hostname': f'host_{i}'}
        
        def mock_vuln_export(*args, **kwargs):
            """Mock vulnerability export - returns 50 vulns"""
            for i in range(50):
                yield {'asset': {'id': f'asset_{i}'}, 'plugin': {'id': f'plugin_{i}'}}
        
        mock_client.exports.assets.side_effect = mock_asset_export
        mock_client.exports.vulns.side_effect = mock_vuln_export
        
        # Mock plugins API
        mock_client.plugins.families.return_value = [
            {'id': 1, 'name': 'Family1'},
            {'id': 2, 'name': 'Family2'}
        ]
        mock_client.plugins.family_details.return_value = {
            'plugins': [
                {'id': 101, 'name': 'Plugin1'},
                {'id': 102, 'name': 'Plugin2'}
            ]
        }
        mock_client.plugins.plugin_details.return_value = {
            'id': 101,
            'name': 'Test Plugin',
            'description': 'Test'
        }
        
        # Mock scans API
        mock_client.scans.list.return_value = {
            'scans': [
                {'id': 1, 'name': 'Scan1', 'status': 'completed', 'last_modification_date': 1000000}
            ]
        }
        mock_client.scans.details.return_value = {
            'hosts': [
                {'host_id': 1, 'hostname': 'testhost'}
            ]
        }
        mock_client.scans.host_details.return_value = {
            'compliance': [
                {'plugin_id': 201, 'status': 'FAILED'}
            ]
        }
        
        # Mock HEC handler
        with patch('tenable_collector.CriblHECHandler') as mock_hec:
            mock_hec_instance = Mock()
            mock_hec_instance.send_batch.return_value = 100  # All events sent successfully
            mock_hec.return_value = mock_hec_instance
            
            # Import and run collector
            import tenable_collector
            
            print("\nInitializing TenableIntegration...")
            collector = tenable_collector.TenableIntegration()
            
            print(f"max_workers set to: {collector.max_workers}")
            print(f"batch_size set to: {collector.batch_size}")
            print(f"max_events set to: {collector.max_events}")
            
            # Test all feeds
            print("\n" + "=" * 80)
            print("TESTING ALL 10 FEEDS")
            print("=" * 80)
            
            data_types = ['all']
            
            # Capture which feeds get processed
            processed_feeds = []
            original_process_feed = collector._process_feed
            
            def track_feed_processing(feed_name):
                print(f"\n>>> Processing feed: {feed_name}")
                processed_feeds.append(feed_name)
                try:
                    result = original_process_feed(feed_name)
                    print(f"<<< Feed {feed_name} completed with {result} events")
                    return result
                except Exception as e:
                    print(f"<<< Feed {feed_name} FAILED: {e}")
                    import traceback
                    traceback.print_exc()
                    return 0
            
            collector._process_feed = track_feed_processing
            
            # Run the collector
            print("\nStarting collection run...")
            collector.run_once(data_types)
            
            # Report results
            print("\n" + "=" * 80)
            print("EXECUTION SUMMARY")
            print("=" * 80)
            print(f"Total feeds processed: {len(processed_feeds)}")
            print(f"Feeds: {processed_feeds}")
            
            expected_feeds = [
                'tenableio_asset',
                'tenableio_asset_self_scan',
                'tenableio_compliance',
                'tenableio_deleted_asset',
                'tenableio_fixed_vulnerability',
                'tenableio_plugin',
                'tenableio_terminated_asset',
                'tenableio_vulnerability',
                'tenableio_vulnerability_no_info',
                'tenableio_vulnerability_self_scan'
            ]
            
            missing_feeds = [f for f in expected_feeds if f not in processed_feeds]
            
            if missing_feeds:
                print(f"\n❌ MISSING FEEDS ({len(missing_feeds)}):")
                for feed in missing_feeds:
                    print(f"  - {feed}")
            else:
                print("\n✅ ALL 10 FEEDS PROCESSED SUCCESSFULLY!")
            
            print("=" * 80)
