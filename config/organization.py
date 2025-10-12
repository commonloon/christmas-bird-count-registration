# Club-specific settings for email customization
# Updated by Claude AI on 2025-10-12

"""
Organization configuration for Christmas Bird Count registration system.

This file contains club-specific settings that customize the email templates
and user-facing content for different bird count organizations.

To adapt this system for another club:
1. Update all the variables below with your organization's information
2. Ensure all URLs are valid and accessible
3. Test email delivery with your contact addresses
"""

from config.cloud import BASE_URL_TEST, BASE_URL_PRODUCTION

# Organization Information
ORGANIZATION_NAME = "Nature Vancouver"
ORGANIZATION_WEBSITE = "https://naturevancouver.ca"
ORGANIZATION_CONTACT = "info@naturevancouver.ca"

# Christmas Bird Count Specific Information
COUNT_CONTACT = "cbc@naturevancouver.ca"
COUNT_EVENT_NAME = "Vancouver Christmas Bird Count"
COUNT_INFO_URL = "https://naturevancouver.ca/birding/vancouver-area-christmas-bird-count/"

# Email Configuration
FROM_EMAIL = "cbc@naturevancouver.ca"  # Default sender email address

# Timezone Configuration
# For list of valid timezone values, see: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones
# Common North American examples: America/Vancouver, America/Toronto, America/New_York, America/Chicago
DISPLAY_TIMEZONE = "America/Vancouver"  # Used for email timestamps and scheduled tasks

# Test Mode Configuration
TEST_RECIPIENT = "birdcount@naturevancouver.ca"  # All test server emails redirect here

# Logo Configuration
LOGO_PATH = "/static/icons/NV_logo.png"  # Path relative to base URL

# URL Functions (environment-aware)
def get_base_url():
    """Get environment-appropriate base URL."""
    from config.email_settings import is_test_server
    if is_test_server():
        return BASE_URL_TEST
    else:
        return BASE_URL_PRODUCTION

def get_registration_url():
    """Get environment-appropriate registration URL (base URL)."""
    return get_base_url()

def get_admin_url():
    """Get environment-appropriate admin interface URL."""
    return f"{get_base_url()}/admin"

def get_leader_url():
    """Get environment-appropriate leader dashboard URL."""
    return f"{get_base_url()}/leader"

def get_logo_url():
    """Get environment-appropriate logo URL."""
    return f"{get_base_url()}{LOGO_PATH}"

# Template variable dictionary for email rendering
def get_organization_variables():
    """Get all organization variables for email template rendering."""
    return {
        'organization_name': ORGANIZATION_NAME,
        'organization_website': ORGANIZATION_WEBSITE,
        'organization_contact': ORGANIZATION_CONTACT,
        'count_contact': COUNT_CONTACT,
        'count_event_name': COUNT_EVENT_NAME,
        'count_info_url': COUNT_INFO_URL,
        'from_email': FROM_EMAIL,
        'registration_url': get_registration_url(),
        'admin_url': get_admin_url(),
        'leader_url': get_leader_url(),
        'logo_url': get_logo_url(),
        'test_recipient': TEST_RECIPIENT,
        'display_timezone': DISPLAY_TIMEZONE
    }

# Helper function for other clubs
def validate_organization_config():
    """Validate that all required organization settings are configured."""
    required_settings = [
        'ORGANIZATION_NAME',
        'ORGANIZATION_WEBSITE',
        'ORGANIZATION_CONTACT',
        'COUNT_CONTACT',
        'COUNT_EVENT_NAME',
        'COUNT_INFO_URL'
    ]

    missing_settings = []
    for setting in required_settings:
        if not globals().get(setting):
            missing_settings.append(setting)

    if missing_settings:
        raise ValueError(f"Missing required organization settings: {', '.join(missing_settings)}")

    return True