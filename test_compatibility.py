#!/usr/bin/env python
"""
Test Python 3.6.8 compatibility
Verifies that our code will run on production server
"""
import sys
import os
import json

def test_python_version():
    """Check Python version"""
    print("Python version: {}.{}.{}".format(sys.version_info.major, sys.version_info.minor, sys.version_info.micro))
    if sys.version_info < (3, 6):
        print("ERROR: Python 3.6+ required")
        return False
    print("OK: Python version compatible")
    return True

def test_imports():
    """Test that all required modules can be imported"""
    print("\nTesting imports...")
    try:
        import logging
        print("OK: logging")
        import json
        print("OK: json")
        import os
        print("OK: os")
        import time
        print("OK: time")
        import argparse
        print("OK: argparse")
        
        # Test checkpoint_manager
        from checkpoint_manager import FileCheckpoint
        print("OK: checkpoint_manager.FileCheckpoint")
        
        # Test tenable_common
        from tenable_common import CriblHECHandler, setup_logging
        print("OK: tenable_common.CriblHECHandler")
        print("OK: tenable_common.setup_logging")
        
        return True
    except Exception as e:
        print("ERROR importing: {}".format(e))
        return False

def test_checkpoint_manager():
    """Test file-based checkpointing"""
    print("\nTesting checkpoint manager...")
    try:
        from checkpoint_manager import FileCheckpoint
        
        # Create test checkpoint
        test_dir = "test_checkpoints"
        os.makedirs(test_dir, exist_ok=True)
        
        checkpoint = FileCheckpoint(checkpoint_dir=test_dir, key_prefix="test_data")
        
        # Test timestamp
        test_key = "test_export"
        checkpoint.set_last_timestamp(test_key, 1234567890)
        timestamp = checkpoint.get_last_timestamp(test_key)
        assert timestamp == 1234567890, "Timestamp mismatch"
        print("OK: Timestamp checkpoint")
        
        # Test processed IDs
        checkpoint.add_processed_id(test_key, "test_id_123")
        checkpoint.add_processed_id(test_key, "test_id_456")
        assert checkpoint.is_processed(test_key, "test_id_123"), "ID not marked as processed"
        print("OK: Processed IDs")
        
        # Cleanup
        import shutil
        shutil.rmtree(test_dir)
        print("OK: Checkpoint manager working")
        return True
    except Exception as e:
        print("ERROR in checkpoint manager: {}".format(e))
        import traceback
        traceback.print_exc()
        return False

def test_string_formatting():
    """Test that we're not using f-strings"""
    print("\nChecking for f-strings in production files...")
    production_files = [
        'checkpoint_manager.py',
        'tenable_common.py',
        'tenable_collector.py'
    ]
    
    found_fstrings = False
    for filename in production_files:
        if os.path.exists(filename):
            with open(filename, 'r') as f:
                content = f.read()
                lines = content.split('\n')
                for i, line in enumerate(lines, 1):
                    # Check for f-strings (f" or f')
                    if " f\"" in line or " f'" in line or "=f\"" in line or "=f'" in line or "(f\"" in line or "(f'" in line:
                        print("WARNING: Possible f-string in {} line {}: {}".format(filename, i, line.strip()))
                        found_fstrings = True
    
    if not found_fstrings:
        print("OK: No f-strings found in production files")
        return True
    else:
        print("ERROR: F-strings found (incompatible with Python 3.6.8)")
        return False

def main():
    """Run all tests"""
    print("=" * 60)
    print("Python 3.6.8 Compatibility Test")
    print("=" * 60)
    
    results = []
    results.append(("Python Version", test_python_version()))
    results.append(("Imports", test_imports()))
    results.append(("Checkpoint Manager", test_checkpoint_manager()))
    results.append(("String Formatting", test_string_formatting()))
    
    print("\n" + "=" * 60)
    print("Test Results:")
    print("=" * 60)
    
    all_passed = True
    for name, result in results:
        status = "PASS" if result else "FAIL"
        print("{}: {}".format(name, status))
        if not result:
            all_passed = False
    
    print("=" * 60)
    if all_passed:
        print("SUCCESS: All compatibility tests passed!")
        return 0
    else:
        print("FAILURE: Some tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
