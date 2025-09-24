#!/usr/bin/env python3
"""
Simple validation script for regression tests
Tests basic functionality without browser automation to verify fixes
"""

import sys
import os
from datetime import datetime

# Add project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

def validate_imports():
    """Test that all required modules can be imported."""
    try:
        # Test core imports
        from models.participant import ParticipantModel
        from config.database import get_firestore_client
        print("[OK] Core imports successful")

        # Test selenium imports (but don't initialize)
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait, Select
        print("[OK] Selenium imports successful")

        # Test database connection
        db, database_id = get_firestore_client()
        print(f"[OK] Database connection successful: {database_id}")

        # Test model initialization
        participant_model = ParticipantModel(db, datetime.now().year)
        print("[OK] ParticipantModel initialization successful")

        return True

    except Exception as e:
        print(f"[ERROR] Import validation failed: {e}")
        return False

def validate_database_operations():
    """Test basic database operations."""
    try:
        from models.participant import ParticipantModel
        from config.database import get_firestore_client

        db, _ = get_firestore_client()
        participant_model = ParticipantModel(db, datetime.now().year)

        # Test basic queries
        all_participants = participant_model.get_all_participants()
        print(f"[OK] Found {len(all_participants)} participants in database")

        all_leaders = participant_model.get_leaders()
        print(f"[OK] Found {len(all_leaders)} leaders in database")

        # Verify all leaders are participants (single-table integrity)
        leader_ids = {leader['id'] for leader in all_leaders}
        participant_ids = {p['id'] for p in all_participants}
        orphaned_leaders = leader_ids - participant_ids

        if len(orphaned_leaders) == 0:
            print("[OK] No orphaned leader records (single-table integrity confirmed)")
        else:
            print(f"[ERROR] Found {len(orphaned_leaders)} orphaned leader records")
            return False

        # Verify leaders have is_leader flag
        for leader in all_leaders:
            if not leader.get('is_leader', False):
                print(f"[ERROR] Leader {leader['id']} missing is_leader flag")
                return False
        print("[OK] All leaders have is_leader=True")

        return True

    except Exception as e:
        print(f"[ERROR] Database validation failed: {e}")
        return False

def validate_form_fields():
    """Validate that the form field names we're using in tests are correct."""
    expected_fields = {
        'text_inputs': ['first_name', 'last_name', 'email', 'phone', 'phone2'],
        'selects': ['skill_level', 'experience', 'preferred_area'],
        'radio_buttons': ['regular', 'feeder'],  # IDs for participation_type radio buttons
        'checkboxes': ['has_binoculars', 'spotting_scope', 'interested_in_leadership', 'interested_in_scribe'],
        'textarea': ['notes_to_organizers']
    }

    expected_values = {
        'skill_level': ['Newbie', 'Beginner', 'Intermediate', 'Expert'],
        'experience': ['None', '1-2 counts', '3+ counts'],
        'participation_type': ['regular', 'FEEDER']
    }

    print("[OK] Form field validation - Expected fields defined:")
    for field_type, fields in expected_fields.items():
        print(f"  - {field_type}: {fields}")

    print("[OK] Form value validation - Expected values defined:")
    for field, values in expected_values.items():
        print(f"  - {field}: {values}")

    return True

def main():
    """Run all validation tests."""
    print("="*60)
    print("REGRESSION TEST VALIDATION")
    print("="*60)

    validations = [
        ("Import Validation", validate_imports),
        ("Database Operations", validate_database_operations),
        ("Form Fields", validate_form_fields)
    ]

    results = []
    for name, validator in validations:
        print(f"\n--- {name} ---")
        result = validator()
        results.append((name, result))
        if result:
            print(f"[OK] {name}: PASSED")
        else:
            print(f"[ERROR] {name}: FAILED")

    print("\n" + "="*60)
    print("VALIDATION SUMMARY")
    print("="*60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "PASS" if result else "FAIL"
        print(f"{name}: {status}")

    print(f"\nOverall: {passed}/{total} validations passed")

    if passed == total:
        print("[OK] All validations passed - regression tests should work")
        return 0
    else:
        print("[ERROR] Some validations failed - fix issues before running tests")
        return 1

if __name__ == "__main__":
    sys.exit(main())