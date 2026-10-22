# Updated by Claude AI on 2025-09-12
"""
Rate limiting configuration for the application.
Designed to prevent DDoS while allowing legitimate batch operations.
"""

import os

def is_test_mode():
    """Check if running in test mode based on environment variable."""
    return os.getenv('TEST_MODE', '').lower() == 'true'

# Rate limit configurations - sized for ~10 concurrent users max
# Registration limit is higher in test mode to allow efficient test script execution
RATE_LIMITS = {
    # Public registration endpoint - allows batch entry but blocks bots
    'registration': '50 per minute' if is_test_mode() else '10 per minute',
    
    # API endpoints for map data and area information
    'api_general': '20 per minute',       # Plenty for 10 concurrent users browsing maps
    
    # Admin endpoints - moderate limits for small admin team
    'admin_general': '30 per minute',     # Dashboard, participant lists, browsing
    'admin_modify': '30 per minute',      # Adding/editing leaders, assigning participants (fast admin work)
    
    # Landing-page "Report a problem" form - emails every super-admin per submission,
    # so deliberately much tighter than the other public endpoints
    'problem_report': '20 per minute' if is_test_mode() else '3 per minute',

    # Authentication endpoints - higher in test mode: an automated browser suite can
    # legitimately trigger more than 5 login-related requests/minute (e.g. any
    # unauthenticated request to an admin/leader route redirects to /auth/login,
    # which Selenium follows as a real GET), and test mode is far less likely to be
    # running on a publicly reachable server than this was originally written for.
    'auth': '100 per minute' if is_test_mode() else '5 per minute',  # Login attempts, OAuth callbacks
}

# Storage backend configuration for Flask-Limiter
# Using in-memory storage (simple and sufficient for single-instance Cloud Run)
LIMITER_STORAGE_URL = 'memory://'

# Default rate limit for any endpoint not specifically configured
DEFAULT_RATE_LIMIT = '20 per minute'

def get_rate_limit_key():
    """
    Generate rate limit key based on client IP.

    Uses the connection's peer address (request.remote_addr), never the
    X-Forwarded-For header: a client can send any value in that header, which
    would hand it a fresh rate-limit bucket on every request. On the FullHost app
    node Apache sees the real client address directly (see services/ip_blocker.py's
    get_client_ip(), which this must stay consistent with). Updated by Claude AI on 2026-10-22.
    """
    from flask import request

    return request.remote_addr or 'unknown'

def get_rate_limit_message(endpoint_type: str) -> str:
    """
    Get user-friendly error message for different endpoint types.
    """
    messages = {
        'registration': 'Too many registration attempts. Please wait a moment before submitting again.',
        'api_general': 'Too many requests. Please wait a moment before refreshing.',
        'admin_general': 'Too many requests. Please wait a moment.',
        'admin_modify': 'Too many changes. Please wait a moment before making more modifications.',
        'auth': 'Too many authentication attempts. Please wait before trying again.',
        'problem_report': 'Too many reports. Please wait a minute before sending another.',
    }
    
    return messages.get(endpoint_type, 'Rate limit exceeded. Please wait before trying again.')