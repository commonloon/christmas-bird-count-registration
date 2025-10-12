#!/usr/bin/env python3
# Test Suite Setup Validation
# Updated by Claude AI on 2025-09-25

"""
Quick validation script to verify the functional test suite setup.
Run this before executing tests to ensure all dependencies and configuration are correct.
"""

import sys
import os
import subprocess
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def check_python_version():
    """Check Python version is compatible."""
    version = sys.version_info
    if version < (3, 8):
        print(f"❌ Python {version.major}.{version.minor} is too old. Python 3.8+ required.")
        return False
    print(f"✅ Python {version.major}.{version.minor}.{version.micro} - Compatible")
    return True

def check_dependencies():
    """Check that required packages are installed."""
    required_packages = [
        'pytest',
        'selenium',
        'webdriver_manager',
        'google.cloud.firestore',
        'google.cloud.secretmanager',
        'requests',
        'faker',
        'beautifulsoup4'
    ]

    missing_packages = []

    for package in required_packages:
        try:
            __import__(package)
            print(f"✅ {package} - Available")
        except ImportError:
            missing_packages.append(package)
            print(f"❌ {package} - Missing")

    if missing_packages:
        print(f"\n📝 Install missing packages:")
        print(f"pip install -r tests/requirements.txt")
        return False

    return True

def check_gcloud_setup():
    """Check Google Cloud authentication and configuration."""
    try:
        # Check if gcloud is available
        result = subprocess.run(['gcloud', '--version'],
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print("✅ Google Cloud SDK - Available")
        else:
            print("❌ Google Cloud SDK - Not available")
            return False
    except (subprocess.TimeoutExpired, FileNotFoundError):
        print("❌ Google Cloud SDK - Not found in PATH")
        return False

    # Check project configuration
    try:
        result = subprocess.run(['gcloud', 'config', 'get-value', 'project'],
                              capture_output=True, text=True, timeout=10)
        project = result.stdout.strip()
        if project == 'vancouver-cbc-registration':
            print("✅ Google Cloud Project - Configured correctly")
        else:
            print(f"❌ Google Cloud Project - Expected 'vancouver-cbc-registration', got '{project}'")
            print("   Run: gcloud config set project vancouver-cbc-registration")
            return False
    except subprocess.TimeoutExpired:
        print("❌ Google Cloud Project - Configuration check timed out")
        return False

    return True

def check_authentication():
    """Check Google Cloud authentication."""
    try:
        from google.cloud import firestore
        client = firestore.Client()
        # Try a simple operation
        client.collection('test').limit(1).get()
        print("✅ Google Cloud Authentication - Working")
        return True
    except Exception as e:
        print(f"❌ Google Cloud Authentication - Failed: {e}")
        print("   Run: gcloud auth application-default login")
        return False

def check_test_structure():
    """Check test directory structure."""
    test_dir = Path(__file__).parent

    required_files = [
        'config.py',
        'pytest.ini',
        'requirements.txt',
        'README.md',
        'page_objects/__init__.py',
        'page_objects/base_page.py',
        'page_objects/registration_page.py',
        'data/__init__.py',
        'data/test_scenarios.py',
        'data/test_accounts.py'
    ]

    required_test_files = [
        'test_registration_workflows.py',
        'test_admin_dashboard_workflows.py',
        'test_csv_export_workflows.py',
        'test_admin_participant_management.py'
    ]

    all_good = True

    for file_path in required_files + required_test_files:
        full_path = test_dir / file_path
        if full_path.exists():
            print(f"✅ {file_path} - Present")
        else:
            print(f"❌ {file_path} - Missing")
            all_good = False

    return all_good

def check_configuration():
    """Check test configuration."""
    try:
        from tests.test_config import get_base_url, get_database_name
        from tests.data import get_test_participant

        base_url = get_base_url()
        database_name = get_database_name()

        print(f"✅ Test Configuration - Base URL: {base_url}")
        print(f"✅ Test Configuration - Database: {database_name}")

        # Test data generation
        participant = get_test_participant('participants', 'regular_newbie')
        if participant and 'personal' in participant:
            print("✅ Test Data Generation - Working")
        else:
            print("❌ Test Data Generation - Failed")
            return False

        return True
    except Exception as e:
        print(f"❌ Test Configuration - Error: {e}")
        return False

def check_firefox():
    """Check Firefox installation."""
    try:
        result = subprocess.run(['firefox', '--version'],
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            version = result.stdout.strip()
            print(f"✅ Firefox - {version}")
            return True
        else:
            print("❌ Firefox - Not available")
            return False
    except (subprocess.TimeoutExpired, FileNotFoundError):
        print("❌ Firefox - Not found in PATH")
        print("   Install Firefox from: https://www.mozilla.org/firefox/")
        return False

def main():
    """Run all validation checks."""
    print("🧪 Christmas Bird Count Registration - Test Suite Validation")
    print("=" * 60)

    checks = [
        ("Python Version", check_python_version),
        ("Dependencies", check_dependencies),
        ("Google Cloud SDK", check_gcloud_setup),
        ("Authentication", check_authentication),
        ("Test Structure", check_test_structure),
        ("Configuration", check_configuration),
        ("Firefox Browser", check_firefox)
    ]

    results = []

    for check_name, check_func in checks:
        print(f"\n📋 Checking {check_name}...")
        try:
            result = check_func()
            results.append((check_name, result))
        except Exception as e:
            print(f"❌ {check_name} - Unexpected error: {e}")
            results.append((check_name, False))

    # Summary
    print("\n" + "=" * 60)
    print("📊 VALIDATION SUMMARY")
    print("=" * 60)

    all_passed = True
    for check_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {check_name}")
        if not passed:
            all_passed = False

    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 ALL CHECKS PASSED - Test suite ready to run!")
        print("\n💡 Quick Start:")
        print("   pytest tests/ -m critical -v")
    else:
        print("⚠️  SOME CHECKS FAILED - Fix issues before running tests")
        print("\n📚 See tests/README.md for detailed setup instructions")

    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())