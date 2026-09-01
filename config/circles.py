# Updated by Claude AI on 2026-08-31
import os

from models.db import DEFAULT_CIRCLE_SLUG


def get_default_circle_slug():
    """The circle slug to use outside a resolved request context (scripts, tests)."""
    return os.environ.get('DEFAULT_CIRCLE_SLUG', DEFAULT_CIRCLE_SLUG)
