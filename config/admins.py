# Updated by Claude AI on 2025-09-22
# Admin email whitelist for Vancouver CBC Registration App
# Environment-based configuration with automatic test account management

import os
import logging

# Production admin emails (always active)
PRODUCTION_ADMIN_EMAILS = [
    'birdcount@naturevancouver.ca',       # deployment account owner
    'webmaster@naturevancouver.ca',       # webmaster
    'kelvin@naturevancouver.ca',          # Count coordinator
    'michelle@naturevancouver.ca',        # Count coordinator
]

# Test admin emails (NEVER deployed to production)
TEST_ADMIN_EMAILS = [
    'cbc-test-admin1@naturevancouver.ca',
    'cbc-test-admin2@naturevancouver.ca',
]

def is_test_environment():
    """Detect if running in test environment."""
    return (
        os.getenv('TEST_MODE', '').lower() == 'true' or
        os.getenv('FLASK_ENV') == 'development' or
        'test' in os.getenv('GOOGLE_CLOUD_PROJECT', '').lower()
    )

def get_admin_emails() -> list:
    """Get admin emails based on environment with safety checks."""
    admins = PRODUCTION_ADMIN_EMAILS.copy()

    if is_test_environment():
        admins.extend(TEST_ADMIN_EMAILS)
        logging.info(f"Test environment detected: Added {len(TEST_ADMIN_EMAILS)} test admin accounts")
    else:
        # Double-check we're not accidentally in production with test indicators
        if any('test' in email.lower() for email in PRODUCTION_ADMIN_EMAILS):
            logging.error("SECURITY WARNING: Test emails detected in production admin list!")
            admins = [email for email in admins if 'test' not in email.lower()]

        logging.info(f"Production environment: Using {len(admins)} production admin accounts only")

    return admins

def is_admin(email: str) -> bool:
    """Check if an email address has admin privileges."""
    if not email:
        return False
    admin_emails = get_admin_emails()
    return email.lower().strip() in [admin.lower() for admin in admin_emails]

# For backward compatibility
ADMIN_EMAILS = get_admin_emails()

# Runtime validation
if not is_test_environment():
    test_emails_in_list = [email for email in ADMIN_EMAILS if 'test' in email.lower()]
    if test_emails_in_list:
        raise RuntimeError(f"SECURITY ERROR: Test admin emails found in production: {test_emails_in_list}")

# Note: Test accounts are automatically added in test environments only
# Admins have full access to:
# - All participant data (current and historical years)
# - Area leader assignment and management
# - System configuration and user management
# - Data export and reporting functions