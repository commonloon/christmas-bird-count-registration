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

# UI Customization - Customize these for your specific bird count
IS_CBC = True  # True for Christmas Bird Counts, False for other counts (Spring, etc.)
COUNT_EXPERIENCE_LABEL = "CBC Experience"  # Label for the experience field
FEEDER_COUNTER_LABEL = "Count birds at my home feeder"  # Label for feeder counter option
NOTES_PLACEHOLDER_EXAMPLE = "I would prefer to be assigned to an area in East Vancouver"  # Example text for notes field

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
REGISTRATION_OPENS = 4

# Email Configuration
FROM_EMAIL = "cbc@naturevancouver.ca"  # Default sender email address

# Timezone Configuration
# For list of valid timezone values, see: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones
# Common North American examples: America/Vancouver, America/Toronto, America/New_York, America/Chicago
DISPLAY_TIMEZONE = "America/Vancouver"  # Used for email timestamps and scheduled tasks

# Test Mode Configuration
TEST_RECIPIENT = "birdcount@naturevancouver.ca"  # All test server emails redirect here

# Logo Configuration - Vancouver's own logo, set on its circle row (circles.logo_path),
# not used as a fallback for other circles (see get_logo_url(), which returns None when
# a circle hasn't set its own). Kept as a module constant only for tests/installation/
# test_deployment.py's import; not otherwise referenced by the live app.
LOGO_PATH = "/static/icons/NV_logo.png"  # Path relative to base URL


def _active_circle():
    """The circle resolved for the current request (see app.py's resolve_circle
    before_request hook), or None outside a request context / before resolution has
    run (scripts, tests) - callers fall back to this module's constants in that case.
    """
    try:
        from flask import g, has_request_context
        if has_request_context():
            return getattr(g, 'circle', None)
    except RuntimeError:
        pass
    return None


_NO_DEFAULT = object()


def _circle_value(key, default=_NO_DEFAULT, unset_default=None):
    """Get a config value from the active circle.

    Two distinct "no value" cases, handled differently:

    1. No circle resolved AT ALL (outside a request context, or g.circle is None
       on the landing host) - this is a multi-circle platform with no default/
       fallback circle, so there is nothing to substitute. Raises unless the
       caller explicitly opts into a real fallback via `default` - currently
       only display_timezone does this (see get_organization_variables()),
       since a slightly-wrong timezone for a not-yet-multi-timezone deployment
       is low stakes compared to leaking organization identity. Callers with no
       request in flight (scripts, tests) must push a request context for one
       specific circle first - see test/email_generator.py's
       _push_circle_context() for the established pattern.

    2. A real circle IS resolved, but this particular field was never filled in
       for it - most of these columns are nullable (models/db.py's Circle table),
       so this is routine for a newly-created or partially-configured circle, not
       a bug. Never falls back to Vancouver's value here either (same reasoning),
       but crashing the whole site over one blank optional field would be worse
       than showing something neutral - returns `unset_default` (plain empty/
       generic, never another circle's real data).
    """
    circle = _active_circle()
    if circle is not None:
        value = circle.get(key)
        return value if value is not None else unset_default
    if default is _NO_DEFAULT:
        raise RuntimeError(
            f"No circle resolved - '{key}' has no cross-circle default. This is a "
            f"multi-circle platform; every caller needs a real, resolved circle "
            f"(see app.py's resolve_circle() / test/email_generator.py's "
            f"_push_circle_context() for scripts)."
        )
    return default


# URL Functions (circle/environment-aware)
def get_base_url():
    """The current circle's externally-visible base URL (scheme+host, no
    trailing slash).

    Prefers the actual request's own Host header when in a request context -
    this is always correct regardless of CBC vs non-CBC subdomain level, test
    vs prod, or which circle, since it's just echoing back whatever domain
    was actually used to reach this request (see app.py's resolve_circle).
    Outside a request (no known circle at all - a standalone script/test),
    falls back to the landing page's own domain rather than guessing any one
    circle's URL.
    """
    from flask import request, has_request_context
    if has_request_context():
        try:
            return request.host_url.rstrip('/')
        except RuntimeError:
            pass
    from app import LANDING_HOST
    return f'https://{LANDING_HOST}'

def get_registration_url():
    """Get environment-appropriate registration URL (base URL)."""
    return get_base_url()

def get_admin_url():
    """Get environment-appropriate admin interface URL.

    Path is /bigbird, not /admin - deliberately, so bots that default to
    guessing "/admin" don't land on the real admin panel (see routes/main.py's
    honeypot_trap, which now catches /admin and /admin/* instead).
    """
    return f"{get_base_url()}/bigbird"

def get_leader_url():
    """Get environment-appropriate leader dashboard URL."""
    return f"{get_base_url()}/leader"

def get_logo_url():
    """This circle's logo URL, or None if it hasn't uploaded one.

    No fallback to another circle's logo (e.g. Vancouver's) - callers must
    handle None explicitly (show a placeholder, omit an <img> tag, etc.)
    rather than silently displaying the wrong organization's branding.

    Checks logo_content_type, not the logo bytes themselves (Circle.logo_data
    is a deferred column - see models/db.py - fetching it here would trigger
    an unnecessary lazy SELECT just to decide whether a logo exists).
    """
    circle = _active_circle()
    if not circle or not circle.get('logo_content_type'):
        return None
    return f"{get_base_url()}/api/circles/{circle['slug']}/logo"

def get_count_date(year=None):
    """Get formatted count date with day of week for the given year.

    Args:
        year: Year to get count date for. If None, uses current year.

    Returns:
        Formatted string like "Saturday, December 14, 2024" or "TBD" if not configured.
    """
    if year is None:
        year = datetime.now().year

    date_str = _circle_value('yearly_count_dates').get(year)
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
    """Get all organization variables for email template rendering.

    Requires a resolved circle (raises RuntimeError otherwise, via _circle_value) -
    there is no cross-circle default for any of these. display_timezone is the
    sole exception to that no-circle-at-all case, still falling back to this
    module's constant - see _circle_value's docstring for why.

    Most of these columns are nullable (models/db.py's Circle table) - a real,
    correctly-resolved circle that simply hasn't filled in an optional field
    (very normal for a newly-created circle) gets a plain, neutral unset_default
    below, never Vancouver's actual value - see _circle_value's docstring, case 2.
    'name'/'circle_name'/'is_cbc'/'display_timezone' are NOT NULL at the DB level,
    so they need no unset_default; they can only be missing via the no-circle-at-
    all case, which correctly raises instead.
    """
    return {
        'organization_name': _circle_value('name'),
        'organization_website': _circle_value('website', unset_default=''),
        'organization_contact': _circle_value('contact', unset_default=''),
        'count_contact': _circle_value('count_contact', unset_default=''),
        # Unset count_event_name falls back to this circle's own circle_name
        # (NOT NULL) - its own real data, not another circle's.
        'count_event_name': _circle_value('count_event_name', unset_default=_circle_value('circle_name')),
        'count_info_url': _circle_value('count_info_url', unset_default=''),
        # None (not '') for from_email/test_recipient - lets send_email()'s own
        # env-configured fallback apply, same as it already does for callers
        # outside any circle context (e.g. the landing host's multi-circle email).
        'from_email': _circle_value('from_email', unset_default=None),
        'registration_url': get_registration_url(),
        'admin_url': get_admin_url(),
        'leader_url': get_leader_url(),
        'logo_url': get_logo_url(),
        'test_recipient': _circle_value('test_recipient', unset_default=None),
        'display_timezone': _circle_value('display_timezone', DISPLAY_TIMEZONE),
        'is_cbc': _circle_value('is_cbc'),
        'count_experience_label': _circle_value('count_experience_label', unset_default='Experience'),
        'feeder_counter_label': _circle_value('feeder_counter_label', unset_default='Count birds at my home feeder'),
        'notes_placeholder_example': _circle_value('notes_placeholder_example', unset_default='')
    }

# Registration Window Helper Functions

def _get_validated_registration_closes():
    """Get validated registration-closes-days value with proper bounds checking."""
    try:
        value = abs(int(_circle_value('registration_closes_days')))  # Treat negative as positive
        if value > 21:
            return 1  # Default for out of bounds
        return value
    except (ValueError, TypeError):
        return 1  # Default for invalid values

def _get_validated_registration_opens():
    """Get validated registration-opens-months value."""
    try:
        value = int(_circle_value('registration_opens_months'))
        if value <= 0:
            return 3  # Default for non-positive
        return value
    except (ValueError, TypeError):
        return 3  # Default for invalid values

def _get_pacific_now():
    """Get current datetime in the active circle's timezone (named for its historical
    Pacific-only default; DISPLAY_TIMEZONE/circle timezone may differ per circle)."""
    pacific_tz = pytz.timezone(_circle_value('display_timezone', DISPLAY_TIMEZONE))
    return datetime.now(pacific_tz)

def _make_date_pacific_aware(date_str):
    """Convert date string to timezone-aware datetime at start of day in the active
    circle's timezone.

    Args:
        date_str: Date string in 'YYYY-MM-DD' format

    Returns:
        Timezone-aware datetime at 00:00:01 in the circle's timezone, or None if invalid
    """
    try:
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
        pacific_tz = pytz.timezone(_circle_value('display_timezone', DISPLAY_TIMEZONE))
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

    for count_year, count_date_str in _circle_value('yearly_count_dates', YEARLY_COUNT_DATES).items():
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
    count_date_str = _circle_value('yearly_count_dates', YEARLY_COUNT_DATES)[current_year]
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