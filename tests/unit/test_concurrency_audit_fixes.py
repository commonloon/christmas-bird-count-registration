# Updated by Claude AI on 2026-09-09
"""
Tests for the fixes from this session's concurrency/transaction-safety audit:

1. Historical-year writes now rejected server-side (previously UI-only) -
   routes/admin.py's _reject_if_historical_year_form/_json.
2. delete_participant/withdraw_participant/reactivate_participant are now
   single atomic transactions (delete/status-change + log + leader
   deactivation), not several separately-committed steps.
3. Magic-link token redemption is now an atomic UPDATE...WHERE used_at IS
   NULL, closing a double-redemption race.

See SCHEDULER_ARCHITECTURE_PLAN.txt / the session's audit findings for the
full context - the rate limiter and digest-email-timestamp findings were
explicitly excluded from the audit and aren't covered here. The connection-
pool sizing change (models/db.py) is a config knob, not independently
testable at this level.
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from config.database import get_db_session
from models.db import MagicLinkToken, Participant
from models.participant import ParticipantModel
from models.removal_log import RemovalLogModel
from models.withdrawal_log import WithdrawalLogModel
from tests.test_config import TEST_CIRCLE_SLUG

CURRENT_YEAR = datetime.now().year
HISTORICAL_YEAR = CURRENT_YEAR - 1


@pytest.fixture
def db_session():
    return get_db_session()


@pytest.fixture
def test_participant(db_session):
    """A fresh, throwaway participant in TEST_CIRCLE_SLUG's current year."""
    model = ParticipantModel(db_session, CURRENT_YEAR, TEST_CIRCLE_SLUG)
    unique = secrets.token_hex(4)
    participant_id = model.add_participant({
        'first_name': 'ConcurrencyAudit', 'last_name': f'Test{unique}',
        'email': f'concurrency-audit-{unique}@example.com',
        'preferred_area': 'UNASSIGNED', 'skill_level': 'Intermediate',
        'experience': '1-2 counts', 'participation_type': 'regular',
    })
    yield participant_id
    db_session.query(Participant).filter_by(id=participant_id).delete()
    db_session.commit()


class TestHistoricalYearWriteProtection:
    """Previously these routes only hid/disabled controls in the UI - a
    crafted request with an arbitrary `year` could mutate historical data.
    Confirmed server-side now, not just in the template."""

    def test_delete_participant_rejects_historical_year(self, admin_client, db_session, test_participant):
        resp = admin_client.post(f'/bigbird/delete_participant/{test_participant}',
                                  data={'year': HISTORICAL_YEAR, 'reason': 'test'})
        assert resp.status_code == 302

        model = ParticipantModel(db_session, CURRENT_YEAR, TEST_CIRCLE_SLUG)
        assert model.get_participant(test_participant) is not None

    def test_withdraw_participant_rejects_historical_year(self, admin_client, db_session, test_participant):
        resp = admin_client.post(f'/bigbird/withdraw_participant/{test_participant}',
                                  data={'year': HISTORICAL_YEAR, 'reason': 'test'})
        assert resp.status_code == 302

        model = ParticipantModel(db_session, CURRENT_YEAR, TEST_CIRCLE_SLUG)
        assert model.get_participant(test_participant)['status'] == 'active'

    def test_edit_participant_json_rejects_historical_year(self, admin_client, db_session, test_participant):
        resp = admin_client.post('/bigbird/edit_participant', json={
            'participant_id': str(test_participant),
            'first_name': 'Changed', 'last_name': 'Name',
            'email': 'changed@example.com',
            'year': HISTORICAL_YEAR,
        })
        data = resp.get_json()
        assert data['success'] is False
        assert 'read-only' in data['message'].lower()

        model = ParticipantModel(db_session, CURRENT_YEAR, TEST_CIRCLE_SLUG)
        assert model.get_participant(test_participant)['first_name'] == 'ConcurrencyAudit'

    def test_current_year_write_still_allowed(self, admin_client, db_session, test_participant):
        """The guard must not be so broad it blocks legitimate current-year writes."""
        resp = admin_client.post(f'/bigbird/withdraw_participant/{test_participant}',
                                  data={'year': CURRENT_YEAR, 'reason': 'test'})
        assert resp.status_code == 302

        model = ParticipantModel(db_session, CURRENT_YEAR, TEST_CIRCLE_SLUG)
        assert model.get_participant(test_participant)['status'] == 'withdrawn'


class TestAtomicParticipantDeletion:
    """delete_participant now wraps delete + log_removal + leader
    deactivation in one transaction - any failure must roll back everything,
    not leave a deleted participant with no removal-log entry."""

    def test_successful_delete_creates_removal_log_entry(self, admin_client, db_session, test_participant):
        resp = admin_client.post(f'/bigbird/delete_participant/{test_participant}',
                                  data={'year': CURRENT_YEAR, 'reason': 'audit test'})
        assert resp.status_code == 302

        model = ParticipantModel(db_session, CURRENT_YEAR, TEST_CIRCLE_SLUG)
        assert model.get_participant(test_participant) is None

        removal_model = RemovalLogModel(db_session, CURRENT_YEAR, TEST_CIRCLE_SLUG)
        matching = [r for r in removal_model.get_all_removals()
                    if r['participant_name'].startswith('ConcurrencyAudit')]
        assert len(matching) >= 1
        assert matching[0]['reason'] == 'audit test'

    def test_failed_leader_deactivation_rolls_back_the_whole_delete(self, admin_client, db_session, test_participant):
        """Force a failure inside the leader-deactivation step and confirm
        the participant is NOT deleted and NO removal-log entry exists -
        proving the whole operation is atomic, not partially committed."""
        model = ParticipantModel(db_session, CURRENT_YEAR, TEST_CIRCLE_SLUG)
        model.assign_area_leadership(test_participant, 'A', 'test-setup')
        assert model.get_participant(test_participant)['is_leader'] is True

        with patch('models.participant.ParticipantModel.deactivate_leaders_by_identity',
                   side_effect=RuntimeError('simulated failure')):
            resp = admin_client.post(f'/bigbird/delete_participant/{test_participant}',
                                      data={'year': CURRENT_YEAR, 'reason': 'should not persist'})
            assert resp.status_code == 302

        # Participant must still exist - the delete_participant() call earlier
        # in the same transaction must have been rolled back too.
        fresh = ParticipantModel(db_session, CURRENT_YEAR, TEST_CIRCLE_SLUG)
        participant = fresh.get_participant(test_participant)
        assert participant is not None
        assert participant['is_leader'] is True

        removal_model = RemovalLogModel(db_session, CURRENT_YEAR, TEST_CIRCLE_SLUG)
        matching = [r for r in removal_model.get_all_removals() if r['reason'] == 'should not persist']
        assert matching == []


class TestMagicLinkSingleUse:
    """A plain read-then-write on used_at let two near-simultaneous
    redemptions of the same token both succeed. Now an atomic
    UPDATE...WHERE used_at IS NULL - only the first redemption can win."""

    @pytest.fixture
    def magic_link_token(self, db_session):
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode('utf-8')).hexdigest()
        row = MagicLinkToken(
            email='cbc-test-admin1@naturevancouver.ca',
            token_hash=token_hash,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(row)
        db_session.commit()
        yield raw_token
        db_session.query(MagicLinkToken).filter_by(token_hash=token_hash).delete()
        db_session.commit()

    def test_get_renders_confirmation_without_consuming_token(self, client, db_session, magic_link_token):
        """GET must not burn the token - an email-security scanner fetching
        the link server-side (see routes/auth.py's verify() docstring) should
        leave it usable for the real recipient's subsequent click."""
        resp = client.get(f'/auth/verify/{magic_link_token}')
        assert resp.status_code == 200
        assert b'verify-form' in resp.data

        token_hash = hashlib.sha256(magic_link_token.encode('utf-8')).hexdigest()
        record = db_session.query(MagicLinkToken).filter_by(token_hash=token_hash).first()
        assert record.used_at is None

    def test_first_redemption_succeeds(self, client, magic_link_token):
        resp = client.post(f'/auth/verify/{magic_link_token}')
        assert resp.status_code == 302
        assert '/auth/login' not in resp.headers['Location']

    def test_second_redemption_of_the_same_token_is_rejected(self, client, magic_link_token):
        first = client.post(f'/auth/verify/{magic_link_token}')
        assert first.status_code == 302
        assert '/auth/login' not in first.headers['Location']

        second = client.get(f'/auth/verify/{magic_link_token}', follow_redirects=True)
        assert b'already been used' in second.data
