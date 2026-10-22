# Updated by Claude AI on 2026-10-22
"""
Bounded history of bot registration attempts, and the super-admin alerts built on it.

"Attempt" means a submission our own checks rejected: filled honeypot, missing/forged/
too-fast/expired form token, URL-bearing or over-long name, disposable email domain.
(Flask-WTF's CSRF 400s happen before our route runs, and real people trigger them
whenever a session expires, so they are not counted.)

Storage has hard ceilings that do not depend on attack volume:
  bot_attempt_hourly  (hour, circle, reason) -> count. Kept 30 days.
  bot_attempt_daily   (Pacific day, dimension, value) -> count. Dimensions total/circle/
                      reason are kept 400 days (long-term trend); ip/ip_prefix/user_agent/
                      email_domain 90 days. Each dimension holds at most 200 distinct
                      values per day - the rest fold into one '(other)' row.
  bot_attempt_sample  ring buffer of the last 200 attempts in full, for forensics. It holds
                      attacker-supplied text, so nothing from it is ever put in an email.
Each web process also stops writing after MAX_WRITES_PER_MINUTE and just counts what it
dropped, folding that count in with the next recorded attempt.

Alerts (run from the hourly `flask tick-scheduled-emails` cron, see scheduler_cli.py), to
the super-admins only:
  - a daily summary at 06:00 Pacific, only if the previous Pacific day had any attempt;
  - an alert when the previous full hour had more than ALERT_THRESHOLD attempts across all
    circles, at most one per ALERT_COOLDOWN_HOURS (the daily summary still covers the rest).
Email bodies contain only counts and a few short sanitized labels (never names or notes,
and user agents are reduced to a browser/OS family), so a bot cannot use them to relay text.
"""

import ipaddress
import logging
import re
import threading
from datetime import datetime, timedelta, timezone

import pytz
from sqlalchemy import bindparam, text

from config.admins import get_admin_emails
from config.database import get_db_session
from models.app_settings import AppSettingsModel
from models.db import get_engine
from services.email_service import email_service

logger = logging.getLogger(__name__)

PACIFIC = pytz.timezone('America/Vancouver')

SUMMARY_HOUR_LOCAL = 6
SUMMARY_WINDOW_HOURS = 3
ALERT_THRESHOLD = 10          # alert when the previous hour had MORE than this many
ALERT_COOLDOWN_HOURS = 6

MAX_WRITES_PER_MINUTE = 300
MAX_VALUES_PER_DAY_DIMENSION = 200
SAMPLE_RING_SIZE = 200

HOURLY_RETENTION_DAYS = 30
LONG_RETENTION_DAYS = 400
DETAIL_RETENTION_DAYS = 90
LONG_DIMENSIONS = ('total', 'circle', 'reason')
HOURLY_ROW_WARN_THRESHOLD = 10_000
DAILY_ROW_WARN_THRESHOLD = 100_000

OTHER_VALUE = '(other)'
RATE_CAPPED_REASON = 'rate_capped'
UNRECORDED_CIRCLE = '(unrecorded)'

SUMMARY_STATE_KEY = 'bot_summary_last_sent_date'
ALERT_STATE_KEY = 'bot_alert_last_sent_at'

_lock = threading.Lock()
_window = {'minute': None, 'writes': 0, 'dropped': 0}

_BROWSER_PATTERNS = [
    ('Edge', re.compile(r'Edg(?:e|A|iOS)?/(\d+)')),
    ('Opera', re.compile(r'OPR/(\d+)')),
    ('Firefox', re.compile(r'Firefox/(\d+)')),
    ('Chrome', re.compile(r'(?:Chrome|CriOS)/(\d+)')),
    ('Safari', re.compile(r'Version/(\d+).*Safari/')),
    ('curl', re.compile(r'curl/(\d+)')),
    ('python-requests', re.compile(r'python-requests/(\d+)')),
    ('Go-http-client', re.compile(r'Go-http-client/(\d+)')),
    ('okhttp', re.compile(r'okhttp/(\d+)')),
    ('zgrab', re.compile(r'zgrab')),
]
_OS_PATTERNS = [
    ('Windows', 'Windows'), ('iPhone', 'iOS'), ('iPad', 'iOS'), ('Android', 'Android'),
    ('Macintosh', 'macOS'), ('Linux', 'Linux'),
]


def user_agent_family(user_agent: str) -> str:
    """Reduce a raw User-Agent to a short fixed-vocabulary label like 'Chrome/125 Windows',
    so the stored/emailed value cannot carry attacker-chosen text."""
    if not user_agent:
        return 'none'
    browser = ''
    for name, pattern in _BROWSER_PATTERNS:
        match = pattern.search(user_agent)
        if match:
            browser = name + (f'/{match.group(1)}' if match.groups() else '')
            break
    os_name = next((label for needle, label in _OS_PATTERNS if needle in user_agent), '')
    return f'{browser} {os_name}'.strip() or 'other'


def ip_prefix(ip: str) -> str:
    """/24 for IPv4, /48 for IPv6; '' if not a valid address."""
    try:
        address = ipaddress.ip_address(ip)
    except ValueError:
        return ''
    bits = 24 if address.version == 4 else 48
    return str(ipaddress.ip_network(f'{address}/{bits}', strict=False))


def _admit(now_ts: float):
    """Per-process write throttle. Returns (allowed, dropped_count_to_flush)."""
    minute = int(now_ts // 60)
    with _lock:
        flush = 0
        if _window['minute'] != minute:
            flush = _window['dropped']
            _window.update(minute=minute, writes=0, dropped=0)
        if _window['writes'] >= MAX_WRITES_PER_MINUTE:
            _window['dropped'] += 1
            return False, flush
        _window['writes'] += 1
        return True, flush


def _bump_hourly(conn, hour, circle_slug, reason, n):
    conn.execute(text(
        "INSERT INTO bot_attempt_hourly (hour, circle_slug, reason, count) "
        "VALUES (:hour, :circle, :reason, :n) "
        "ON CONFLICT (hour, circle_slug, reason) DO UPDATE "
        "SET count = bot_attempt_hourly.count + :n"),
        {'hour': hour, 'circle': circle_slug[:50], 'reason': reason[:30], 'n': n})


def _bump_daily(conn, day, dimension, value, n=1):
    value = (value or '')[:100]
    params = {'day': day, 'dim': dimension, 'value': value, 'n': n}
    updated = conn.execute(text(
        "UPDATE bot_attempt_daily SET count = count + :n "
        "WHERE day = :day AND dimension = :dim AND value = :value"), params).rowcount
    if updated:
        return
    if dimension != 'total':
        distinct = conn.execute(text(
            "SELECT count(*) FROM bot_attempt_daily "
            "WHERE day = :day AND dimension = :dim AND value <> :other"),
            {'day': day, 'dim': dimension, 'other': OTHER_VALUE}).scalar()
        if distinct >= MAX_VALUES_PER_DAY_DIMENSION:
            params['value'] = OTHER_VALUE
    conn.execute(text(
        "INSERT INTO bot_attempt_daily (day, dimension, value, count) "
        "VALUES (:day, :dim, :value, :n) "
        "ON CONFLICT (day, dimension, value) DO UPDATE "
        "SET count = bot_attempt_daily.count + :n"), params)


def _write_sample(conn, now, reason, circle_slug, ip, user_agent, email, name):
    conn.execute(text(
        "INSERT INTO bot_attempt_sample "
        "(slot, occurred_at, reason, circle_slug, ip, user_agent, email, name) "
        "VALUES (nextval('bot_attempt_sample_seq') % :size, :now, :reason, :circle, :ip, :ua, :email, :name) "
        "ON CONFLICT (slot) DO UPDATE SET occurred_at = EXCLUDED.occurred_at, "
        "reason = EXCLUDED.reason, circle_slug = EXCLUDED.circle_slug, ip = EXCLUDED.ip, "
        "user_agent = EXCLUDED.user_agent, email = EXCLUDED.email, name = EXCLUDED.name"),
        {'size': SAMPLE_RING_SIZE, 'now': now, 'reason': reason[:30], 'circle': (circle_slug or '')[:50],
         'ip': (ip or '')[:45], 'ua': (user_agent or '')[:100], 'email': (email or '')[:100],
         'name': (name or '')[:100]})


def record_bot_attempt(reason, circle_slug, ip, user_agent='', email='', name='', now=None) -> bool:
    """Record one rejected registration attempt. Never raises - a failure here must not
    affect the registration response. Returns whether it was recorded."""
    try:
        now = now or datetime.now(timezone.utc)
        allowed, carried = _admit(now.timestamp())
        if not allowed:
            return False
        hour = now.replace(minute=0, second=0, microsecond=0)
        day = now.astimezone(PACIFIC).date()
        circle_slug = circle_slug or UNRECORDED_CIRCLE
        with get_engine().begin() as conn:
            if carried:
                _bump_hourly(conn, hour, UNRECORDED_CIRCLE, RATE_CAPPED_REASON, carried)
                _bump_daily(conn, day, 'total', 'all', carried)
                _bump_daily(conn, day, 'reason', RATE_CAPPED_REASON, carried)
            _bump_hourly(conn, hour, circle_slug, reason, 1)
            _bump_daily(conn, day, 'total', 'all')
            _bump_daily(conn, day, 'circle', circle_slug)
            _bump_daily(conn, day, 'reason', reason)
            if ip:
                _bump_daily(conn, day, 'ip', ip)
                prefix = ip_prefix(ip)
                if prefix:
                    _bump_daily(conn, day, 'ip_prefix', prefix)
            _bump_daily(conn, day, 'user_agent', user_agent_family(user_agent))
            if email and '@' in email:
                _bump_daily(conn, day, 'email_domain', email.rsplit('@', 1)[1].lower())
            _write_sample(conn, now, reason, circle_slug, ip, user_agent, email, name)
        return True
    except Exception as e:
        logger.error(f'Could not record bot attempt: {e}', exc_info=True)
        return False


def _safe_label(value, limit=40):
    """Attacker-influenced labels (email domains) are shown in emails only after reducing
    them to harmless characters and a short length."""
    return re.sub(r'[^A-Za-z0-9.:/_() -]', '?', str(value))[:limit]


def _top(conn, day, dimension, limit=10):
    return conn.execute(text(
        "SELECT value, count FROM bot_attempt_daily WHERE day = :day AND dimension = :dim "
        "ORDER BY count DESC, value LIMIT :limit"),
        {'day': day, 'dim': dimension, 'limit': limit}).fetchall()


def _format_rows(rows):
    return [f'  {_safe_label(value):<42}{count}' for value, count in rows] or ['  (none)']


def build_daily_summary(conn, local_day):
    """Plain-text summary of one Pacific day, or None if it had no attempts."""
    total = conn.execute(text(
        "SELECT count FROM bot_attempt_daily WHERE day = :day AND dimension = 'total' AND value = 'all'"),
        {'day': local_day}).scalar() or 0
    if not total:
        return None
    trend = dict(conn.execute(text(
        "SELECT day, count FROM bot_attempt_daily WHERE dimension = 'total' AND value = 'all' "
        "AND day BETWEEN :start AND :end"),
        {'start': local_day - timedelta(days=6), 'end': local_day}).fetchall())
    lines = [f'Bot registration attempts rejected on {local_day.isoformat()} (Pacific): {total}', '',
             'Last 7 days:']
    for offset in range(6, -1, -1):
        day = local_day - timedelta(days=offset)
        lines.append(f'  {day.isoformat()}  {trend.get(day, 0)}')
    for title, dimension in (('By reason', 'reason'), ('By circle', 'circle'),
                             ('Top networks (/24)', 'ip_prefix'), ('Top IPs', 'ip'),
                             ('Browser/OS families', 'user_agent'), ('Email domains', 'email_domain')):
        lines += ['', f'{title}:'] + _format_rows(_top(conn, local_day, dimension))
    lines += ['', 'Counts only: names, notes and raw user agents are deliberately left out. '
                  'The most recent attempts in full are in the bot_attempt_sample table.']
    return '\n'.join(lines) + '\n'


def build_hourly_alert(conn, hour_start, total, today_local):
    rows = conn.execute(text(
        "SELECT circle_slug, reason, count FROM bot_attempt_hourly WHERE hour = :hour "
        "ORDER BY count DESC"), {'hour': hour_start}).fetchall()
    local_start = hour_start.astimezone(PACIFIC).strftime('%Y-%m-%d %H:%M %Z')
    lines = [f'{total} bot registration attempts were rejected in the hour starting {local_start}, '
             f'across all circles (alert threshold: more than {ALERT_THRESHOLD}).', '', 'By circle / reason:']
    lines += [f'  {_safe_label(circle):<28}{_safe_label(reason):<24}{count}' for circle, reason, count in rows]
    lines += ['', "Today's top networks (/24):"] + _format_rows(_top(conn, today_local, 'ip_prefix', 5))
    lines += ['', f'You will get at most one of these alerts every {ALERT_COOLDOWN_HOURS} hours; the daily '
                  'summary (06:00 Pacific) covers everything.']
    return '\n'.join(lines) + '\n'


def prune(conn, now):
    """Delete expired rows; warn if a table is bigger than its design ceiling."""
    today = now.astimezone(PACIFIC).date()
    removed = conn.execute(text("DELETE FROM bot_attempt_hourly WHERE hour < :cutoff"),
                           {'cutoff': now - timedelta(days=HOURLY_RETENTION_DAYS)}).rowcount
    removed += conn.execute(text(
        "DELETE FROM bot_attempt_daily WHERE dimension IN :long AND day < :cutoff").bindparams(
        bindparam('long', expanding=True)),
        {'long': list(LONG_DIMENSIONS), 'cutoff': today - timedelta(days=LONG_RETENTION_DAYS)}).rowcount
    removed += conn.execute(text(
        "DELETE FROM bot_attempt_daily WHERE dimension NOT IN :long AND day < :cutoff").bindparams(
        bindparam('long', expanding=True)),
        {'long': list(LONG_DIMENSIONS), 'cutoff': today - timedelta(days=DETAIL_RETENTION_DAYS)}).rowcount
    for table, ceiling in (('bot_attempt_hourly', HOURLY_ROW_WARN_THRESHOLD),
                           ('bot_attempt_daily', DAILY_ROW_WARN_THRESHOLD)):
        rows = conn.execute(text(f'SELECT count(*) FROM {table}')).scalar()
        if rows > ceiling:
            logger.warning(f'{table} has {rows} rows, above its expected ceiling of {ceiling}')
    return removed


def _default_send(to_addresses, subject, body):
    alert_from = AppSettingsModel(get_db_session()).get_scheduler_alert_from_email()
    return email_service.send_email(to_addresses, subject, body, from_email=alert_from)


def run_bot_attempt_notifications(now_utc=None, send=None):
    """Hourly-tick entry point: daily summary, hourly-spike alert, pruning. Each step is
    isolated so one failing never blocks the others. `now_utc` and `send` are injectable
    for tests. Returns a JSON-serializable summary."""
    now = now_utc or datetime.now(timezone.utc)
    send = send or _default_send
    settings = AppSettingsModel(get_db_session())
    recipients = sorted(set(get_admin_emails()))
    result = {'summary_sent': False, 'alert_sent': False, 'pruned': 0, 'errors': 0}
    local = now.astimezone(PACIFIC)
    today = local.date()

    try:
        due = (SUMMARY_HOUR_LOCAL <= local.hour < SUMMARY_HOUR_LOCAL + SUMMARY_WINDOW_HOURS
               and settings.get(SUMMARY_STATE_KEY) != today.isoformat())
        if due:
            with get_engine().connect() as conn:
                body = build_daily_summary(conn, today - timedelta(days=1))
            if body is None:
                settings.set(SUMMARY_STATE_KEY, today.isoformat())
            elif send(recipients, f'[CBC] Bot registration attempts - {(today - timedelta(days=1)).isoformat()}', body):
                settings.set(SUMMARY_STATE_KEY, today.isoformat())
                result['summary_sent'] = True
            else:
                result['errors'] += 1
                logger.error('Bot attempt daily summary was not sent; will retry within the window')
    except Exception as e:
        result['errors'] += 1
        logger.error(f'Bot attempt daily summary failed: {e}', exc_info=True)

    try:
        hour_start = now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
        with get_engine().connect() as conn:
            total = conn.execute(text("SELECT coalesce(sum(count), 0) FROM bot_attempt_hourly WHERE hour = :hour"),
                                 {'hour': hour_start}).scalar()
            last = settings.get(ALERT_STATE_KEY)
            cooled = not last or now - datetime.fromisoformat(last) >= timedelta(hours=ALERT_COOLDOWN_HOURS)
            if total > ALERT_THRESHOLD and cooled:
                body = build_hourly_alert(conn, hour_start, total, today)
                if send(recipients, f'[CBC] Bot registration spike: {total} attempts in one hour', body):
                    settings.set(ALERT_STATE_KEY, now.isoformat())
                    result['alert_sent'] = True
                else:
                    result['errors'] += 1
    except Exception as e:
        result['errors'] += 1
        logger.error(f'Bot attempt hourly alert failed: {e}', exc_info=True)

    try:
        with get_engine().begin() as conn:
            result['pruned'] = prune(conn, now)
    except Exception as e:
        result['errors'] += 1
        logger.error(f'Bot attempt pruning failed: {e}', exc_info=True)

    return result
