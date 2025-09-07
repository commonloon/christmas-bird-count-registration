# Admin email whitelist for Vancouver CBC Registration App
# Update this list each year as admin responsibilities change

ADMIN_EMAILS = [
    'birdcount@naturevancouver.ca',       # deployment account owner
    'webmaster@naturevancouver.ca',       # webmaster
    'kelvin@naturevancouver.ca',          # Count coordinator
    'michelle@naturevancouver.ca',        # Count coordinator
]

def is_admin(email: str) -> bool:
    """Check if an email address has admin privileges."""
    if not email:
        return False
    return email.lower().strip() in [admin.lower() for admin in ADMIN_EMAILS]

def get_admin_emails() -> list:
    """Get list of all admin email addresses."""
    return ADMIN_EMAILS.copy()

# Note: Update this list annually when deploying for each year's count
# Admins have full access to:
# - All participant data (current and historical years)
# - Area leader assignment and management
# - System configuration and user management
# - Data export and reporting functions