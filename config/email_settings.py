# Updated by Claude AI on 2026-01-12
# Email service configuration and SMTP settings
import os
from flask import request
from typing import Dict, Any, Optional
from config.organization import ORGANIZATION_NAME


# Email provider configurations - provider-agnostic design
EMAIL_PROVIDERS = {
    'smtp2go': {
        'smtp_server': 'mail.smtp2go.com',
        'smtp_port': 587,
        'use_tls': True,
        'username_env': 'SMTP2GO_USERNAME',
        'password_env': 'SMTP2GO_PASSWORD',
        'description': 'SMTP2GO email service'
    },
    'gmail': {
        'smtp_server': 'smtp.gmail.com',
        'smtp_port': 587,
        'use_tls': True,
        'username_env': 'GMAIL_USERNAME',
        'password_env': 'GMAIL_PASSWORD',
        'description': 'Gmail SMTP service'
    },
    'sendgrid': {
        'smtp_server': 'smtp.sendgrid.net',
        'smtp_port': 587,
        'use_tls': True,
        'username_env': 'SENDGRID_USERNAME',
        'password_env': 'SENDGRID_API_KEY',
        'description': 'SendGrid SMTP service'
    },
    'mailgun': {
        'smtp_server': 'smtp.mailgun.org',
        'smtp_port': 587,
        'use_tls': True,
        'username_env': 'MAILGUN_USERNAME',
        'password_env': 'MAILGUN_PASSWORD',
        'description': 'Mailgun SMTP service'
    }
}


def get_email_config() -> Optional[Dict[str, Any]]:
    """
    Get email configuration based on environment variables.

    Returns:
        dict: Email configuration with server, port, credentials, etc.
        None: If email provider is not configured or credentials missing
    """
    # Get provider from environment (default to smtp2go)
    provider = os.environ.get('EMAIL_PROVIDER', 'smtp2go').lower()

    if provider not in EMAIL_PROVIDERS:
        raise ValueError(f"Unknown email provider: {provider}. Available providers: {list(EMAIL_PROVIDERS.keys())}")

    provider_config = EMAIL_PROVIDERS[provider]

    # Get credentials from environment variables and strip whitespace
    username = os.environ.get(provider_config['username_env'])
    password = os.environ.get(provider_config['password_env'])

    if username:
        username = username.strip()
    if password:
        password = password.strip()

    if not username or not password:
        return None

    # Import FROM_EMAIL from organization config
    from config.organization import FROM_EMAIL

    # Build complete configuration
    config = {
        'smtp_server': provider_config['smtp_server'],
        'smtp_port': provider_config['smtp_port'],
        'use_tls': provider_config['use_tls'],
        'smtp_username': username,
        'smtp_password': password,
        'from_email': os.environ.get('FROM_EMAIL', FROM_EMAIL),
        'provider_name': provider,
        'provider_description': provider_config['description'],
        'test_mode': is_test_server()
    }

    return config


def get_available_providers() -> list:
    """
    Get list of available email providers.

    Returns:
        list: List of available provider names with descriptions
    """
    return [
        {
            'name': name,
            'description': config['description'],
            'server': config['smtp_server'],
            'port': config['smtp_port']
        }
        for name, config in EMAIL_PROVIDERS.items()
    ]


def is_test_server() -> bool:
    """Detect if running on test server for email trigger functionality."""
    # Check environment variable first
    if os.getenv('TEST_MODE', '').lower() == 'true':
        return True
    
    # Check if domain contains 'test' for deployed test server
    if request and hasattr(request, 'host') and 'test' in request.host.lower():
        return True
        
    return False


def get_admin_unassigned_url() -> str:
    """Get environment-appropriate URL for admin unassigned page.

    DEPRECATED: Use get_organization_variables()['admin_url'] + '/unassigned' instead.
    This function remains for backward compatibility.
    """
    from config.organization import get_admin_url
    return f"{get_admin_url()}/unassigned"


def get_leader_dashboard_url() -> str:
    """Get environment-appropriate URL for leader dashboard.

    DEPRECATED: Use get_organization_variables()['leader_url'] instead.
    This function remains for backward compatibility.
    """
    from config.organization import get_leader_url
    return get_leader_url()


def get_logo_url() -> str:
    """Get environment-appropriate URL for organization logo.

    DEPRECATED: Use get_organization_variables()['logo_url'] instead.
    This function remains for backward compatibility.
    """
    from config.organization import get_logo_url as org_get_logo_url
    return org_get_logo_url()


def get_email_branding() -> dict:
    """Get complete email branding configuration with environment-specific logo URL."""
    from config.organization import get_logo_url as org_get_logo_url
    branding = EMAIL_BRANDING.copy()
    branding['logo_url'] = org_get_logo_url()
    return branding


# Email template configuration
EMAIL_TEMPLATES = {
    'team_update': 'emails/team_update.html',
    'weekly_summary': 'emails/weekly_summary.html', 
    'admin_digest': 'emails/admin_digest.html'
}

# Email subjects (with date prefix for all emails)
EMAIL_SUBJECTS = {
    'team_update': '{date} Vancouver CBC Area {area_code} Update',
    'weekly_summary': '{date} Vancouver CBC Area {area_code} Weekly Summary',
    'admin_digest': '{date} Vancouver CBC Unassigned Participants'
}

# Email branding configuration
EMAIL_BRANDING = {
    'organization_name': ORGANIZATION_NAME,
    'logo_url': None,  # Will be set based on environment
    'logo_alt': f'{ORGANIZATION_NAME} Logo',
    'primary_color': '#2e8b57',      # Sea green (matches logo)
    'secondary_color': '#1e5c3a',    # Darker green
    'accent_color': '#90ee90',       # Light green
    'background_color': '#f0fff0',   # Honeydew (very light green)
    'text_color': '#333',            # Dark gray for body text
    'badge_warning': '#ffc107',      # Yellow for "Interested" badges
}