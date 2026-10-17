# Updated by Claude AI on 2026-10-16
"""Next-count-date selection for the landing-page circle listings."""
from datetime import date, datetime
from zoneinfo import ZoneInfo

TBA = 'TBA'


def next_count_date(yearly_count_dates, display_timezone, today=None):
    """Pick the date to show for a circle on the landing page.

    Returns (text, is_past): the earliest configured date on or after today (in the
    circle's own timezone), else the most recent past one with is_past=True, else
    ('TBA', False) when no usable date is configured. Unparseable entries are
    ignored rather than failing the whole listing.
    """
    if today is None:
        try:
            today = datetime.now(ZoneInfo(display_timezone)).date()
        except Exception:
            today = date.today()

    parsed = []
    for value in (yearly_count_dates or {}).values():
        try:
            parsed.append(datetime.strptime(value, '%Y-%m-%d').date())
        except (ValueError, TypeError):
            continue

    upcoming = sorted(d for d in parsed if d >= today)
    if upcoming:
        return _format(upcoming[0]), False
    if parsed:
        return _format(max(parsed)), True
    return TBA, False


def _format(d):
    # "Dec 20, 2026" - strftime's %d would zero-pad, so build the day by hand.
    return f"{d.strftime('%b')} {d.day}, {d.year}"
