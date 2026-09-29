# Updated by Claude AI on 2026-09-28
"""
Tests for the scheduled-email admin UI (routes/admin.py): a circle's own
email-schedule page (circle-admin for that circle, or any super-admin) and the
super-admin-only Scheduler console (alert sender setting + guarded manual run).
"""

from datetime import date

import pytest

from config.database import get_db_session
from models.app_settings import SCHEDULER_ALERT_FROM_EMAIL_KEY, AppSettingsModel
from models.db import AppSetting, CircleEmailSchedule, EmailScheduleRunLog
from models.email_schedule import DEFAULT_SCHEDULE, CircleEmailScheduleModel
from services import scheduler_service
from tests.test_config import TEST_CIRCLE_SLUG, TEST_CIRCLE_SLUG_2

SCHEDULE_URL = f'/bigbird/circles/{TEST_CIRCLE_SLUG}/email-schedule'
CONSOLE_URL = '/bigbird/scheduler'


@pytest.fixture
def db():
    return get_db_session()


@pytest.fixture(autouse=True)
def default_schedule_restored(db):
    """Every test here may add/remove rows for the shared 'test' circle - put its
    schedule back to exactly the defaults (and clear its run log) afterwards."""
    yield
    db.rollback()
    db.query(EmailScheduleRunLog).filter_by(circle_slug=TEST_CIRCLE_SLUG).delete()
    db.query(CircleEmailSchedule).filter_by(circle_slug=TEST_CIRCLE_SLUG).delete()
    db.commit()
    CircleEmailScheduleModel(db).create_defaults(TEST_CIRCLE_SLUG)
    db.query(AppSetting).filter_by(key=SCHEDULER_ALERT_FROM_EMAIL_KEY).delete()
    db.commit()


def rows(db, slug=TEST_CIRCLE_SLUG):
    db.expire_all()
    return CircleEmailScheduleModel(db).get_for_circle(slug)


def form(**overrides):
    data = {'action': 'add', 'email_type': 'team_update', 'hour': '12', 'day_of_week': ''}
    data.update(overrides)
    return data


class TestSchedulePageAccess:
    def test_anonymous_redirected_to_login(self, client):
        assert client.get(SCHEDULE_URL).status_code == 302

    def test_circle_admin_can_view_own_circle(self, admin_client):
        resp = admin_client.get(SCHEDULE_URL)
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert 'Leader team update' in html
        assert '7:00 am' in html and '6:00 pm' in html  # the default leader-update times

    def test_circle_admin_cannot_reach_another_circle(self, admin_client, second_test_circle):
        resp = admin_client.get(f'/bigbird/circles/{TEST_CIRCLE_SLUG_2}/email-schedule')
        assert resp.status_code == 302

    def test_super_admin_can_view_any_circle(self, super_admin_client, second_test_circle):
        resp = super_admin_client.get(f'/bigbird/circles/{TEST_CIRCLE_SLUG_2}/email-schedule')
        assert resp.status_code == 200

    def test_anonymous_cannot_post(self, client, db):
        before = rows(db)
        assert client.post(SCHEDULE_URL, data=form()).status_code == 302
        assert rows(db) == before


class TestScheduleEditing:
    def test_add_a_send_time(self, admin_client, db):
        resp = admin_client.post(SCHEDULE_URL, data=form(hour='12', day_of_week='2'), follow_redirects=True)
        assert 'Send time added.' in resp.get_data(as_text=True)
        assert any(r['email_type'] == 'team_update' and r['hour'] == 12 and r['day_of_week'] == 2
                   for r in rows(db))

    def test_duplicate_is_rejected_with_a_message(self, admin_client, db):
        resp = admin_client.post(SCHEDULE_URL, data=form(hour='7'), follow_redirects=True)  # default 7am exists
        assert 'already exists' in resp.get_data(as_text=True)
        assert len([r for r in rows(db) if r['hour'] == 7 and r['email_type'] == 'team_update']) == 1

    @pytest.mark.parametrize('bad', [
        {'hour': '24'}, {'hour': 'abc'}, {'hour': ''}, {'day_of_week': '9'}, {'day_of_week': 'x'},
        {'email_type': 'registration_confirmation'}, {'email_type': ''},
    ])
    def test_invalid_input_changes_nothing(self, admin_client, db, bad):
        before = rows(db)
        admin_client.post(SCHEDULE_URL, data=form(**bad))
        assert rows(db) == before

    def test_remove_a_send_time(self, admin_client, db):
        target = next(r for r in rows(db) if r['email_type'] == 'admin_digest')
        resp = admin_client.post(SCHEDULE_URL, data={'action': 'remove', 'schedule_id': str(target['id'])},
                                 follow_redirects=True)
        assert 'Send time removed.' in resp.get_data(as_text=True)
        assert all(r['id'] != target['id'] for r in rows(db))

    def test_circle_admin_cannot_delete_another_circles_row_by_guessing_its_id(
            self, admin_client, db, second_test_circle):
        other = rows(db, TEST_CIRCLE_SLUG_2)[0]
        admin_client.post(SCHEDULE_URL, data={'action': 'remove', 'schedule_id': str(other['id'])})
        assert any(r['id'] == other['id'] for r in rows(db, TEST_CIRCLE_SLUG_2))

    def test_circle_admin_cannot_post_to_another_circle(self, admin_client, db, second_test_circle):
        before = rows(db, TEST_CIRCLE_SLUG_2)
        admin_client.post(f'/bigbird/circles/{TEST_CIRCLE_SLUG_2}/email-schedule', data=form())
        assert rows(db, TEST_CIRCLE_SLUG_2) == before

    def test_unknown_action_changes_nothing(self, admin_client, db):
        before = rows(db)
        admin_client.post(SCHEDULE_URL, data={'action': 'nuke'})
        assert rows(db) == before
        assert len(before) == len(DEFAULT_SCHEDULE)


class TestSchedulerConsoleAccess:
    @pytest.mark.parametrize('method,url', [
        ('get', CONSOLE_URL), ('post', CONSOLE_URL + '/settings'), ('post', CONSOLE_URL + '/run'),
    ])
    def test_circle_admin_is_refused(self, admin_client, method, url):
        resp = getattr(admin_client, method)(url, data={})
        assert resp.status_code == 302

    def test_circle_admin_cannot_run_or_change_settings(self, admin_client, db, monkeypatch):
        calls = []
        monkeypatch.setattr(scheduler_service, 'run_manual', lambda *a, **k: calls.append(a))
        admin_client.post(CONSOLE_URL + '/run', data={
            'circle_slug': TEST_CIRCLE_SLUG, 'email_type': 'team_update', 'confirm_slug': TEST_CIRCLE_SLUG})
        admin_client.post(CONSOLE_URL + '/settings', data={'alert_from_email': 'x@naturevancouver.ca'})
        assert calls == []
        assert AppSettingsModel(db).get(SCHEDULER_ALERT_FROM_EMAIL_KEY) == 'birdcount@naturevancouver.ca'

    def test_anonymous_is_redirected(self, client):
        assert client.get(CONSOLE_URL).status_code == 302

    def test_super_admin_sees_console(self, super_admin_client):
        resp = super_admin_client.get(CONSOLE_URL)
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert 'Failure alerts' in html and 'Manual run' in html
        assert 'birdcount@naturevancouver.ca' in html


class TestAlertSenderSetting:
    def test_super_admin_can_change_it(self, super_admin_client, db):
        resp = super_admin_client.post(CONSOLE_URL + '/settings', data={'alert_from_email': 'alerts@naturevancouver.ca'},
                                       follow_redirects=True)
        assert 'Alert sender updated.' in resp.get_data(as_text=True)
        assert AppSettingsModel(db).get_scheduler_alert_from_email() == 'alerts@naturevancouver.ca'

    @pytest.mark.parametrize('bad', ['alerts@evil.example.com', 'not-an-email', ''])
    def test_domain_allowlist_and_format_enforced(self, super_admin_client, db, bad):
        super_admin_client.post(CONSOLE_URL + '/settings', data={'alert_from_email': bad})
        assert AppSettingsModel(db).get_scheduler_alert_from_email() == 'birdcount@naturevancouver.ca'


class TestManualRun:
    @pytest.fixture
    def run_calls(self, monkeypatch):
        calls = []

        def fake_run_manual(app_arg, slug, email_type, triggered_by, **kwargs):
            calls.append((slug, email_type, triggered_by))
            return {'success': True, 'emails_sent': 3, 'error_summary': None}

        monkeypatch.setattr(scheduler_service, 'run_manual', fake_run_manual)
        return calls

    def test_requires_the_slug_typed_as_confirmation(self, super_admin_client, run_calls):
        for confirm in ('', 'wrong', TEST_CIRCLE_SLUG_2):
            resp = super_admin_client.post(CONSOLE_URL + '/run', data={
                'circle_slug': TEST_CIRCLE_SLUG, 'email_type': 'team_update', 'confirm_slug': confirm},
                follow_redirects=True)
            assert 'nothing was run' in resp.get_data(as_text=True)
        assert run_calls == []

    def test_missing_slug_never_runs(self, super_admin_client, run_calls):
        super_admin_client.post(CONSOLE_URL + '/run', data={'email_type': 'team_update', 'confirm_slug': ''})
        assert run_calls == []

    def test_confirmed_run_is_attributed_to_the_admin(self, super_admin_client, run_calls):
        resp = super_admin_client.post(CONSOLE_URL + '/run', data={
            'circle_slug': TEST_CIRCLE_SLUG, 'email_type': 'weekly_summary',
            'confirm_slug': f'  {TEST_CIRCLE_SLUG.upper()} '}, follow_redirects=True)
        assert run_calls == [(TEST_CIRCLE_SLUG, 'weekly_summary', 'cbc-test-admin1@naturevancouver.ca')]
        assert '3 email(s) sent' in resp.get_data(as_text=True)

    def test_out_of_season_refusal_is_shown_not_raised(self, super_admin_client, monkeypatch):
        def refuse(*args, **kwargs):
            raise ValueError(scheduler_service.MANUAL_RUN_OUT_OF_SEASON_MESSAGE)

        monkeypatch.setattr(scheduler_service, 'run_manual', refuse)
        resp = super_admin_client.post(CONSOLE_URL + '/run', data={
            'circle_slug': TEST_CIRCLE_SLUG, 'email_type': 'team_update', 'confirm_slug': TEST_CIRCLE_SLUG},
            follow_redirects=True)
        assert resp.status_code == 200
        assert 'outside its email season' in resp.get_data(as_text=True)

    def test_failed_run_is_reported_as_a_failure(self, super_admin_client, monkeypatch):
        monkeypatch.setattr(scheduler_service, 'run_manual', lambda *a, **k: {
            'success': False, 'emails_sent': 0, 'error_summary': 'SMTP exploded'})
        resp = super_admin_client.post(CONSOLE_URL + '/run', data={
            'circle_slug': TEST_CIRCLE_SLUG, 'email_type': 'team_update', 'confirm_slug': TEST_CIRCLE_SLUG},
            follow_redirects=True)
        assert 'FAILED' in resp.get_data(as_text=True) and 'SMTP exploded' in resp.get_data(as_text=True)


class TestSeasonSummary:
    CIRCLE = {'yearly_count_dates': {2026: '2026-12-19', 2027: '2027-12-18'}, 'registration_opens_months': 4}

    def test_in_season(self):
        summary = scheduler_service.season_summary(self.CIRCLE, date(2026, 11, 1))
        assert summary == {'in_season': True, 'starts': date(2026, 8, 19), 'ends': date(2026, 12, 19)}

    def test_between_seasons_points_at_the_next_one(self):
        summary = scheduler_service.season_summary(self.CIRCLE, date(2027, 3, 1))
        assert summary == {'in_season': False, 'starts': date(2027, 8, 18), 'ends': date(2027, 12, 18)}

    def test_no_future_count_date(self):
        summary = scheduler_service.season_summary(self.CIRCLE, date(2028, 1, 1))
        assert summary == {'in_season': False, 'starts': None, 'ends': None}

    def test_no_count_dates_at_all(self):
        summary = scheduler_service.season_summary({'yearly_count_dates': {}}, date(2026, 11, 1))
        assert summary == {'in_season': False, 'starts': None, 'ends': None}
