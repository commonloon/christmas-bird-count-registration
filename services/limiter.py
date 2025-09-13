# Updated by Claude AI on 2025-09-12
"""
Shared rate limiter instance for the application.
This avoids circular import issues when using limiter in route blueprints.
"""

from flask_limiter import Limiter
from config.rate_limits import LIMITER_STORAGE_URL, DEFAULT_RATE_LIMIT, get_rate_limit_key

# Create a limiter instance that can be imported by routes
# The app will be bound to this later in app.py
limiter = Limiter(
    key_func=get_rate_limit_key,
    storage_uri=LIMITER_STORAGE_URL,
    default_limits=[DEFAULT_RATE_LIMIT]
)