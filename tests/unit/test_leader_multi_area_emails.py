# Created by Claude AI on 2026-09-28
"""
Tests for per-area team-update/weekly-summary emails when one person leads
more than one area. test/email_generator.py's generate_team_update_emails/
generate_weekly_summary_emails loop over AREAS, not over leaders, so a person
leading two areas should receive two independent emails, each deep-linking to
its own area's dashboard tab (routes/leader.py's dashboard(), ?area=<code>).
No live server needed - calls the generator functions directly, same pattern
as tests/unit/test_digest_email_content.py.
"""

from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from config.database import get_db_session
from models.db import EmailTimestamp
from models.participant import ParticipantModel
from test.email_generator import EmailTimestampModel, generate_team_update_emails, generate_weekly_summary_emails
from tests.test_config import TEST_CIRCLE_SLUG
from tests.utils.database_utils import create_database_manager

MULTI_AREA_EMAIL = 'multi.area.email.leader@example.com'
ADMIN_ACTOR = 'test-admin@example.com'


@pytest.fixture
def db_session():
    return get_db_session()


@pytest.fixture(autouse=True)
def cleanup(db_session):
    mgr = create_database_manager(db_session)
    mgr.clear_test_collections()
    db_session.query(EmailTimestamp).filter_by(circle_slug=TEST_CIRCLE_SLUG).delete()
    db_session.commit()
    yield
    mgr.clear_test_collections()
    db_session.query(EmailTimestamp).filter_by(circle_slug=TEST_CIRCLE_SLUG).delete()
    db_session.commit()


@pytest.fixture
def participant_model(db_session):
    current_year = datetime.now().year
    return ParticipantModel(db_session, current_year, TEST_CIRCLE_SLUG)


def _make_leader(participant_model, first_name, last_name, area):
    pid = participant_model.add_participant({
        'first_name': first_name, 'last_name': last_name, 'email': MULTI_AREA_EMAIL,
        'preferred_area': area, 'participation_type': 'regular', 'phone': '250-555-0000',
    })
    participant_model.assign_area_leadership(pid, area, ADMIN_ACTOR)
    return pid


def _make_member(participant_model, first_name, area):
    return participant_model.add_participant({
        'first_name': first_name, 'last_name': 'Member', 'email': f'{first_name.lower()}@example.com',
        'preferred_area': area, 'participation_type': 'regular',
    })


class _Capture:
    """Stand-in for services.email_service.email_service.send_email."""

    def __init__(self):
        self.emails = []

    def send(self, recipients, subject, text_content, html_content=None, **kwargs):
        self.emails.append({
            'recipients': recipients if isinstance(recipients, list) else [recipients],
            'subject': subject,
            'html': html_content,
        })
        return True


def _by_area(emails, area_label):
    matches = [e for e in emails if area_label in e['subject']]
    assert len(matches) == 1, f"expected exactly one email mentioning {area_label!r}, got {len(matches)}"
    return matches[0]


class TestTeamUpdatePerArea:
    def test_leader_of_two_changed_areas_gets_two_separate_emails(self, participant_model):
        _make_leader(participant_model, 'HarveyA', 'Dueck', 'A')
        _make_leader(participant_model, 'Harvey', 'Dueck', 'B')
        _make_member(participant_model, 'Alice', 'A')
        _make_member(participant_model, 'Bob', 'B')

        import app as app_module
        capture = _Capture()
        with patch('services.email_service.email_service.send_email', side_effect=capture.send):
            results = generate_team_update_emails(app_module.app, TEST_CIRCLE_SLUG)

        assert results['emails_sent'] == 2
        email_a = _by_area(capture.emails, 'Area A')
        email_b = _by_area(capture.emails, 'Area B')
        assert MULTI_AREA_EMAIL in email_a['recipients']
        assert MULTI_AREA_EMAIL in email_b['recipients']

    def test_each_areas_email_deep_links_to_its_own_tab(self, participant_model):
        _make_leader(participant_model, 'HarveyA', 'Dueck', 'A')
        _make_leader(participant_model, 'Harvey', 'Dueck', 'B')
        _make_member(participant_model, 'Alice', 'A')
        _make_member(participant_model, 'Bob', 'B')

        import app as app_module
        capture = _Capture()
        with patch('services.email_service.email_service.send_email', side_effect=capture.send):
            generate_team_update_emails(app_module.app, TEST_CIRCLE_SLUG)

        email_a = _by_area(capture.emails, 'Area A')
        email_b = _by_area(capture.emails, 'Area B')
        assert '/leader?area=A' in email_a['html']
        assert '?area=B' not in email_a['html']
        assert '/leader?area=B' in email_b['html']
        assert '?area=A' not in email_b['html']

    def test_only_the_area_with_changes_triggers_an_email(self, participant_model, db_session):
        """Area B is marked 'already emailed as of now' before Area A gets a
        new registrant, so only Area A should send - leading two areas must
        not cross-trigger notifications for the untouched one."""
        _make_leader(participant_model, 'HarveyA', 'Dueck', 'A')
        _make_leader(participant_model, 'Harvey', 'Dueck', 'B')
        _make_member(participant_model, 'Bob', 'B')

        current_year = datetime.now().year
        EmailTimestampModel(db_session, current_year, TEST_CIRCLE_SLUG).update_last_email_sent(
            'B', 'team_update', datetime.now(timezone.utc))

        _make_member(participant_model, 'Alice', 'A')

        import app as app_module
        capture = _Capture()
        with patch('services.email_service.email_service.send_email', side_effect=capture.send):
            results = generate_team_update_emails(app_module.app, TEST_CIRCLE_SLUG)

        assert results['emails_sent'] == 1
        assert len(capture.emails) == 1
        assert 'Area A' in capture.emails[0]['subject']


class TestWeeklySummaryPerArea:
    def test_leader_of_two_areas_gets_two_separate_weekly_summaries(self, participant_model):
        _make_leader(participant_model, 'HarveyA', 'Dueck', 'A')
        _make_leader(participant_model, 'Harvey', 'Dueck', 'B')
        _make_member(participant_model, 'Alice', 'A')
        _make_member(participant_model, 'Bob', 'B')

        import app as app_module
        capture = _Capture()
        with patch('services.email_service.email_service.send_email', side_effect=capture.send):
            results = generate_weekly_summary_emails(app_module.app, TEST_CIRCLE_SLUG)

        assert results['emails_sent'] == 2
        email_a = _by_area(capture.emails, 'Area A')
        email_b = _by_area(capture.emails, 'Area B')
        assert '/leader?area=A' in email_a['html']
        assert '/leader?area=B' in email_b['html']


class TestPreviewDeepLink:
    """The admin email-content preview route (build_team_update_preview /
    build_weekly_summary_preview) uses a hardcoded sample area 'A' - its
    dashboard link should carry that through too."""

    def test_team_update_preview_links_to_area_a(self, admin_client):
        resp = admin_client.get(f'/bigbird/circles/{TEST_CIRCLE_SLUG}/email-content/preview/team_update')
        assert resp.status_code == 200
        assert b'?area=A' in resp.data

    def test_weekly_summary_preview_links_to_area_a(self, admin_client):
        resp = admin_client.get(f'/bigbird/circles/{TEST_CIRCLE_SLUG}/email-content/preview/weekly_summary')
        assert resp.status_code == 200
        assert b'?area=A' in resp.data
