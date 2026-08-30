# Helpers for per-circle static assets that aren't (yet) worth storing in the DB.
# See the multi-circle-architecture note: area boundary GeoJSON stays a per-circle
# static file for now (only Vancouver has real data), not a DB blob - deliberately
# the "easy path", but kept behind this one function so it can move into the DB
# later without touching call sites.
import os

from models.db import DEFAULT_CIRCLE_SLUG


def get_default_circle_slug():
    """The circle slug to use outside a resolved request context (scripts, tests)."""
    return os.environ.get('DEFAULT_CIRCLE_SLUG', DEFAULT_CIRCLE_SLUG)


def get_area_boundaries_filename(circle_slug):
    """Filename (relative to static/data/) of a circle's area boundary GeoJSON."""
    return f'area_boundaries_{circle_slug}.json'
