# Updated by Claude AI on 2026-10-20
"""Participation-count tiers used to colour area maps and buttons.

A circle's tiers are defined by two cut-offs, each the lowest count of its tier:
counts below `medium_from` are 'low', counts from `medium_from` up to (but not
including) `high_from` are 'medium', and counts from `high_from` up are 'high'. Defined
that way the three ranges can't overlap or leave a gap. Circles that haven't chosen
their own values (NULL columns) use the defaults. Viewers can try other values in the
browser (static/js/count-thresholds.js); that never changes what is stored here.
"""
DEFAULT_MEDIUM_FROM = 4
DEFAULT_HIGH_FROM = 8

# Generous upper bound - just stops absurd values, not a real-world limit
MAX_THRESHOLD = 999


def get_thresholds(circle):
    """(medium_from, high_from) for a circle dict (or None), defaults where unset."""
    circle = circle or {}
    medium = circle.get('map_medium_from')
    high = circle.get('map_high_from')
    if medium is None or high is None:
        return DEFAULT_MEDIUM_FROM, DEFAULT_HIGH_FROM
    return medium, high


def tier_for_count(count, medium_from, high_from):
    """'low', 'med' or 'high' for a participant count."""
    if count >= high_from:
        return 'high'
    if count >= medium_from:
        return 'med'
    return 'low'


def parse_thresholds(medium_raw, high_raw):
    """Parse the two submitted values. Returns (medium, high, error): both None with no
    error when both are blank (use the defaults); error is a message otherwise unless
    both are whole numbers with 1 <= medium < high <= MAX_THRESHOLD."""
    medium_raw = (medium_raw or '').strip()
    high_raw = (high_raw or '').strip()
    if not medium_raw and not high_raw:
        return None, None, None
    try:
        medium, high = int(medium_raw), int(high_raw)
    except ValueError:
        return None, None, 'Map colour thresholds must be whole numbers (or both left blank for the defaults).'
    if not 1 <= medium < high <= MAX_THRESHOLD:
        return None, None, (f'Map colour thresholds must satisfy 1 ≤ medium < high ≤ {MAX_THRESHOLD}.')
    return medium, high, None
