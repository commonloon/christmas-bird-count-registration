# Updated by Claude AI on 2025-12-09
"""
IP blocking configuration for bot defense.
Defines thresholds, durations, and cache settings for the IP blocking system.
"""

import os

def is_test_mode():
    """Check if running in test mode based on environment variable."""
    return os.getenv('TEST_MODE', '').lower() == 'true'

# 404 rate limiting threshold
# Number of 404 errors within VIOLATION_WINDOW_SECONDS that triggers a block
MAX_404_PER_MINUTE = int(os.getenv('MAX_404_PER_MINUTE', 3))

# Block duration in hours
BLOCK_DURATION_HOURS = int(os.getenv('BLOCK_DURATION_HOURS', 48))

# Honeypot feature flag
HONEYPOT_ENABLED = os.getenv('HONEYPOT_ENABLED', 'true').lower() == 'true'

# Cache settings for blocked IP lookups
CACHE_SIZE = int(os.getenv('IP_BLOCK_CACHE_SIZE', 1000))
CACHE_TTL_SECONDS = int(os.getenv('IP_BLOCK_CACHE_TTL', 300))  # 5 minutes

# Violation tracking settings
VIOLATION_TRACKER_SIZE = int(os.getenv('VIOLATION_TRACKER_SIZE', 5000))
VIOLATION_WINDOW_SECONDS = 60  # Sliding window for 404 counting

# Admin and logging settings
ENABLE_BLOCK_LOGGING = True  # Log all blocks to Cloud Logging
MAX_VIOLATION_HISTORY = 10   # Store last N URLs per IP in block record
