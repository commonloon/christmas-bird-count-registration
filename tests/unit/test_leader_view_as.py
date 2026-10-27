# Created by Claude AI on 2026-10-27
"""
Tests for the admin-only read-only "view as leader" on the leader dashboard
(routes/leader.py's dashboard(), ?as=<email>). Flask-test-client-based, no live
server needed (see tests/unit/conftest.py).
"""

from datetime import datetime

import pytest

from config.database import get_db_session
from models.participant import ParticipantModel
from tests.test_config import TEST_CIRCLE_SLUG, TEST_CIRCLE_SLUG_2
from tests.utils.database_utils import create_database_manager

ADMIN_EMAIL = 'cbc-test-admin1@naturevancouver.ca'
LEADER_EMAIL = 'view.as.leader@example.com'
OTHER_LEADER_EMAIL = 'view.as.other@example.com'
ADMIN_ACTOR = 'test-admin@example.com'


@pytest.fixture
def db_session():
    return get_db_session()


@pytest.fixture(autouse=True)
def cleanup_test_data(db_session):
    db_manager = create_database_manager(db_session)
    db_manager.clear_test_collections()
    yield
    db_manager.clear_test_collections()


@pytest.fixture
def participant_model(db_session):
    return ParticipantModel(db_session, datetime.now().year, TEST_CIRCLE_SLUG)


def _session(client, email):
    with client.session_transaction() as sess:
        sess['user_email'] = email
        sess['user_name'] = 'Test User'


def _make_leader(model, first_name, last_name, email, area):
    pid = model.add_participant({
        'first_name': first_name, 'last_name': last_name, 'email': email,
        'preferred_area': area, 'participation_type': 'regular', 'phone': '250-555-0000',
    })
    model.assign_area_leadership(pid, area, ADMIN_ACTOR)
    return pid


def _make_member(model, first_name, area):
    return model.add_participant({
        'first_name': first_name, 'last_name': 'TeamTest',
        'email': f'{first_name.lower()}@example.com',
        'preferred_area': area, 'participation_type': 'regular',
    })


@pytest.fixture
def two_leaders(participant_model):
    _make_leader(participant_model, 'Peter', 'Viewed', LEADER_EMAIL, 'A')
    _make_leader(participant_model, 'Olive', 'Other', OTHER_LEADER_EMAIL, 'B')
    _make_member(participant_model, 'Alice', 'A')
    _make_member(participant_model, 'Bob', 'B')


class TestAdminViewAs:
    def test_admin_sees_leaders_dashboard_and_banner(self, client, two_leaders):
        _session(client, ADMIN_EMAIL)
        resp = client.get('/leader', query_string={'as': LEADER_EMAIL})
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert 'Leader Dashboard - Area A' in html
        assert 'Alice' in html and 'Bob' not in html
        assert 'Admin preview' in html
        assert 'Peter Viewed' in html

    def test_admin_without_as_gets_picker_listing_leaders(self, client, two_leaders):
        _session(client, ADMIN_EMAIL)
        resp = client.get('/leader')
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert 'Peter Viewed' in html and 'Olive Other' in html
        assert LEADER_EMAIL in html

    def test_email_matching_is_case_insensitive(self, client, two_leaders):
        _session(client, ADMIN_EMAIL)
        html = client.get('/leader', query_string={'as': LEADER_EMAIL.upper()}).get_data(as_text=True)
        assert 'Leader Dashboard - Area A' in html

    def test_non_leader_email_is_rejected_with_redirect(self, client, two_leaders):
        _session(client, ADMIN_EMAIL)
        resp = client.get('/leader', query_string={'as': 'nobody@example.com'})
        assert resp.status_code == 302
        assert 'as=' not in resp.headers.get('Location', '')

    def test_leader_in_a_different_circle_is_not_viewable(self, client, db_session, participant_model):
        other_model = ParticipantModel(db_session, datetime.now().year, TEST_CIRCLE_SLUG_2)
        other_mgr = create_database_manager(db_session, TEST_CIRCLE_SLUG_2)
        try:
            _make_leader(other_model, 'Cross', 'Circle', OTHER_LEADER_EMAIL, 'Z')
            _session(client, ADMIN_EMAIL)
            resp = client.get('/leader', query_string={'as': OTHER_LEADER_EMAIL})
            assert resp.status_code == 302
        finally:
            other_mgr.clear_test_collections()

    def test_tab_and_year_links_keep_the_view_as_param(self, client, participant_model, db_session):
        _make_leader(participant_model, 'Harvey', 'Two', LEADER_EMAIL, 'A')
        _make_leader(participant_model, 'HarveyB', 'Two', LEADER_EMAIL, 'B')
        ParticipantModel(db_session, 2000, TEST_CIRCLE_SLUG).add_participant({
            'first_name': 'OldTimer', 'last_name': 'Test', 'email': 'old@example.com',
            'preferred_area': 'A', 'participation_type': 'regular',
        })
        _session(client, ADMIN_EMAIL)
        html = client.get('/leader', query_string={'as': LEADER_EMAIL}).get_data(as_text=True)
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')
        pill_hrefs = [a.get('href') for a in soup.select('ul.nav-pills a.nav-link')]
        year_hrefs = [a.get('href') for a in soup.select('ul.nav-tabs a.nav-link')]
        assert pill_hrefs and all('as=' in h for h in pill_hrefs)
        assert year_hrefs and all('as=' in h for h in year_hrefs)

    def test_malicious_as_param_is_not_reflected(self, client, two_leaders):
        _session(client, ADMIN_EMAIL)
        payload = '<script>alert(1)</script>'
        resp = client.get('/leader', query_string={'as': payload}, follow_redirects=True)
        assert payload not in resp.get_data(as_text=True)


class TestNonAdminCannotViewAs:
    def test_leader_as_param_is_ignored(self, client, two_leaders):
        _session(client, LEADER_EMAIL)
        html = client.get('/leader', query_string={'as': OTHER_LEADER_EMAIL}).get_data(as_text=True)
        assert 'Leader Dashboard - Area A' in html
        assert 'Bob' not in html
        assert 'Admin preview' not in html
        assert 'View as leader' not in html

    def test_leader_dashboard_without_as_has_no_selector(self, client, two_leaders):
        _session(client, LEADER_EMAIL)
        html = client.get('/leader').get_data(as_text=True)
        assert 'View as leader' not in html
        assert OTHER_LEADER_EMAIL not in html


class TestWeeklySummaryPreview:
    def test_preview_shown_to_admin_in_view_as_only(self, client, two_leaders):
        _session(client, ADMIN_EMAIL)
        html = client.get('/leader', query_string={'as': LEADER_EMAIL}).get_data(as_text=True)
        assert 'Weekly Summary Email Preview - Area A' in html
        assert '<iframe' in html and 'srcdoc=' in html
        assert LEADER_EMAIL in html  # recipients line

    def test_preview_not_shown_to_leader(self, client, two_leaders):
        _session(client, LEADER_EMAIL)
        html = client.get('/leader', query_string={'as': LEADER_EMAIL}).get_data(as_text=True)
        assert 'Weekly Summary Email Preview' not in html

    def test_preview_never_sends_or_writes_timestamp(self, client, two_leaders, db_session, monkeypatch):
        from services.email_service import email_service
        from test.email_generator import EmailTimestampModel
        sent = []
        monkeypatch.setattr(email_service, 'send_email', lambda *a, **k: sent.append(a) or True)
        year = datetime.now().year
        before = EmailTimestampModel(db_session, year, TEST_CIRCLE_SLUG).get_last_email_sent('A', 'weekly_summary')
        _session(client, ADMIN_EMAIL)
        resp = client.get('/leader', query_string={'as': LEADER_EMAIL})
        assert 'Weekly Summary Email Preview' in resp.get_data(as_text=True)
        after = EmailTimestampModel(db_session, year, TEST_CIRCLE_SLUG).get_last_email_sent('A', 'weekly_summary')
        assert sent == []
        assert before == after

    def test_preview_html_is_escaped_inside_srcdoc(self, client, two_leaders):
        _session(client, ADMIN_EMAIL)
        html = client.get('/leader', query_string={'as': LEADER_EMAIL}).get_data(as_text=True)
        srcdoc = html.split('srcdoc="', 1)[1].split('"', 1)[0]
        assert '<' not in srcdoc and '&lt;' in srcdoc

    def test_historical_year_has_no_preview(self, client, two_leaders):
        _session(client, ADMIN_EMAIL)
        html = client.get('/leader', query_string={'as': LEADER_EMAIL, 'year': 2000}).get_data(as_text=True)
        assert 'Weekly Summary Email Preview' not in html
