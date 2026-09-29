# Updated by Claude AI on 2026-09-28
"""
Models for cron-driven per-circle email scheduling (migration 0012,
SCHEDULER_ARCHITECTURE_PLAN.txt): admin-editable send times, and the run log
that the tick command reads to decide what is already done.
"""

from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError

from config.email_content_blocks import SCHEDULABLE_EMAIL_TYPES
from models.db import CircleEmailSchedule, EmailScheduleRunLog

# (email_type, local hour, day_of_week) - day_of_week uses Python's
# date.weekday() convention: 0=Monday ... 6=Sunday, None = every day.
# Friday is therefore 4. Applied to every new circle (CircleModel.create) and
# backfilled for existing ones by migration 0012, which keeps its own copy.
DEFAULT_SCHEDULE = [
    ('team_update', 7, None),
    ('team_update', 18, None),
    ('weekly_summary', 23, 4),
    ('admin_digest', 18, None),
]

# Cap so a circle admin can't accumulate an absurd number of send times.
MAX_SLOTS_PER_EMAIL_TYPE = 4


class CircleEmailScheduleModel:
    """CRUD for circle_email_schedules rows."""

    def __init__(self, db_session):
        self.db = db_session

    def get_for_circle(self, circle_slug):
        """A circle's schedule rows, ordered by email type, then hour."""
        rows = (self.db.query(CircleEmailSchedule)
                .filter_by(circle_slug=circle_slug)
                .order_by(CircleEmailSchedule.email_type, CircleEmailSchedule.hour,
                          CircleEmailSchedule.day_of_week)
                .all())
        return [row.to_dict() for row in rows]

    def get_all(self):
        """Every schedule row for every circle (small table - the tick reads all of it)."""
        rows = (self.db.query(CircleEmailSchedule)
                .order_by(CircleEmailSchedule.circle_slug, CircleEmailSchedule.email_type,
                          CircleEmailSchedule.hour)
                .all())
        return [row.to_dict() for row in rows]

    def add(self, circle_slug, email_type, hour, day_of_week=None, commit=True):
        """Add one send time. Raises ValueError for invalid input, an exact
        duplicate, or too many slots for this email type."""
        if email_type not in SCHEDULABLE_EMAIL_TYPES:
            raise ValueError(f'Unknown email type: {email_type}')
        if not isinstance(hour, int) or isinstance(hour, bool) or not 0 <= hour <= 23:
            raise ValueError('Hour must be a whole number from 0 to 23.')
        if day_of_week is not None and (
                not isinstance(day_of_week, int) or isinstance(day_of_week, bool)
                or not 0 <= day_of_week <= 6):
            raise ValueError('Day of week must be 0 (Monday) to 6 (Sunday), or blank for every day.')

        existing = self.db.query(CircleEmailSchedule).filter_by(
            circle_slug=circle_slug, email_type=email_type).count()
        if existing >= MAX_SLOTS_PER_EMAIL_TYPE:
            raise ValueError(f'At most {MAX_SLOTS_PER_EMAIL_TYPE} send times per email type.')

        now = datetime.now(timezone.utc)
        row = CircleEmailSchedule(
            circle_slug=circle_slug, email_type=email_type, hour=hour,
            day_of_week=day_of_week, created_at=now, updated_at=now,
        )
        self.db.add(row)
        try:
            if commit:
                self.db.commit()
            else:
                self.db.flush()
        except IntegrityError:
            self.db.rollback()
            raise ValueError('That send time already exists.')
        return row.to_dict()

    def remove(self, schedule_id, circle_slug):
        """Delete one row, only if it belongs to circle_slug (a circle admin must
        never be able to delete another circle's row by guessing an id).
        Returns True if a row was deleted."""
        deleted = (self.db.query(CircleEmailSchedule)
                   .filter_by(id=schedule_id, circle_slug=circle_slug)
                   .delete(synchronize_session=False))
        self.db.commit()
        return bool(deleted)

    def create_defaults(self, circle_slug, commit=True):
        """Insert DEFAULT_SCHEDULE for a circle. Skips any slot that already exists."""
        existing = {
            (row['email_type'], row['hour'], row['day_of_week'])
            for row in self.get_for_circle(circle_slug)
        }
        for email_type, hour, day_of_week in DEFAULT_SCHEDULE:
            if (email_type, hour, day_of_week) not in existing:
                self.add(circle_slug, email_type, hour, day_of_week, commit=False)
        if commit:
            self.db.commit()


class EmailScheduleRunLogModel:
    """Append-only run log: the tick's source of truth for "already attempted"."""

    def __init__(self, db_session):
        self.db = db_session

    def has_attempt_since(self, schedule_id, since):
        """True if ANY attempt (success or failure) for this schedule row was logged
        at or after `since`."""
        return self.db.query(EmailScheduleRunLog).filter(
            EmailScheduleRunLog.schedule_id == schedule_id,
            EmailScheduleRunLog.run_at >= since,
        ).first() is not None

    def has_any_attempt(self, schedule_id):
        """True if this schedule row has ever had an attempt logged (evidence the
        scheduler has actually been running for it)."""
        return self.db.query(EmailScheduleRunLog).filter(
            EmailScheduleRunLog.schedule_id == schedule_id,
        ).first() is not None

    def record(self, circle_slug, email_type, year, run_at, success, emails_sent=0,
               error_summary=None, schedule_id=None, triggered_by='scheduler'):
        row = EmailScheduleRunLog(
            circle_slug=circle_slug, email_type=email_type, schedule_id=schedule_id,
            year=year, run_at=run_at, success=success, emails_sent=emails_sent,
            error_summary=error_summary, triggered_by=triggered_by,
        )
        self.db.add(row)
        self.db.commit()
        return row.to_dict()

    def get_recent(self, limit=100, circle_slug=None):
        """Most recent attempts first, optionally for one circle."""
        query = self.db.query(EmailScheduleRunLog)
        if circle_slug:
            query = query.filter_by(circle_slug=circle_slug)
        rows = query.order_by(EmailScheduleRunLog.run_at.desc(), EmailScheduleRunLog.id.desc()).limit(limit).all()
        return [row.to_dict() for row in rows]
