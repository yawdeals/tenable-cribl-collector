#!/usr/bin/env python3
import time
from feeds.base import BaseFeedProcessor


class AssetFeedProcessor(BaseFeedProcessor):
    
    def __init__(self, tenable_client, checkpoint_mgr, hec_handler, batch_size=5000):
        super(AssetFeedProcessor, self).__init__(
            tenable_client, checkpoint_mgr, hec_handler,
            "Asset Inventory", "tenableio_asset", "tenable:io:asset", batch_size
        )
    
    def process(self):
        self.log_start()
        event_count = 0
        
        try:
            self.logger.info("Initiating asset export...")
            for asset in self.tenable.exports.assets():
                asset_id = asset.get('id')
                if self.is_processed(asset_id):
                    continue
                
                if self.send_event(asset, item_id=asset_id):
                    event_count += 1
                    self.log_progress(event_count)
            
            # Flush any remaining events
            self.flush_events()
            self.flush_events()

            self.log_completion(event_count)
        except Exception as e:
            self.logger.error("Error processing asset feed: {0}".format(str(e)))
        
        return event_count


class AssetSelfScanProcessor(BaseFeedProcessor):
    
    def __init__(self, tenable_client, checkpoint_mgr, hec_handler, batch_size=5000):
        super(AssetSelfScanProcessor, self).__init__(
            tenable_client, checkpoint_mgr, hec_handler,
            "Agent-Based Assets", "tenableio_asset_self_scan", "tenable:io:asset:self_scan", batch_size
        )
    
    def process(self):
        self.log_start()
        event_count = 0
        
        try:
            self.logger.info("Initiating agent-based asset export...")
            for asset in self.tenable.exports.assets():
                if not asset.get('has_agent', False):
                    continue
                
                asset_id = asset.get('id')
                if self.is_processed(asset_id):
                    continue
                
                if self.send_event(asset, item_id=asset_id):
                    event_count += 1
                    self.log_progress(event_count)
            
            self.flush_events()
            self.flush_events()

            self.log_completion(event_count)
        except Exception as e:
            self.logger.error("Error processing agent-based asset feed: {0}".format(str(e)))
        
        return event_count


class DeletedAssetProcessor(BaseFeedProcessor):
    
    def __init__(self, tenable_client, checkpoint_mgr, hec_handler, batch_size=5000):
        super(DeletedAssetProcessor, self).__init__(
            tenable_client, checkpoint_mgr, hec_handler,
            "Deleted Assets", "tenableio_deleted_asset", "tenable:io:asset:deleted", batch_size)
    
    def process(self):
        self.log_start()
        event_count = 0
        
        try:
            previous_assets = self.get_processed_ids()
            self.logger.info("Found {0} assets in previous checkpoint".format(len(previous_assets)))
            
            current_assets = set()
            self.logger.info("Fetching current assets from Tenable...")
            for asset in self.tenable.exports.assets():
                current_assets.add(asset.get('id'))
            
            self.logger.info("Found {0} current assets".format(len(current_assets)))
            deleted_assets = previous_assets - current_assets
            
            if deleted_assets:
                self.logger.info("Detected {0} deleted assets".format(len(deleted_assets)))
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
            
            for asset_id in current_assets:
                self.mark_processed(asset_id)
            
            self.flush_events()

            
            self.log_completion(event_count)
        except Exception as e:
            self.logger.error("Error processing deleted asset feed: {0}".format(str(e)))
        
        return event_count


class TerminatedAssetProcessor(BaseFeedProcessor):
    
    def __init__(self, tenable_client, checkpoint_mgr, hec_handler, batch_size=5000):
        super(TerminatedAssetProcessor, self).__init__(
            tenable_client, checkpoint_mgr, hec_handler,
            "Terminated Assets", "tenableio_terminated_asset", "tenable:io:asset:terminated", batch_size)
    
    def process(self):
        self.log_start()
        event_count = 0
        
        try:
            self.logger.info("Initiating terminated asset export...")
            for asset in self.tenable.exports.assets():
                if 'terminated_at' not in asset or asset.get('terminated_at') is None:
                    continue
                
                asset_id = asset.get('id')
                if self.is_processed(asset_id):
                    continue
                
                if self.send_event(asset, item_id=asset_id):
                    event_count += 1
                    self.log_progress(event_count)
            
            self.flush_events()

            
            self.log_completion(event_count)
        except Exception as e:
            self.logger.error("Error processing terminated asset feed: {0}".format(str(e)))
        
        return event_count
