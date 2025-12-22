# Club-specific settings for email customization
# Updated by Claude AI on 2025-12-18

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
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import pytz

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
    2026: '2026-12-19',
    2027: '2027-12-18',
    2028: '2028-12-16',
    2029: '2029-12-15',
}

# Registration Window Configuration
# Number of days before the count to close registration
# Valid range: 0-21 days
# - Negative values are treated as positive (absolute value)
# - Values > 21 or invalid values default to 1
# - Zero is allowed (registration closes at 00:00:01 on count day)
# Example: If count is Dec 20 and REGISTRATION_CLOSES = 1, registration closes at 00:00:01 on Dec 19
REGISTRATION_CLOSES = 1

# Number of months before the count to open registration
# Valid range: Must be positive integer
# - Invalid or non-positive values default to 3
# Example: If count is Dec 20 and REGISTRATION_OPENS = 3, registration opens on Sept 20
REGISTRATION_OPENS = 3

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

# Registration Window Helper Functions

def _get_validated_registration_closes():
    """Get validated REGISTRATION_CLOSES value with proper bounds checking."""
    try:
        value = abs(int(REGISTRATION_CLOSES))  # Treat negative as positive
        if value > 21:
            return 1  # Default for out of bounds
        return value
    except (ValueError, TypeError):
        return 1  # Default for invalid values

def _get_validated_registration_opens():
    """Get validated REGISTRATION_OPENS value."""
    try:
        value = int(REGISTRATION_OPENS)
        if value <= 0:
            return 3  # Default for non-positive
        return value
    except (ValueError, TypeError):
        return 3  # Default for invalid values

def _get_pacific_now():
    """Get current datetime in Pacific timezone."""
    pacific_tz = pytz.timezone(DISPLAY_TIMEZONE)
    return datetime.now(pacific_tz)

def _make_date_pacific_aware(date_str):
    """Convert date string to timezone-aware datetime at start of day in Pacific time.

    Args:
        date_str: Date string in 'YYYY-MM-DD' format

    Returns:
        Timezone-aware datetime at 00:00:01 in Pacific timezone, or None if invalid
    """
    try:
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
        pacific_tz = pytz.timezone(DISPLAY_TIMEZONE)
        # Set to 00:00:01 (one second after midnight)
        aware_datetime = pacific_tz.localize(datetime(date_obj.year, date_obj.month, date_obj.day, 0, 0, 1))
        return aware_datetime
    except (ValueError, TypeError):
        return None

def get_current_registration_year():
    """Get the count year that registration is currently open for, or None if closed.

    Returns:
        Integer year if registration is open, None if closed
    """
    now = _get_pacific_now()
    closes_days = _get_validated_registration_closes()
    opens_months = _get_validated_registration_opens()

    for count_year, count_date_str in YEARLY_COUNT_DATES.items():
        count_date = _make_date_pacific_aware(count_date_str)
        if not count_date:
            continue

        # Calculate registration window
        opening = count_date - relativedelta(months=opens_months)
        closing = count_date - timedelta(days=closes_days)

        if opening <= now < closing:
            return count_year

    return None

def get_registration_status():
    """Get detailed registration status information.

    Returns:
        Dictionary with keys:
        - is_open: Boolean indicating if registration is open
        - count_year: Year registration is open for (None if closed)
        - days_until_closing: Days until registration closes (None if closed)
        - closing_date: Date when registration closes (None if closed)
        - closed_message: Message to display when closed (None if open)
    """
    current_year = get_current_registration_year()

    if current_year is None:
        # Registration is closed
        org_vars = get_organization_variables()
        closed_message = (
            f"Thank you for your interest in {org_vars['count_event_name']}. "
            f"Registration for the count has closed for the season. "
            f"Registration should reopen a few months prior to the next count. "
            f"Please email {org_vars['count_contact']} with any inquiries."
        )
        return {
            'is_open': False,
            'count_year': None,
            'days_until_closing': None,
            'closing_date': None,
            'closed_message': closed_message
        }

    # Registration is open
    now = _get_pacific_now()
    count_date_str = YEARLY_COUNT_DATES[current_year]
    count_date = _make_date_pacific_aware(count_date_str)
    closes_days = _get_validated_registration_closes()

    closing_date = count_date - timedelta(days=closes_days)
    days_until_closing = (closing_date.date() - now.date()).days

    return {
        'is_open': True,
        'count_year': current_year,
        'days_until_closing': days_until_closing,
        'closing_date': closing_date,
        'closed_message': None
    }

def is_registration_open():
    """Simple check if registration is currently open.

    Returns:
        Boolean indicating if registration is open
    """
    return get_current_registration_year() is not None

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