# Updated by Claude AI on 2025-10-22
"""
Timezone conversion utilities for consistent datetime handling across emails and templates.

Provides conversion from UTC to configured display timezone for email generation
and template rendering.
"""

from datetime import datetime, timezone
import pytz
import logging

logger = logging.getLogger(__name__)


def get_timezone_label(tz_name: str) -> str:
    """
    Get a user-friendly timezone label from timezone name.

    Args:
        tz_name: Timezone name from IANA tz database (e.g., 'America/Vancouver')

    Returns:
        Friendly timezone label (e.g., 'Pacific Time')
    """
    timezone_labels = {
        'America/Vancouver': 'Pacific Time',
        'America/Los_Angeles': 'Pacific Time',
        'America/Denver': 'Mountain Time',
        'America/Chicago': 'Central Time',
        'America/Toronto': 'Eastern Time',
        'America/New_York': 'Eastern Time',
        'America/Mexico_City': 'Central Time',
        'Canada/Pacific': 'Pacific Time',
        'Canada/Mountain': 'Mountain Time',
        'Canada/Central': 'Central Time',
        'Canada/Eastern': 'Eastern Time',
        'UTC': 'UTC',
        'Etc/UTC': 'UTC',
    }

    # Return custom label if defined, otherwise extract from timezone name
    if tz_name in timezone_labels:
        return timezone_labels[tz_name]

    # Fallback: extract the last part of the timezone name
    # E.g., 'America/Vancouver' -> 'Vancouver'
    return tz_name.split('/')[-1] if '/' in tz_name else tz_name


def convert_to_display_timezone(utc_datetime: datetime) -> tuple:
    """
    Convert UTC datetime to configured display timezone.

    Args:
        utc_datetime: datetime object in UTC (should be timezone-aware or assumed UTC)

    Returns:
        Tuple of (converted_datetime, timezone_label)
        - converted_datetime: datetime object in display timezone (timezone-aware)
        - timezone_label: friendly label like 'Pacific Time'

    Example:
        >>> utc_dt = datetime.now(timezone.utc)
        >>> converted_dt, label = convert_to_display_timezone(utc_dt)
        >>> print(f"Registered on {converted_dt.strftime('%B %d, %Y at %H:%M')} {label}")
        Registered on October 22, 2025 at 19:27 Pacific Time
    """
    try:
        from config.organization import DISPLAY_TIMEZONE
        tz_name = DISPLAY_TIMEZONE
    except ImportError:
        logger.warning("Could not import DISPLAY_TIMEZONE from config, defaulting to America/Vancouver")
        tz_name = 'America/Vancouver'

    try:
        # Ensure input is timezone-aware (assume UTC if naive)
        if utc_datetime.tzinfo is None:
            utc_datetime = utc_datetime.replace(tzinfo=timezone.utc)

        # Get the target timezone
        target_tz = pytz.timezone(tz_name)

        # Convert to target timezone
        converted_datetime = utc_datetime.astimezone(target_tz)

        # Get friendly label
        timezone_label = get_timezone_label(tz_name)

        return converted_datetime, timezone_label

    except Exception as e:
        logger.error(f"Error converting timezone {tz_name}: {e}")
        # Fallback: return original datetime with label
        timezone_label = get_timezone_label(tz_name)
        return utc_datetime, timezone_label
