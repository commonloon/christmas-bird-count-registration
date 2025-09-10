# Email service configuration and SMTP settings
import os
from flask import request
from typing import Dict, Any


def get_email_config() -> Dict[str, Any]:
    """Get email configuration based on environment."""
    return {
        'smtp_server': os.environ.get('SMTP_SERVER', 'smtp.gmail.com'),
        'smtp_port': int(os.environ.get('SMTP_PORT', 587)),
        'smtp_username': os.environ.get('SMTP_USERNAME'),
        'smtp_password': os.environ.get('SMTP_PASSWORD'),
        'from_email': os.environ.get('FROM_EMAIL', 'birdcount@naturevancouver.ca'),
        'test_mode': is_test_server()
    }


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
    """Get environment-appropriate URL for admin unassigned page."""
    if is_test_server():
        return 'https://cbc-test.naturevancouver.ca/admin/unassigned'
    else:
        return 'https://cbc-registration.naturevancouver.ca/admin/unassigned'


def get_leader_dashboard_url() -> str:
    """Get environment-appropriate URL for leader dashboard."""
    if is_test_server():
        return 'https://cbc-test.naturevancouver.ca/leader'
    else:
        return 'https://cbc-registration.naturevancouver.ca/leader'


# Email template configuration
EMAIL_TEMPLATES = {
    'team_update': 'emails/team_update.html',
    'weekly_summary': 'emails/weekly_summary.html', 
    'admin_digest': 'emails/admin_digest.html'
}

# Email subjects
EMAIL_SUBJECTS = {
    'team_update': 'Team Update for Vancouver CBC Area {area_code}',
    'weekly_summary': 'Weekly Team Summary for Vancouver CBC Area {area_code}',
    'admin_digest': 'Vancouver CBC Participants not assigned to a count area'
}