import os
from datetime import datetime
import pytz


class Config:
    """Base configuration class."""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-key-change-in-production'

    # Google Cloud settings
    GOOGLE_CLOUD_PROJECT = os.environ.get('GOOGLE_CLOUD_PROJECT')

    # Application settings
    REGISTRATION_OPEN = True
    CURRENT_COUNT_YEAR = datetime.now().year

    # Email settings (for notifications)
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')

    # Admin email for notifications
    ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', 'admin@naturevancouver.ca')


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True


class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False


# Configuration mapping
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}


# Timezone helper functions
def get_display_timezone():
    """Get the timezone for displaying dates to users."""
    tz_name = os.environ.get('DISPLAY_TIMEZONE', 'America/Vancouver')
    return pytz.timezone(tz_name)


def get_local_time(utc_datetime):
    """Convert UTC datetime to local display time."""
    if utc_datetime is None:
        return None
    
    display_tz = get_display_timezone()
    
    # Handle timezone-aware vs timezone-naive datetimes
    if utc_datetime.tzinfo is None:
        # Assume UTC if no timezone info
        utc_datetime = pytz.UTC.localize(utc_datetime)
    
    return utc_datetime.astimezone(display_tz)


def get_utc_datetime(local_datetime=None):
    """Convert local datetime to UTC, or get current UTC time."""
    if local_datetime is None:
        return datetime.utcnow().replace(tzinfo=pytz.UTC)
    
    display_tz = get_display_timezone()
    
    # If naive datetime, assume it's in display timezone
    if local_datetime.tzinfo is None:
        local_datetime = display_tz.localize(local_datetime)
    
    return local_datetime.astimezone(pytz.UTC)