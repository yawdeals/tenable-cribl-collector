#!/usr/bin/env python3
"""
Test Tenable.io API Access
Diagnostic script to verify Tenable.io API connectivity and discover accessible data
"""

import os
import json
from dotenv import load_dotenv
from tenable.io import TenableIO


def print_section(title):
    """Print a formatted section header"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def safe_api_call(description, func):
    """
    Safely execute an API call and handle errors
    
    Args:
        description: What we're trying to retrieve
        func: Function to execute
    """
    print(f"\nAttempting to retrieve: {description}")
    try:
        result = func()
        if isinstance(result, list):
            print(f"[SUCCESS] Found {len(result)} items")
            return result
        elif isinstance(result, dict):
            print(f"[SUCCESS] Retrieved data")
            return result
        else:
            print(f"[SUCCESS]")
            return result
    except Exception as e:
        print(f"[FAILED] {str(e)}")
        return None


def main():
    """Test all available Tenable.io API endpoints"""
    
    # Load environment
    load_dotenv()
    
    print_section("Tenable.io API Access Test")
    print("Testing connectivity and discovering available data...")
    
    # Initialize Tenable client
    try:
        tenable = TenableIO(
            access_key=os.getenv('TENABLE_ACCESS_KEY'),
            secret_key=os.getenv('TENABLE_SECRET_KEY'),
            url=os.getenv('TENABLE_URL', 'https://cloud.tenable.com')
        )
        print("[SUCCESS] Initialized Tenable.io client")
    except Exception as e:
        print(f"[ERROR] Failed to initialize Tenable client: {e}")
        return
    
    # Test 1: Scanners
    print_section("1. Scanners")
    scanners = safe_api_call("Scanners list", lambda: list(tenable.scanners.list()))
    if scanners:
        for scanner in scanners[:5]:  # Show first 5
            print(f"   - {scanner.get('name')} (ID: {scanner.get('id')}, Status: {scanner.get('status')})")
    
    # Test 2: Scans
    print_section("2. Scans")
    scans = safe_api_call("Scans list", lambda: list(tenable.scans.list()))
    if scans:
        for scan in scans[:5]:  # Show first 5
            print(f"   - {scan.get('name')} (ID: {scan.get('id')}, Status: {scan.get('status')})")
    
    # Test 3: Assets
    print_section("3. Assets")
    assets = safe_api_call("Assets list", lambda: list(tenable.assets.list()))
    if assets:
        for asset in assets[:5]:  # Show first 5
            print(f"   - {asset.get('hostname', asset.get('id'))} (Last seen: {asset.get('last_seen')})")
    
    # Test 4: Folders
    print_section("4. Folders")
    folders = safe_api_call("Folders list", lambda: list(tenable.folders.list()))
    if folders:
        for folder in folders[:5]:
            print(f"   - {folder.get('name')} (ID: {folder.get('id')})")
    
    # Test 5: Agent Groups
    print_section("5. Agent Groups")
    agent_groups = safe_api_call("Agent groups list", lambda: list(tenable.agent_groups.list()))
    if agent_groups:
        for group in agent_groups[:5]:
            print(f"   - {group.get('name')} (ID: {group.get('id')})")
    
    # Test 6: Scan Policies
    print_section("6. Scan Policies")
    policies = safe_api_call("Policies list", lambda: list(tenable.policies.list()))
    if policies:
        for policy in policies[:5]:
            print(f"   - {policy.get('name')} (ID: {policy.get('id')})")
    
    # Test 7: Users
    print_section("7. Users")
    users = safe_api_call("Users list", lambda: list(tenable.users.list()))
    if users:
        for user in users[:5]:
            print(f"   - {user.get('username')} ({user.get('email')})")
    
    # Test 8: Groups
    print_section("8. Groups")
    groups = safe_api_call("Groups list", lambda: list(tenable.groups.list()))
    if groups:
        for group in groups[:5]:
            print(f"   - {group.get('name')} (ID: {group.get('id')})")
    
    # Test 9: Networks
    print_section("9. Networks")
    networks = safe_api_call("Networks list", lambda: list(tenable.networks.list()))
    if networks:
        for network in networks[:5]:
            print(f"   - {network.get('name')} (UUID: {network.get('uuid')})")
    
    # Test 10: Plugins
    print_section("10. Plugin Families")
    plugin_families = safe_api_call("Plugin families", lambda: tenable.plugins.families())
    if plugin_families:
        families = plugin_families.get('families', [])
        print(f"   Found {len(families)} plugin families")
        for family in families[:5]:
            print(f"   - {family.get('name')} (ID: {family.get('id')})")
    
    # Test 11: Exclusions
    print_section("11. Scan Exclusions")
    exclusions = safe_api_call("Exclusions list", lambda: list(tenable.exclusions.list()))
    if exclusions:
        for exclusion in exclusions[:5]:
            print(f"   - {exclusion.get('name')} (ID: {exclusion.get('id')})")
    
    # Test 12: Credentials
    print_section("12. Credentials")
    credentials = safe_api_call("Credentials list", lambda: list(tenable.credentials.list()))
    if credentials:
        for cred in credentials[:5]:
            print(f"   - {cred.get('name')} (Type: {cred.get('type')})")
    
    # Summary
    print_section("Summary")
    print("\nData Availability Summary:")
    
    available_data = []
    if scanners:
        available_data.append(f"{len(scanners)} Scanners")
    if scans:
        available_data.append(f"{len(scans)} Scans")
    if assets:
        available_data.append(f"{len(assets)} Assets")
    if folders:
        available_data.append(f"{len(folders)} Folders")
    if agent_groups:
        available_data.append(f"{len(agent_groups)} Agent Groups")
    if policies:
        available_data.append(f"{len(policies)} Policies")
    if users:
        available_data.append(f"{len(users)} Users")
    if groups:
        available_data.append(f"{len(groups)} Groups")
    if networks:
        available_data.append(f"{len(networks)} Networks")
    if exclusions:
        available_data.append(f"{len(exclusions)} Exclusions")
    if credentials:
        available_data.append(f"{len(credentials)} Credentials")
    
    if available_data:
        print("\nAvailable data sources:")
        for item in available_data:
            print(f"  [OK] {item}")
        print("\n[SUCCESS] Your API keys are working! You can access the above data.")
    else:
        print("\n[WARNING] No data found. Your Tenable.io account may be empty or not fully configured.")
        print("   Possible reasons:")
        print("   - Trial account with no scanners deployed")
        print("   - No scans have been run yet")
        print("   - Account permissions may be limited")
    
    print("\n" + "=" * 80)
    print("Test completed!")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
