# Club-specific settings for email customization
# Updated by Claude AI on 2025-10-30

"""
Organization configuration for Christmas Bird Count registration system.

This file contains club-specific settings that customize the email templates
and user-facing content for different bird count organizations.

To adapt this system for another club:
1. Update all the variables below with your organization's information
2. Ensure all URLs are valid and accessible
3. Test email delivery with your contact addresses
"""

from config.cloud import TEST_BASE_URL, PRODUCTION_BASE_URL
from datetime import datetime

# Organization Information
ORGANIZATION_NAME = "Nature Vancouver"
ORGANIZATION_WEBSITE = "https://naturevancouver.ca"
ORGANIZATION_CONTACT = "info@naturevancouver.ca"

# Christmas Bird Count Specific Information
COUNT_CONTACT = "cbc@naturevancouver.ca"
COUNT_EVENT_NAME = "Vancouver Christmas Bird Count"
COUNT_INFO_URL = "https://naturevancouver.ca/birding/vancouver-area-christmas-bird-count/"

# Year-specific count dates (YYYY-MM-DD format)
# Update annually with the scheduled count date for each year
YEARLY_COUNT_DATES = {
    2024: '2024-12-14',
    2025: '2025-12-20',
}

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
        return TEST_BASE_URL
    else:
        return PRODUCTION_BASE_URL

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

def get_count_date(year=None):
    """Get formatted count date with day of week for the given year.

    Args:
        year: Year to get count date for. If None, uses current year.

    Returns:
        Formatted string like "Saturday, December 14, 2024" or "TBD" if not configured.
    """
    if year is None:
        year = datetime.now().year

    date_str = YEARLY_COUNT_DATES.get(year)
    if not date_str:
        return "TBD"

    try:
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
        # Format: "Saturday, December 14, 2024"
        return date_obj.strftime('%A, %B %d, %Y')
    except ValueError:
        return "TBD"

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