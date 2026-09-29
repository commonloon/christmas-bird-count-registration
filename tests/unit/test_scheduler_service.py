# Updated by Claude AI on 2026-09-28
"""
Tests for cron-driven email scheduling: services/scheduler_service.py (due-time
logic, season window, tick, manual run, failure notifications),
models/email_schedule.py and models/app_settings.py.

Time is always injected (now_utc) and generators are always fakes, so nothing
depends on the real clock or sends real email. email_service.send_email is
replaced with a recorder. tick() is restricted to the 'test' circle
(only_circles) so real circles in the local dev DB are never touched.
"""

# Import order safety - see tests/unit/test_multi_circle_isolation.py's comment.
import app  # noqa: F401

from datetime import date, datetime, timedelta, timezone

import pytest

from config.database import get_db_session
from models.app_settings import (
    DEFAULT_SCHEDULER_ALERT_FROM_EMAIL, SCHEDULER_ALERT_FROM_EMAIL_KEY, AppSettingsModel,
)
from models.circle import CircleModel
from models.db import AppSetting, Circle, CircleEmailSchedule, EmailScheduleRunLog
from models.email_schedule import (
    DEFAULT_SCHEDULE, MAX_SLOTS_PER_EMAIL_TYPE, CircleEmailScheduleModel, EmailScheduleRunLogModel,
)
from services import scheduler_service
from services.email_service import email_service
from services.scheduler_service import (
    MANUAL_RUN_OUT_OF_SEASON_MESSAGE, MISSED_WINDOW_MESSAGE, classify_schedule_rows, is_in_season,
    most_recent_occurrence, run_manual, tick, tick_lock,
)
from tests.test_config import TEST_CIRCLE_SLUG, TEST_CIRCLE_SLUG_2
from tests.unit.conftest import CIRCLE_ADMIN_TEST_EMAIL

UTC = timezone.utc
# Not America/Vancouver: the installed tzdata treats Vancouver as permanent UTC-7,
# which would make these hand-computed offsets depend on the tz database version.
VANCOUVER = 'America/Los_Angeles'
LONG_AGO = datetime(2020, 1, 1, tzinfo=UTC)


def utc(*args):
    return datetime(*args, tzinfo=UTC)


class TestMostRecentOccurrence:
    def test_daily_slot_earlier_today_when_already_passed(self):
        # 2026-11-20 16:30 UTC = 08:30 PST; today's 07:00 PST (15:00 UTC) has passed.
        assert most_recent_occurrence(7, None, utc(2026, 11, 20, 16, 30), VANCOUVER) == utc(2026, 11, 20, 15, 0)

    def test_daily_slot_falls_back_to_yesterday_when_not_yet_reached(self):
        # 2026-11-20 14:00 UTC = 06:00 PST; 07:00 hasn't happened today yet.
        assert most_recent_occurrence(7, None, utc(2026, 11, 20, 14, 0), VANCOUVER) == utc(2026, 11, 19, 15, 0)

    def test_exactly_on_the_hour_counts_as_occurred(self):
        assert most_recent_occurrence(7, None, utc(2026, 11, 20, 15, 0), VANCOUVER) == utc(2026, 11, 20, 15, 0)

    def test_weekday_convention_is_python_weekday_friday_is_4(self):
        # 2026-11-20 is a Friday. Friday 23:00 PST = Saturday 07:00 UTC.
        assert date(2026, 11, 20).weekday() == 4
        now = utc(2026, 11, 25, 12, 0)  # Wednesday
        assert most_recent_occurrence(23, 4, now, VANCOUVER) == utc(2026, 11, 21, 7, 0)

    def test_weekly_slot_on_its_own_day_before_the_hour_uses_last_week(self):
        # Friday 2026-11-20 20:00 PST (Sat 04:00 UTC) - tonight's 23:00 hasn't happened.
        now = utc(2026, 11, 21, 4, 0)
        assert most_recent_occurrence(23, 4, now, VANCOUVER) == utc(2026, 11, 14, 7, 0)

    def test_uses_the_circles_own_timezone_including_dst(self):
        # July: Los Angeles is PDT (UTC-7), Toronto EDT (UTC-4).
        now = utc(2026, 7, 15, 20, 0)
        assert most_recent_occurrence(7, None, now, VANCOUVER) == utc(2026, 7, 15, 14, 0)
        assert most_recent_occurrence(7, None, now, 'America/Toronto') == utc(2026, 7, 15, 11, 0)


class TestIsInSeason:
    CIRCLE = {'yearly_count_dates': {2026: '2026-12-19'}, 'registration_opens_months': 4}

    def test_opening_day_is_in_season(self):
        assert is_in_season(self.CIRCLE, date(2026, 8, 19))

    def test_day_before_opening_is_out_of_season(self):
        assert not is_in_season(self.CIRCLE, date(2026, 8, 18))

    def test_count_day_itself_is_in_season(self):
        assert is_in_season(self.CIRCLE, date(2026, 12, 19))

    def test_day_after_count_is_out_of_season(self):
        assert not is_in_season(self.CIRCLE, date(2026, 12, 20))

    def test_no_count_dates_means_never_in_season(self):
        assert not is_in_season({'yearly_count_dates': {}, 'registration_opens_months': 4}, date(2026, 11, 1))

    def test_unparseable_count_date_is_ignored(self):
        circle = {'yearly_count_dates': {2026: 'TBD', 2027: '2027-12-18'}, 'registration_opens_months': 4}
        assert is_in_season(circle, date(2027, 11, 1))
        assert not is_in_season(circle, date(2026, 11, 1))

    def test_invalid_opens_months_falls_back_to_three(self):
        circle = {'yearly_count_dates': {2026: '2026-12-19'}, 'registration_opens_months': 0}
        assert is_in_season(circle, date(2026, 9, 19))
        assert not is_in_season(circle, date(2026, 9, 18))


class TestClassifyScheduleRows:
    NOW = utc(2026, 11, 20, 16, 30)  # 08:30 PST
    CIRCLE = {'slug': 'x', 'display_timezone': VANCOUVER,
              'yearly_count_dates': {2026: '2026-12-19'}, 'registration_opens_months': 4}

    def schedule(self, **overrides):
        row = {'id': 1, 'circle_slug': 'x', 'email_type': 'team_update', 'hour': 7,
               'day_of_week': None, 'created_at': LONG_AGO}
        row.update(overrides)
        return row

    def classify(self, schedules, attempted=lambda schedule_id, since: False, circles=None):
        circles = {'x': self.CIRCLE} if circles is None else circles
        return classify_schedule_rows(schedules, circles, attempted, self.NOW)

    def test_within_retry_window_is_due(self):
        due, expired = self.classify([self.schedule()])  # 07:00 PST, now 08:30 -> 1.5h
        assert len(due) == 1 and not expired
        assert due[0]['occurrence'] == utc(2026, 11, 20, 15, 0)

    def test_exactly_at_the_end_of_the_window_is_still_due(self):
        now = utc(2026, 11, 20, 18, 0)  # 3h after 15:00 UTC
        due, expired = classify_schedule_rows([self.schedule()], {'x': self.CIRCLE}, lambda i, s: False, now)
        assert len(due) == 1 and not expired

    def test_past_the_retry_window_is_expired_not_due(self):
        due, expired = self.classify([self.schedule(hour=4)])  # 04:00 PST, 4.5h ago
        assert not due and len(expired) == 1

    def test_any_logged_attempt_suppresses_it(self):
        assert self.classify([self.schedule()], attempted=lambda i, s: True) == ([], [])

    def test_attempt_lookup_gets_this_rows_id_and_the_occurrence_start(self):
        seen = []
        self.classify([self.schedule(id=42)], attempted=lambda i, s: seen.append((i, s)) or False)
        assert seen == [(42, utc(2026, 11, 20, 15, 0))]

    def test_row_created_after_the_occurrence_is_ignored(self):
        created_at = utc(2026, 11, 20, 15, 30)  # admin added it 30 min after 07:00 PST
        assert self.classify([self.schedule(created_at=created_at)]) == ([], [])

    def test_out_of_season_occurrence_is_ignored(self):
        circle = dict(self.CIRCLE, yearly_count_dates={2026: '2026-11-19'})  # count was yesterday
        assert self.classify([self.schedule()], circles={'x': circle}) == ([], [])

    def test_unknown_circle_is_ignored(self):
        assert self.classify([self.schedule(circle_slug='gone')]) == ([], [])

    def test_bad_timezone_is_skipped_not_raised(self):
        circle = dict(self.CIRCLE, display_timezone='Not/AZone')
        assert self.classify([self.schedule()], circles={'x': circle}) == ([], [])


# --- database-backed tests ------------------------------------------------

# 2026-11-20 16:30 UTC = 08:30 PST. With the fixture's rows below: the 07:00 slot
# is due (1.5h ago), the 04:00 slot is expired (4.5h ago).
TICK_NOW = utc(2026, 11, 20, 16, 30)
OUT_OF_SEASON_NOW = utc(2027, 3, 1, 16, 30)


@pytest.fixture
def db():
    return get_db_session()


@pytest.fixture
def sent_emails(monkeypatch):
    """Replace email_service.send_email with a recorder that never sends anything."""
    sent = []

    def fake_send_email(to_addresses, subject, body, html_body=None, from_email=None, test_recipient=None):
        sent.append({'to': list(to_addresses), 'subject': subject, 'body': body, 'from': from_email})
        return True

    monkeypatch.setattr(email_service, 'send_email', fake_send_email)
    return sent


@pytest.fixture
def scheduled_circle(db):
    """The 'test' circle put into a known state for tick tests: Los Angeles timezone,
    a count date that puts TICK_NOW in season, and exactly two schedule rows
    (07:00 team_update, 04:00 admin_digest), both created long ago. Restored to
    the original config plus the default schedule afterwards."""
    circle = db.query(Circle).filter_by(slug=TEST_CIRCLE_SLUG).first()
    original = {
        'yearly_count_dates': circle.yearly_count_dates,
        'registration_opens_months': circle.registration_opens_months,
        'display_timezone': circle.display_timezone,
    }
    circle.yearly_count_dates = {'2026': '2026-12-19'}
    circle.registration_opens_months = 4
    circle.display_timezone = VANCOUVER
    db.commit()

    def reset_rows():
        db.query(EmailScheduleRunLog).filter_by(circle_slug=TEST_CIRCLE_SLUG).delete()
        db.query(CircleEmailSchedule).filter_by(circle_slug=TEST_CIRCLE_SLUG).delete()
        db.commit()

    reset_rows()
    rows = {}
    schedule_model = CircleEmailScheduleModel(db)
    for email_type, hour in (('team_update', 7), ('admin_digest', 4)):
        row = schedule_model.add(TEST_CIRCLE_SLUG, email_type, hour)
        db.query(CircleEmailSchedule).filter_by(id=row['id']).update({'created_at': LONG_AGO})
        rows[email_type] = row
    db.commit()

    yield rows

    reset_rows()
    circle = db.query(Circle).filter_by(slug=TEST_CIRCLE_SLUG).first()
    for key, value in original.items():
        setattr(circle, key, value)
    db.commit()
    CircleEmailScheduleModel(db).create_defaults(TEST_CIRCLE_SLUG)


class FakeGenerators:
    """Records calls; per-email-type behaviour is a return dict or an exception to raise."""

    def __init__(self, **behaviour):
        self.calls = []
        self.behaviour = behaviour

    def __call__(self, email_type):
        def generator(app_arg, circle_slug):
            self.calls.append((email_type, circle_slug))
            outcome = self.behaviour.get(email_type, {'emails_sent': 2, 'errors': []})
            if isinstance(outcome, Exception):
                raise outcome
            return outcome
        return generator

    def as_map(self):
        return {t: self(t) for t in ('team_update', 'weekly_summary', 'admin_digest')}


def run_tick(now=TICK_NOW, generators=None):
    generators = generators or FakeGenerators()
    summary = tick(app.app, now_utc=now, generators=generators.as_map(), only_circles=[TEST_CIRCLE_SLUG])
    return summary, generators


def logged_runs(db):
    db.expire_all()
    return EmailScheduleRunLogModel(db).get_recent(circle_slug=TEST_CIRCLE_SLUG)


class TestTick:
    def test_due_row_runs_its_generator_once_and_is_logged(self, db, scheduled_circle, sent_emails):
        summary, generators = run_tick()

        assert generators.calls == [('team_update', TEST_CIRCLE_SLUG)]
        assert summary['attempted'] == 1 and summary['succeeded'] == 1 and summary['failed'] == 0
        ok = [r for r in logged_runs(db) if r['success']]
        assert len(ok) == 1
        assert ok[0]['schedule_id'] == scheduled_circle['team_update']['id']
        assert ok[0]['emails_sent'] == 2
        assert ok[0]['triggered_by'] == 'scheduler'

    def test_second_tick_for_the_same_occurrence_does_not_rerun(self, db, scheduled_circle, sent_emails):
        run_tick()
        summary, generators = run_tick(now=TICK_NOW + timedelta(hours=1))

        assert generators.calls == []
        assert summary['attempted'] == 0

    def test_missed_occurrence_past_retry_window_logs_synthetic_failure_and_alerts(
            self, db, scheduled_circle, sent_emails):
        summary, generators = run_tick()

        assert summary['expired'] == 1
        assert ('admin_digest', TEST_CIRCLE_SLUG) not in generators.calls  # never attempted
        missed = [r for r in logged_runs(db) if not r['success']]
        assert len(missed) == 1
        assert missed[0]['error_summary'] == MISSED_WINDOW_MESSAGE
        assert missed[0]['schedule_id'] == scheduled_circle['admin_digest']['id']
        assert summary['notified'] is True
        assert any(MISSED_WINDOW_MESSAGE in email['body'] for email in sent_emails)

    def test_synthetic_failure_is_not_reported_again_on_the_next_tick(self, db, scheduled_circle, sent_emails):
        run_tick()
        sent_emails.clear()
        summary, _ = run_tick(now=TICK_NOW + timedelta(hours=1))

        assert summary['expired'] == 0
        assert sent_emails == []

    def test_generator_reporting_errors_is_a_failure_and_is_never_auto_retried(
            self, db, scheduled_circle, sent_emails):
        generators = FakeGenerators(team_update={'emails_sent': 1, 'errors': ['SMTP exploded']})
        summary, _ = run_tick(generators=generators)
        assert summary['failed'] == 1

        failed = [r for r in logged_runs(db) if not r['success'] and r['email_type'] == 'team_update']
        assert len(failed) == 1 and 'SMTP exploded' in failed[0]['error_summary']

        summary, generators2 = run_tick(now=TICK_NOW + timedelta(hours=1), generators=generators)
        assert generators2.calls.count(('team_update', TEST_CIRCLE_SLUG)) == 1  # not retried

    def test_generator_raising_is_logged_and_does_not_stop_other_rows(self, db, scheduled_circle, sent_emails):
        # Make BOTH rows due: the 04:00 slot is only 1.5h old at 05:30 PST (13:30 UTC).
        now = utc(2026, 11, 20, 12, 30)  # 04:30 PST -> 04:00 slot 0.5h old; 07:00 slot from yesterday
        generators = FakeGenerators(admin_digest=RuntimeError('boom'))
        summary, _ = run_tick(now=now, generators=generators)

        assert summary['failed'] == 1
        failed = [r for r in logged_runs(db) if not r['success'] and r['email_type'] == 'admin_digest']
        assert len(failed) == 1 and failed[0]['error_summary'] == 'boom'

    def test_out_of_season_nothing_runs_and_nothing_is_logged(self, db, scheduled_circle, sent_emails):
        summary, generators = run_tick(now=OUT_OF_SEASON_NOW)

        assert generators.calls == []
        assert summary == {'attempted': 0, 'succeeded': 0, 'failed': 0, 'expired': 0,
                           'notified': False, 'skipped_locked': False}
        assert logged_runs(db) == []
        assert sent_emails == []

    def test_no_failures_means_no_notification_email(self, db, scheduled_circle, sent_emails):
        db.query(CircleEmailSchedule).filter_by(id=scheduled_circle['admin_digest']['id']).delete()
        db.commit()
        summary, _ = run_tick()

        assert summary['succeeded'] == 1 and summary['notified'] is False
        assert sent_emails == []

    def test_held_advisory_lock_makes_the_tick_skip(self, db, scheduled_circle, sent_emails):
        with tick_lock() as first:
            assert first is True
            summary, generators = run_tick()

        assert summary['skipped_locked'] is True
        assert generators.calls == []
        assert logged_runs(db) == []

    def test_lock_is_released_after_a_tick(self, db, scheduled_circle, sent_emails):
        run_tick()
        with tick_lock() as acquired:
            assert acquired is True

    def test_circle_with_no_count_date_is_skipped(self, db, second_test_circle, sent_emails):
        summary = tick(app.app, now_utc=TICK_NOW, generators=FakeGenerators().as_map(),
                       only_circles=[TEST_CIRCLE_SLUG_2])
        assert summary['attempted'] == 0 and summary['expired'] == 0


class TestFailureNotifications:
    def test_super_admins_get_the_detail_from_the_configured_sender(self, db, scheduled_circle, sent_emails):
        run_tick(generators=FakeGenerators(team_update={'emails_sent': 0, 'errors': ['SMTP exploded']}))

        super_email = next(e for e in sent_emails if 'cbc-test-admin1@naturevancouver.ca' in e['to'])
        assert 'SMTP exploded' in super_email['body']
        assert TEST_CIRCLE_SLUG in super_email['body']
        assert super_email['from'] == DEFAULT_SCHEDULER_ALERT_FROM_EMAIL
        assert '2 job(s) failed' in super_email['subject']  # the error + the missed 04:00 slot

    def test_sender_follows_the_app_setting(self, db, scheduled_circle, sent_emails):
        AppSettingsModel(db).set(SCHEDULER_ALERT_FROM_EMAIL_KEY, 'alerts@naturevancouver.ca')
        try:
            run_tick(generators=FakeGenerators(team_update={'emails_sent': 0, 'errors': ['x']}))
        finally:
            db.query(AppSetting).filter_by(key=SCHEDULER_ALERT_FROM_EMAIL_KEY).delete()
            db.commit()

        assert sent_emails and all(e['from'] == 'alerts@naturevancouver.ca' for e in sent_emails)

    def test_circle_admins_get_their_own_circles_failures_without_raw_error_text(
            self, db, scheduled_circle, circle_admin_row, sent_emails):
        run_tick(generators=FakeGenerators(team_update={'emails_sent': 0, 'errors': ['secret SQL detail']}))

        circle_email = next(e for e in sent_emails if CIRCLE_ADMIN_TEST_EMAIL in e['to'])
        assert 'team update' in circle_email['body']
        assert 'secret SQL detail' not in circle_email['body']
        super_email = next(e for e in sent_emails if 'cbc-test-admin1@naturevancouver.ca' in e['to'])
        assert CIRCLE_ADMIN_TEST_EMAIL not in super_email['to']

    def test_one_summary_email_per_tick_however_many_failures(self, db, scheduled_circle, sent_emails):
        run_tick(generators=FakeGenerators(team_update={'emails_sent': 0, 'errors': ['a']}))

        super_emails = [e for e in sent_emails if 'cbc-test-admin1@naturevancouver.ca' in e['to']]
        assert len(super_emails) == 1

    def test_a_failing_notification_send_does_not_break_the_tick(self, db, scheduled_circle, monkeypatch):
        def broken_send(*args, **kwargs):
            raise RuntimeError('SMTP down')
        monkeypatch.setattr(email_service, 'send_email', broken_send)

        summary, _ = run_tick(generators=FakeGenerators(team_update={'emails_sent': 0, 'errors': ['a']}))
        assert summary['failed'] == 1 and summary['notified'] is False


class TestRunManual:
    def test_manual_run_is_logged_with_the_admin_and_no_schedule_row(self, db, scheduled_circle, sent_emails):
        generators = FakeGenerators()
        result = run_manual(app.app, TEST_CIRCLE_SLUG, 'weekly_summary', 'admin@example.com',
                            now_utc=TICK_NOW, generators=generators.as_map())

        assert generators.calls == [('weekly_summary', TEST_CIRCLE_SLUG)]
        assert result['success'] is True
        assert result['schedule_id'] is None
        assert result['triggered_by'] == 'admin@example.com'

    def test_manual_run_does_not_suppress_the_scheduled_occurrence(self, db, scheduled_circle, sent_emails):
        run_manual(app.app, TEST_CIRCLE_SLUG, 'team_update', 'admin@example.com',
                   now_utc=TICK_NOW, generators=FakeGenerators().as_map())
        _, generators = run_tick()

        assert ('team_update', TEST_CIRCLE_SLUG) in generators.calls

    def test_manual_run_records_a_failure(self, db, scheduled_circle, sent_emails):
        generators = FakeGenerators(team_update={'emails_sent': 0, 'errors': ['nope']})
        result = run_manual(app.app, TEST_CIRCLE_SLUG, 'team_update', 'admin@example.com',
                            now_utc=TICK_NOW, generators=generators.as_map())
        assert result['success'] is False and result['error_summary'] == 'nope'

    def test_manual_run_refused_out_of_season(self, db, scheduled_circle, sent_emails):
        generators = FakeGenerators()
        with pytest.raises(ValueError, match='email season'):
            run_manual(app.app, TEST_CIRCLE_SLUG, 'team_update', 'admin@example.com',
                       now_utc=OUT_OF_SEASON_NOW, generators=generators.as_map())
        assert generators.calls == []
        assert MANUAL_RUN_OUT_OF_SEASON_MESSAGE.startswith('This circle')

    def test_manual_run_rejects_unknown_type_and_circle(self, db, scheduled_circle, sent_emails):
        generators = FakeGenerators().as_map()
        with pytest.raises(ValueError):
            run_manual(app.app, TEST_CIRCLE_SLUG, 'registration_confirmation', 'a@example.com',
                       now_utc=TICK_NOW, generators=generators)
        with pytest.raises(ValueError):
            run_manual(app.app, 'no-such-circle', 'team_update', 'a@example.com',
                       now_utc=TICK_NOW, generators=generators)


class TestScheduleModel:
    def test_new_circle_gets_the_default_schedule(self, db, second_test_circle):
        rows = CircleEmailScheduleModel(db).get_for_circle(TEST_CIRCLE_SLUG_2)
        assert {(r['email_type'], r['hour'], r['day_of_week']) for r in rows} == set(DEFAULT_SCHEDULE)

    def test_default_leader_update_times_are_7am_and_6pm(self):
        hours = sorted(h for t, h, d in DEFAULT_SCHEDULE if t == 'team_update')
        assert hours == [7, 18]

    def test_add_validates_input(self, db, scheduled_circle):
        model = CircleEmailScheduleModel(db)
        for bad in ({'email_type': 'registration_confirmation', 'hour': 5},
                    {'email_type': 'team_update', 'hour': 24},
                    {'email_type': 'team_update', 'hour': -1},
                    {'email_type': 'team_update', 'hour': True},
                    {'email_type': 'team_update', 'hour': 5, 'day_of_week': 7}):
            with pytest.raises(ValueError):
                model.add(TEST_CIRCLE_SLUG, **bad)

    def test_duplicate_slot_rejected_including_every_day_nulls(self, db, scheduled_circle):
        model = CircleEmailScheduleModel(db)
        with pytest.raises(ValueError, match='already exists'):
            model.add(TEST_CIRCLE_SLUG, 'team_update', 7)  # same hour, day NULL - NULLs must still collide
        model.add(TEST_CIRCLE_SLUG, 'team_update', 7, 2)  # same hour, specific day is a different slot

    def test_slot_cap_per_email_type(self, db, scheduled_circle):
        model = CircleEmailScheduleModel(db)
        for hour in range(8, 8 + MAX_SLOTS_PER_EMAIL_TYPE - 1):
            model.add(TEST_CIRCLE_SLUG, 'team_update', hour)
        with pytest.raises(ValueError, match='At most'):
            model.add(TEST_CIRCLE_SLUG, 'team_update', 22)

    def test_remove_only_deletes_within_the_given_circle(self, db, scheduled_circle, second_test_circle):
        model = CircleEmailScheduleModel(db)
        other = model.get_for_circle(TEST_CIRCLE_SLUG_2)[0]

        assert model.remove(other['id'], TEST_CIRCLE_SLUG) is False
        assert any(r['id'] == other['id'] for r in model.get_for_circle(TEST_CIRCLE_SLUG_2))
        assert model.remove(other['id'], TEST_CIRCLE_SLUG_2) is True

    def test_create_defaults_is_idempotent(self, db, second_test_circle):
        model = CircleEmailScheduleModel(db)
        model.create_defaults(TEST_CIRCLE_SLUG_2)
        assert len(model.get_for_circle(TEST_CIRCLE_SLUG_2)) == len(DEFAULT_SCHEDULE)


class TestAppSettings:
    def test_alert_sender_defaults_when_unset(self, db):
        db.query(AppSetting).filter_by(key=SCHEDULER_ALERT_FROM_EMAIL_KEY).delete()
        db.commit()
        assert AppSettingsModel(db).get_scheduler_alert_from_email() == 'birdcount@naturevancouver.ca'

    def test_set_then_get_and_overwrite(self, db):
        model = AppSettingsModel(db)
        try:
            model.set(SCHEDULER_ALERT_FROM_EMAIL_KEY, 'a@naturevancouver.ca', updated_by='me@example.com')
            model.set(SCHEDULER_ALERT_FROM_EMAIL_KEY, 'b@naturevancouver.ca')
            assert model.get_scheduler_alert_from_email() == 'b@naturevancouver.ca'
        finally:
            db.query(AppSetting).filter_by(key=SCHEDULER_ALERT_FROM_EMAIL_KEY).delete()
            db.commit()
