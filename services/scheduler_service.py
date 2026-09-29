# Updated by Claude AI on 2026-09-28
"""
Cron-driven email scheduling (SCHEDULER_ARCHITECTURE_PLAN.txt).

One hourly cron entry runs `flask tick-scheduled-emails` (services/scheduler_cli.py),
which calls tick() here. tick() decides, per circle_email_schedules row, whether
that row's most recent expected occurrence is due, runs the matching email
generator for that circle, and records every attempt in email_schedule_run_log.

Retry policy: an occurrence that was never attempted is run when its tick finally
arrives, up to RETRY_WINDOW after its scheduled time. After that a synthetic
failure row is written instead. An occurrence that WAS attempted and failed is
never retried automatically - it is reported to the super-admins (and that
circle's admins) for a human to look at.
"""

import logging
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone

import pytz
from dateutil.relativedelta import relativedelta
from sqlalchemy import text

from config.admins import get_admin_emails
from config.database import get_db_session
from config.email_content_blocks import SCHEDULABLE_EMAIL_TYPES
from models.app_settings import AppSettingsModel
from models.circle import CircleAdminModel, CircleModel
from models.db import get_engine
from models.email_schedule import CircleEmailScheduleModel, EmailScheduleRunLogModel
from services.email_service import email_service

logger = logging.getLogger(__name__)

RETRY_WINDOW = timedelta(hours=3)
# Arbitrary constant key for the Postgres advisory lock that keeps two ticks
# (overlapping runs, or a second app instance's crontab) from running at once.
TICK_ADVISORY_LOCK_KEY = 7_261_800_112
ERROR_SUMMARY_MAX_CHARS = 2000
MISSED_WINDOW_MESSAGE = 'did not run within the 3h retry window'

MANUAL_RUN_OUT_OF_SEASON_MESSAGE = "This circle is outside its email season (registration opening through the count date)."


def _default_generators():
    """email_type -> generator(app, circle_slug). Imported lazily: test.email_generator
    pulls in most of the app, and the pure due-time logic here needs none of it."""
    from test.email_generator import (
        generate_admin_digest_email, generate_team_update_emails, generate_weekly_summary_emails,
    )
    return {
        'team_update': generate_team_update_emails,
        'weekly_summary': generate_weekly_summary_emails,
        'admin_digest': generate_admin_digest_email,
    }


def most_recent_occurrence(hour, day_of_week, now_utc, tz_name):
    """The latest time <= now_utc (returned in UTC) at which a schedule row with this
    local `hour` and `day_of_week` (Python date.weekday(): 0=Monday..6=Sunday, None =
    every day) was due, evaluated in the circle's own timezone."""
    tz = pytz.timezone(tz_name)
    local_now = now_utc.astimezone(tz)
    for days_back in range(0, 8):
        day = local_now.date() - timedelta(days=days_back)
        if day_of_week is not None and day.weekday() != day_of_week:
            continue
        candidate = tz.normalize(tz.localize(datetime(day.year, day.month, day.day, hour)))
        if candidate <= local_now:
            return candidate.astimezone(timezone.utc)
    raise ValueError(f'No occurrence found for hour={hour} day_of_week={day_of_week}')


def _registration_opens_months(circle):
    """Mirrors config/organization.py's _get_validated_registration_opens(), which
    needs a resolved request circle and so can't be called from here."""
    try:
        value = int(circle.get('registration_opens_months'))
    except (TypeError, ValueError):
        return 3
    return value if value > 0 else 3


def is_in_season(circle, local_date):
    """True if local_date falls from the day registration opens through the count
    date itself, inclusive, for any of the circle's configured count years."""
    opens_months = _registration_opens_months(circle)
    for date_str in (circle.get('yearly_count_dates') or {}).values():
        try:
            count_date = date.fromisoformat(date_str)
        except (TypeError, ValueError):
            continue
        if count_date - relativedelta(months=opens_months) <= local_date <= count_date:
            return True
    return False


def season_summary(circle, local_today):
    """What an admin needs to know about when this circle's emails run:
    {'in_season': bool, 'starts': date or None, 'ends': date or None}. In season,
    starts/ends are the current season's opening and count dates; otherwise they
    are the next upcoming season's, or None/None if no future count date is set."""
    opens_months = _registration_opens_months(circle)
    upcoming = []
    for date_str in (circle.get('yearly_count_dates') or {}).values():
        try:
            count_date = date.fromisoformat(date_str)
        except (TypeError, ValueError):
            continue
        opening = count_date - relativedelta(months=opens_months)
        if opening <= local_today <= count_date:
            return {'in_season': True, 'starts': opening, 'ends': count_date}
        if opening > local_today:
            upcoming.append((opening, count_date))
    if upcoming:
        starts, ends = min(upcoming)
        return {'in_season': False, 'starts': starts, 'ends': ends}
    return {'in_season': False, 'starts': None, 'ends': None}


def classify_schedule_rows(schedules, circles_by_slug, has_attempt_since, now_utc):
    """Split schedule rows into (due, expired) lists of
    {'schedule', 'circle', 'occurrence'} dicts.

    A row is skipped entirely (in neither list) when its circle is unknown, the
    row was created after the occurrence (an admin adding a 14:00 slot at 15:00
    must not fire retroactively), the occurrence's local date was outside the
    circle's season, or any attempt - success or failure - is already logged for
    it. Otherwise it is due while within RETRY_WINDOW of the occurrence, and
    expired once past it."""
    due, expired = [], []
    for schedule in schedules:
        circle = circles_by_slug.get(schedule['circle_slug'])
        if circle is None:
            continue
        try:
            occurrence = most_recent_occurrence(
                schedule['hour'], schedule['day_of_week'], now_utc, circle['display_timezone'])
        except (pytz.UnknownTimeZoneError, ValueError) as e:
            logger.error(f"Cannot compute schedule {schedule['id']} for {schedule['circle_slug']}: {e}")
            continue

        if schedule['created_at'] > occurrence:
            continue
        local_date = occurrence.astimezone(pytz.timezone(circle['display_timezone'])).date()
        if not is_in_season(circle, local_date):
            continue
        if has_attempt_since(schedule['id'], occurrence):
            continue

        entry = {'schedule': schedule, 'circle': circle, 'occurrence': occurrence}
        (due if now_utc - occurrence <= RETRY_WINDOW else expired).append(entry)
    return due, expired


@contextmanager
def tick_lock():
    """Non-blocking Postgres advisory lock, yielding whether it was acquired.
    Held on a dedicated connection (not the scoped session, which returns its
    connection to the pool between commits and would silently drop a
    session-level lock). Explicitly unlocked before the connection goes back
    to the pool, since closing a pooled connection does not end its DB session."""
    conn = get_engine().connect()
    acquired = False
    try:
        acquired = bool(conn.execute(
            text('SELECT pg_try_advisory_lock(:key)'), {'key': TICK_ADVISORY_LOCK_KEY}).scalar())
        yield acquired
    finally:
        try:
            if acquired:
                conn.execute(text('SELECT pg_advisory_unlock(:key)'), {'key': TICK_ADVISORY_LOCK_KEY})
        finally:
            conn.close()


def _run_generator(app, generator_fn, circle_slug):
    """Run one generator, returning (success, emails_sent, error_summary). The
    generators catch most exceptions themselves and report them in results['errors'],
    so a non-empty errors list counts as failure just like a raised exception."""
    try:
        results = generator_fn(app, circle_slug)
    except Exception as e:
        logger.error(f'Generator failed for {circle_slug}: {e}', exc_info=True)
        return False, 0, str(e)[:ERROR_SUMMARY_MAX_CHARS]

    errors = results.get('errors') or []
    summary = '; '.join(str(err) for err in errors)[:ERROR_SUMMARY_MAX_CHARS] if errors else None
    return not errors, results.get('emails_sent', 0), summary


def _format_failure(circle_slug, email_type, occurrence, tz_name, error_summary):
    local = occurrence.astimezone(pytz.timezone(tz_name)) if occurrence else None
    return {
        'circle_slug': circle_slug,
        'email_type': email_type,
        'occurrence_local': local.strftime('%Y-%m-%d %H:%M %Z') if local else 'manual run',
        'error_summary': error_summary or 'unknown error',
    }


def send_failure_notifications(db, failures, circles_by_slug):
    """One summary email to the super-admins covering every failure, plus one
    email per affected circle to that circle's own admins. Circle admins get the
    circle, email type and time only - not the raw error text, which can carry
    internals (SQL, paths) that are the super-admins' business. A failure to
    send is logged and swallowed: there is no alerting for the alerting."""
    if not failures:
        return False

    alert_from = AppSettingsModel(db).get_scheduler_alert_from_email()
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    super_admins = sorted(set(get_admin_emails()))

    lines = [
        f"- {f['circle_slug']} / {f['email_type']} / scheduled {f['occurrence_local']}: {f['error_summary']}"
        for f in failures
    ]
    subject = f'[CBC Scheduler] {len(failures)} job(s) failed - {today}'
    body = (
        'The following scheduled email jobs failed or did not run:\n\n' + '\n'.join(lines) +
        '\n\nFailed runs are not retried automatically. Check the Scheduler page in the '
        'admin console for details, and re-run from there once the cause is fixed.\n'
    )
    sent = False
    try:
        sent = email_service.send_email(super_admins, subject, body, from_email=alert_from)
    except Exception as e:
        logger.error(f'Could not send scheduler failure notification: {e}', exc_info=True)
    if not sent:
        logger.error(f'Scheduler failure notification to super-admins was not sent ({len(failures)} failure(s))')

    admin_model = CircleAdminModel(db)
    for slug in sorted({f['circle_slug'] for f in failures}):
        recipients = sorted(
            {a['email'] for a in admin_model.get_admins_for_circle(slug)} - set(super_admins))
        if not recipients:
            continue
        circle_failures = [f for f in failures if f['circle_slug'] == slug]
        circle_name = (circles_by_slug.get(slug) or {}).get('circle_name', slug)
        circle_lines = [
            f"- {f['email_type'].replace('_', ' ')} scheduled {f['occurrence_local']}"
            for f in circle_failures
        ]
        circle_body = (
            f'The following scheduled emails for {circle_name} did not go out:\n\n' +
            '\n'.join(circle_lines) +
            '\n\nThe site administrators have been notified and will look into it. '
            'No action is needed from you.\n'
        )
        try:
            email_service.send_email(
                recipients, f'[CBC Scheduler] {circle_name}: {len(circle_failures)} email job(s) failed - {today}',
                circle_body, from_email=alert_from)
        except Exception as e:
            logger.error(f'Could not send scheduler failure notification for {slug}: {e}', exc_info=True)

    return sent


def tick(app, now_utc=None, generators=None, only_circles=None):
    """Run everything that is due right now. Returns a JSON-serializable summary.
    `now_utc` and `generators` are injectable for tests; `only_circles` (an
    iterable of slugs) restricts the tick to those circles, for tests and for
    a hand-run `flask tick-scheduled-emails --circle SLUG`."""
    now_utc = now_utc or datetime.now(timezone.utc)
    generators = generators or _default_generators()
    summary = {'attempted': 0, 'succeeded': 0, 'failed': 0, 'expired': 0,
               'notified': False, 'skipped_locked': False}

    with tick_lock() as acquired:
        if not acquired:
            logger.warning('Another scheduler tick is already running - skipping this one')
            summary['skipped_locked'] = True
            return summary

        db = get_db_session()
        circles_by_slug = {c['slug']: c for c in CircleModel(db).get_all()}
        schedules = CircleEmailScheduleModel(db).get_all()
        if only_circles is not None:
            only_circles = set(only_circles)
            schedules = [s for s in schedules if s['circle_slug'] in only_circles]
        run_log =EmailScheduleRunLogModel(db)
        due, expired = classify_schedule_rows(schedules, circles_by_slug, run_log.has_attempt_since, now_utc)

        failures = []

        for entry in expired:
            schedule, circle = entry['schedule'], entry['circle']
            EmailScheduleRunLogModel(get_db_session()).record(
                schedule['circle_slug'], schedule['email_type'], now_utc.year, now_utc, False,
                error_summary=MISSED_WINDOW_MESSAGE, schedule_id=schedule['id'])
            summary['expired'] += 1
            failures.append(_format_failure(
                schedule['circle_slug'], schedule['email_type'], entry['occurrence'],
                circle['display_timezone'], MISSED_WINDOW_MESSAGE))

        for entry in due:
            schedule, circle = entry['schedule'], entry['circle']
            generator_fn = generators.get(schedule['email_type'])
            if generator_fn is None:
                logger.error(f"No generator registered for email type {schedule['email_type']}")
                continue

            summary['attempted'] += 1
            success, emails_sent, error_summary = _run_generator(app, generator_fn, schedule['circle_slug'])
            # run_at is the tick's own timestamp (when the occurrence was evaluated),
            # the same clock has_attempt_since() compares against - not the moment
            # the generator finished. The generator may also have discarded the
            # scoped session (it pushes its own request context), so always fetch
            # a fresh one for the log write.
            EmailScheduleRunLogModel(get_db_session()).record(
                schedule['circle_slug'], schedule['email_type'], now_utc.year, now_utc,
                success, emails_sent=emails_sent, error_summary=error_summary, schedule_id=schedule['id'])
            if success:
                summary['succeeded'] += 1
            else:
                summary['failed'] += 1
                failures.append(_format_failure(
                    schedule['circle_slug'], schedule['email_type'], entry['occurrence'],
                    circle['display_timezone'], error_summary))

        summary['notified'] = send_failure_notifications(get_db_session(), failures, circles_by_slug)

    return summary


def run_manual(app, circle_slug, email_type, triggered_by, now_utc=None, generators=None):
    """Super-admin "run now" for one (circle, email type). Refuses outside the
    circle's season. The generators only send what changed since each area's last
    send, so running this right after a normal run sends nothing new. Logged with
    schedule_id NULL and the triggering admin's email. Returns the run-log dict;
    raises ValueError for an unknown circle/type or an out-of-season circle."""
    now_utc = now_utc or datetime.now(timezone.utc)
    if email_type not in SCHEDULABLE_EMAIL_TYPES:
        raise ValueError(f'Unknown email type: {email_type}')
    generators = generators or _default_generators()

    db = get_db_session()
    circle = CircleModel(db).get_by_slug(circle_slug)
    if circle is None:
        raise ValueError(f'Unknown circle: {circle_slug}')
    local_date = now_utc.astimezone(pytz.timezone(circle['display_timezone'])).date()
    if not is_in_season(circle, local_date):
        raise ValueError(MANUAL_RUN_OUT_OF_SEASON_MESSAGE)

    success, emails_sent, error_summary = _run_generator(app, generators[email_type], circle_slug)
    return EmailScheduleRunLogModel(get_db_session()).record(
        circle_slug, email_type, now_utc.year, now_utc, success,
        emails_sent=emails_sent, error_summary=error_summary, triggered_by=triggered_by)
