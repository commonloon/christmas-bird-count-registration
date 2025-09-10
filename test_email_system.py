#!/usr/bin/env python3
"""
Test script for email automation system

This script tests the email generation and sending functionality
in a controlled environment.
"""

import os
import sys
from datetime import datetime

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set test mode
os.environ['TEST_MODE'] = 'true'

from flask import Flask
from config.database import get_firestore_client
from config.email_settings import is_test_server
from utils.email_generator import (
    generate_team_update_emails,
    generate_weekly_summary_emails, 
    generate_admin_digest_email
)

def test_environment_detection():
    """Test that environment detection works properly."""
    print("Testing environment detection...")
    print(f"is_test_server(): {is_test_server()}")
    print(f"TEST_MODE environment variable: {os.environ.get('TEST_MODE')}")
    
def test_database_connection():
    """Test database connection."""
    print("\nTesting database connection...")
    try:
        db, database_id = get_firestore_client()
        print(f"✅ Database connection successful: {database_id}")
        return db
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return None

def test_email_generation():
    """Test email generation functions."""
    print("\nTesting email generation functions...")
    
    # Create minimal Flask app for template context
    app = Flask(__name__, template_folder='templates')
    
    with app.app_context():
        try:
            print("Testing team update emails...")
            team_results = generate_team_update_emails()
            print(f"Team updates: {team_results}")
            
            print("\nTesting weekly summary emails...")
            weekly_results = generate_weekly_summary_emails()
            print(f"Weekly summaries: {weekly_results}")
            
            print("\nTesting admin digest email...")
            digest_results = generate_admin_digest_email()
            print(f"Admin digest: {digest_results}")
            
            return True
            
        except Exception as e:
            print(f"❌ Email generation failed: {e}")
            import traceback
            traceback.print_exc()
            return False

def main():
    """Run all tests."""
    print("🧪 Email Automation System Test")
    print("=" * 40)
    
    # Test environment
    test_environment_detection()
    
    # Test database
    db = test_database_connection()
    if not db:
        print("❌ Cannot continue without database connection")
        return
    
    # Test email generation
    success = test_email_generation()
    
    if success:
        print("\n✅ All tests passed!")
        print("\nNext steps:")
        print("1. Deploy the application to test server")
        print("2. Access admin dashboard and test email triggers")
        print("3. Check that emails are sent to birdcount@naturevancouver.ca")
    else:
        print("\n❌ Tests failed - check errors above")

if __name__ == '__main__':
    main()