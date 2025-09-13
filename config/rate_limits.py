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
    
    # Authentication endpoints
    'auth': '5 per minute',               # Login attempts, OAuth callbacks
}

# Storage backend configuration for Flask-Limiter
# Using in-memory storage (simple and sufficient for single-instance Cloud Run)
LIMITER_STORAGE_URL = 'memory://'

# Default rate limit for any endpoint not specifically configured
DEFAULT_RATE_LIMIT = '20 per minute'

def get_rate_limit_key():
    """
    Generate rate limit key based on client IP.
    Uses X-Forwarded-For header since we're behind Cloud Run proxy.
    """
    from flask import request
    
    # Use X-Forwarded-For header if behind a proxy (like Cloud Run)
    forwarded_for = request.headers.get('X-Forwarded-For')
    if forwarded_for:
        # Take the first IP in the chain (original client)
        client_ip = forwarded_for.split(',')[0].strip()
    else:
        client_ip = request.remote_addr or 'unknown'
    
    return client_ip

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
    }
    
    return messages.get(endpoint_type, 'Rate limit exceeded. Please wait before trying again.')