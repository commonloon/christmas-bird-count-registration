# Updated by Claude AI on 2026-10-22
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
MAX_404_PER_MINUTE = int(os.getenv('MAX_404_PER_MINUTE', 12))

# URLs to exclude from 404 counting (common browser resource requests)
# These are automatically requested by browsers and shouldn't count as violations
EXCLUDED_404_PATHS = {
    '/favicon.ico',
    '/apple-touch-icon.png',
    '/apple-touch-icon-precomposed.png',
    '/robots.txt',  # Also commonly requested
    '/sitemap.xml'  # Also commonly requested
}

# Block duration in hours
BLOCK_DURATION_HOURS = int(os.getenv('BLOCK_DURATION_HOURS', 48))

# Honeypot feature flag
HONEYPOT_ENABLED = os.getenv('HONEYPOT_ENABLED', 'true').lower() == 'true'

# Cache settings for blocked IP lookups
CACHE_SIZE = int(os.getenv('IP_BLOCK_CACHE_SIZE', 1000))
CACHE_TTL_SECONDS = int(os.getenv('IP_BLOCK_CACHE_TTL', 300))  # 5 minutes

# Violation tracking settings
VIOLATION_WINDOW_SECONDS = 60  # Fixed window for 404 counting (stored in Firestore, see services/ip_blocker.py)

# Admin and logging settings
ENABLE_BLOCK_LOGGING = True  # Log all blocks to Cloud Logging

# Paths that only vulnerability scanners request: secret/config files, VCS and cloud-credential
# directories, CMS/framework admin endpoints, PHP files (this app serves none), backup archives.
# Checked only for requests that matched no route (the 404 handler), so a real route can never
# be caught by it; a match blocks the IP immediately instead of waiting for MAX_404_PER_MINUTE.
PROBE_PATH_PATTERN = (
    r'(^|/)\.(?!well-known)'   # any dotfile/dot-directory: .env, .git, .aws, .claude, .github, ...
    r'|^/(wp-admin|wp-login|wp-content|wp-includes|wp-json|wordpress|xmlrpc\.php|phpmyadmin|pma|cgi-bin|vendor/phpunit'
    r'|actuator|solr|kibana|jenkins|manager/html|boaform|HNAP1|owa|ecp|server-status|fpm-status|_profiler)(/|$)'
    r'|\.php\d?$'
    r'|\.(sql|bak|old|orig|save|swp|tar|tgz|gz|zip|7z|rar|env)$'
    r'|(^|/)(phpinfo|Dockerfile|env|env\.js|env\.txt|config\.(js|json|ya?ml|env)|settings(\.local)?\.json'
    r'|appsettings[\w.]*\.json|credentials(\.\w+)?|secrets?\.(json|ya?ml)|composer\.(json|lock)'
    r'|package\.json|docker-compose\.ya?ml)(/|$)'
)
