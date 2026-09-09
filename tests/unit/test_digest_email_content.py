# Updated by Claude AI on 2026-09-09
"""
Tests for Stage 2 of the email content customization feature
(EMAIL_CUSTOMIZATION_PLAN.txt): the three Task-Scheduler-driven digest emails
(team_update, weekly_summary, admin_digest) becoming admin-customizable, and
the admin_digest recipients fix (union of circle-admins + global ADMIN_EMAILS).

See tests/unit/test_email_content.py for the Stage 1 (registration/withdrawal)
tests this builds on - the underlying resolution/substitution/route mechanics
are shared and already covered there; this file focuses on what's new here:
the three additional email types, per-area subject substitution, and the
digest recipients change.
"""

from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from config.database import get_db_session
from config.email_content_blocks import get_blocks, get_email_types
from models.circle import CircleAdminModel
from models.db import EmailContentDefault, EmailContentOverride, Participant
from models.email_content import EmailContentModel
from models.participant import ParticipantModel
from tests.test_config import TEST_CIRCLE_SLUG

DIGEST_EMAIL_TYPES = ('team_update', 'weekly_summary', 'admin_digest')


class TestDigestBlockRegistry:
    def test_all_three_digest_types_registered(self):
        for email_type in DIGEST_EMAIL_TYPES:
            assert email_type in get_email_types()

    def test_team_update_has_expected_blocks(self):
        assert set(get_blocks('team_update').keys()) == {'subject', 'greeting_intro', 'next_steps_body'}

    def test_weekly_summary_has_expected_blocks(self):
        assert set(get_blocks('weekly_summary').keys()) == {'subject', 'next_steps_body'}

    def test_admin_digest_has_expected_blocks(self):
        assert set(get_blocks('admin_digest').keys()) == {
            'subject', 'greeting_salutation', 'recommended_actions_body'}

    def test_subject_fallbacks_no_longer_hardcode_vancouver(self):
        """The block registry's fallback text replaces what used to be
        config/email_settings.py's EMAIL_SUBJECTS dict, which hardcoded
        "Vancouver CBC" unconditionally regardless of which circle the email
        was actually for - a real cross-circle bug. Pin that it's gone."""
        for email_type in DIGEST_EMAIL_TYPES:
            fallback = get_blocks(email_type)['subject']['fallback']
            assert 'Vancouver' not in fallback


@pytest.fixture
def db_session():
    return get_db_session()


@pytest.fixture(autouse=True)
def clean_up_test_rows(db_session):
    """Same convention as test_email_content.py - 'test' is the dedicated
    always-safe-to-wipe circle."""
    def _clean():
        db_session.query(EmailContentDefault).filter(
            EmailContentDefault.email_type.in_(DIGEST_EMAIL_TYPES),
        ).delete(synchronize_session=False)
        db_session.query(EmailContentOverride).filter(
            EmailContentOverride.email_type.in_(DIGEST_EMAIL_TYPES),
            EmailContentOverride.circle_slug == TEST_CIRCLE_SLUG,
        ).delete(synchronize_session=False)
        db_session.commit()

    _clean()
    yield
    _clean()


class TestDigestPreviewRoutes:
    def test_team_update_preview_renders(self, admin_client):
        resp = admin_client.get(f'/bigbird/circles/{TEST_CIRCLE_SLUG}/email-content/preview/team_update')
        assert resp.status_code == 200
        assert b'Team Update' in resp.data

    def test_weekly_summary_preview_renders(self, admin_client):
        resp = admin_client.get(f'/bigbird/circles/{TEST_CIRCLE_SLUG}/email-content/preview/weekly_summary')
        assert resp.status_code == 200
        assert b'Weekly Summary' in resp.data

    def test_admin_digest_preview_renders(self, admin_client):
        resp = admin_client.get(f'/bigbird/circles/{TEST_CIRCLE_SLUG}/email-content/preview/admin_digest')
        assert resp.status_code == 200
        assert b'Unassigned Participants' in resp.data


class TestDigestOverrideReachesPreview:
    """Mirrors test_email_content.py's TestOverrideReachesGeneratedEmail - a
    saved override must actually show up in the rendered preview output, not
    just resolve_all(). One check per digest type is enough here since the
    underlying resolve/substitute/render mechanism is already proven generic
    by the Stage 1 tests; what's actually new per-type is covered instead by
    TestDigestBlockRegistry (right blocks exist) and the subject-substitution
    test below (per-area placeholder correctness)."""

    def test_team_update_next_steps_override_appears(self, db_session, admin_client):
        EmailContentModel(db_session).set_override(
            TEST_CIRCLE_SLUG, 'team_update', 'next_steps_body',
            'TEAM UPDATE MARKER: bring snacks.', 'tester@example.com',
        )
        resp = admin_client.get(f'/bigbird/circles/{TEST_CIRCLE_SLUG}/email-content/preview/team_update')
        assert b'TEAM UPDATE MARKER: bring snacks.' in resp.data

    def test_weekly_summary_next_steps_override_appears(self, db_session, admin_client):
        EmailContentModel(db_session).set_override(
            TEST_CIRCLE_SLUG, 'weekly_summary', 'next_steps_body',
            'WEEKLY SUMMARY MARKER: check the weather.', 'tester@example.com',
        )
        resp = admin_client.get(f'/bigbird/circles/{TEST_CIRCLE_SLUG}/email-content/preview/weekly_summary')
        assert b'WEEKLY SUMMARY MARKER: check the weather.' in resp.data

    def test_admin_digest_recommended_actions_override_appears(self, db_session, admin_client):
        EmailContentModel(db_session).set_override(
            TEST_CIRCLE_SLUG, 'admin_digest', 'recommended_actions_body',
            'ADMIN DIGEST MARKER: check the queue.', 'tester@example.com',
        )
        resp = admin_client.get(f'/bigbird/circles/{TEST_CIRCLE_SLUG}/email-content/preview/admin_digest')
        assert b'ADMIN DIGEST MARKER: check the queue.' in resp.data

    def test_team_update_subject_substitutes_date_and_area_code(self, db_session, admin_client):
        """The subject block is resolved once per circle but substituted fresh
        per area (team_update/weekly_summary send one email per area) - pin
        that $date/$area_code actually get replaced with real values, not
        left as literal placeholder text."""
        EmailContentModel(db_session).set_override(
            TEST_CIRCLE_SLUG, 'team_update', 'subject',
            'Area $area_code update for $date', 'tester@example.com',
        )
        resp = admin_client.get(f'/bigbird/circles/{TEST_CIRCLE_SLUG}/email-content/preview/team_update')
        assert b'$area_code' not in resp.data
        assert b'$date' not in resp.data
        assert b'Area A update for' in resp.data


class TestAdminDigestRecipients:
    """The plan's recipients fix: admin_digest must go to the union of this
    circle's own circle-admins AND the global super-admin whitelist, not just
    the global list (which was the pre-existing behavior before this
    session's change - backward-compatible for Vancouver since its admins
    were already in that global list, but silently excluded a circle's own
    self-service admins otherwise)."""

    def test_recipients_include_both_circle_admin_and_global_admins(self, db_session):
        from config.admins import ADMIN_EMAILS
        import app as app_module
        from test.email_generator import generate_admin_digest_email

        current_year = datetime.now().year
        participant_model = ParticipantModel(db_session, current_year, TEST_CIRCLE_SLUG)
        participant_id = participant_model.add_participant({
            'first_name': 'Digest', 'last_name': 'TestParticipant',
            'email': 'digest-test-participant@example.com',
            'preferred_area': 'UNASSIGNED', 'skill_level': 'Intermediate',
            'experience': '1-2 counts', 'participation_type': 'regular',
        })
        circle_admin_model = CircleAdminModel(db_session)
        circle_admin_email = 'digest-recipient-test@example.com'
        circle_admin_model.add_admin(circle_admin_email, TEST_CIRCLE_SLUG)

        captured = {}

        def fake_send_email(recipients, subject, text_content, html_content=None, **kwargs):
            captured['recipients'] = recipients
            return True

        try:
            with patch('services.email_service.email_service.send_email', side_effect=fake_send_email):
                results = generate_admin_digest_email(app_module.app, TEST_CIRCLE_SLUG)

            assert results['emails_sent'] == 1
            assert circle_admin_email in captured['recipients']
            for admin_email in ADMIN_EMAILS:
                assert admin_email in captured['recipients']
        finally:
            circle_admin_model.remove_admin(circle_admin_email, TEST_CIRCLE_SLUG)
            db_session.query(Participant).filter_by(id=participant_id).delete()
            db_session.commit()
