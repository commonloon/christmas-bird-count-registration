# Updated by Claude AI on 2026-10-22
"""
Tests for the public registration form's bot defenses: signed form-load
timestamp, honeypot field, URL-bearing names, disposable email domains, and the
confirmation email not relaying attacker-controlled text.
"""

from datetime import datetime

import pytest

from config.database import get_db_session
from models.participant import ParticipantModel
from services import security
from services.email_service import email_service
from services.security import (
    check_form_token, is_disposable_email, make_form_token, name_looks_like_spam,
)
from tests.test_config import TEST_CIRCLE_SLUG

YEAR = datetime.now().year
GOOD_EMAIL = 'spam-defense-test@example.com'


def _form(app, **overrides):
    with app.test_request_context():
        token = make_form_token()
    data = {
        'form_token': token,
        'first_name': 'Sparrow',
        'last_name': 'SpamDefenseTest',
        'email': GOOD_EMAIL,
        'phone': '555-0100',
        'skill_level': 'Beginner',
        'experience': 'None',
        'preferred_area': 'UNASSIGNED',
        'participation_type': 'regular',
    }
    data.update(overrides)
    return data


def _registered():
    model = ParticipantModel(get_db_session(), YEAR, TEST_CIRCLE_SLUG)
    return [p for p in model.get_participants_by_email(GOOD_EMAIL)] + \
           [p for p in model.get_participants_by_email('bgg671lbkbz0p7mt7ywd@fextemp.com')]


@pytest.fixture(autouse=True)
def no_real_waiting(monkeypatch):
    """Tests submit instantly; the real minimum-fill-time check is tested directly below."""
    monkeypatch.setattr(security, 'MIN_FORM_FILL_SECONDS', 0)


@pytest.fixture(autouse=True)
def cleanup():
    yield
    model = ParticipantModel(get_db_session(), YEAR, TEST_CIRCLE_SLUG)
    for p in _registered():
        model.delete_participant(p['id'])


@pytest.fixture
def sent(monkeypatch):
    calls = []
    monkeypatch.setattr(email_service, 'send_email',
                        lambda to, subject, body, html=None, *a, **kw: calls.append((to, html)) or True)
    return calls


def test_name_looks_like_spam():
    assert name_looks_like_spam('a href=https://evil.example payment available')
    assert name_looks_like_spam('visit www.example.com')
    assert name_looks_like_spam('deposit at spam.com')
    assert name_looks_like_spam('x' * 51)
    # Observed spam: 'href' glued to a URL fragment, and a bare URL fragment
    assert name_looks_like_spam('a hrefhttpsliniivideougo-naphpsmmuz payment availablea hscbf lecz')
    assert name_looks_like_spam('deposit available Confirm your transaction httpsliniivideougo')
    for name in ("Jane", "O'Brien", "Mary-Ann", "José", "de la Cruz", "Smith Jr",
                 "Eshref", "Shref", "Beshref"):   # real names containing the substring 'href'
        assert not name_looks_like_spam(name)


def test_is_disposable_email():
    assert is_disposable_email('bgg671lbkbz0p7mt7ywd@fextemp.com')
    assert is_disposable_email('someone@sub.mailinator.com')
    assert not is_disposable_email('someone@gmail.com')
    assert not is_disposable_email('someone@notmailinator.com')
    assert not is_disposable_email('')


def test_form_token_rules(app):
    with app.test_request_context():
        assert check_form_token('') == 'missing'
        assert check_form_token('forged') == 'missing'
        token = make_form_token()
        assert check_form_token(token) is None


def test_form_token_too_fast(app, monkeypatch):
    monkeypatch.setattr(security, 'MIN_FORM_FILL_SECONDS', 60)
    with app.test_request_context():
        assert check_form_token(make_form_token()) == 'too_fast'


def test_form_token_expired(app, monkeypatch):
    monkeypatch.setattr(security, 'MAX_FORM_AGE_SECONDS', -1)
    with app.test_request_context():
        assert check_form_token(make_form_token()) == 'expired'


def test_valid_registration_succeeds_and_emails(app, client, sent):
    response = client.post('/register', data=_form(app))
    assert response.status_code == 302 and '/success' in response.headers['Location']
    assert len(_registered()) == 1
    assert len(sent) == 1


def test_missing_form_token_rejected(app, client, sent):
    data = _form(app)
    del data['form_token']
    client.post('/register', data=data)
    assert _registered() == [] and sent == []


def test_filled_honeypot_rejected(app, client, sent):
    client.post('/register', data=_form(app, fax_number='555-1234'))
    assert _registered() == [] and sent == []


def test_url_in_name_rejected(app, client, sent):
    client.post('/register', data=_form(
        app, first_name='a href https://liniivideorugo-naphpsmmuz.example payment available'))
    assert _registered() == [] and sent == []


def test_disposable_email_rejected(app, client, sent):
    client.post('/register', data=_form(app, email='bgg671lbkbz0p7mt7ywd@fextemp.com'))
    assert _registered() == [] and sent == []


def test_confirmation_email_does_not_echo_notes(app, client, sent):
    client.post('/register', data=_form(app, notes_to_organizers='SPAMNOTE-MARKER please click'))
    assert len(sent) == 1
    assert 'SPAMNOTE-MARKER' not in sent[0][1]


def test_confirmation_email_backstop_blanks_spam_name_and_skips_disposable(app, client, sent):
    with client:
        client.get('/')  # establishes g.circle for the test circle
        participant = {'first_name': 'click https://evil.example', 'last_name': 'x' * 60,
                       'email': GOOD_EMAIL, 'participation_type': 'regular'}
        email_service.send_registration_confirmation(participant, 'UNASSIGNED')
        assert len(sent) == 1
        assert 'evil.example' not in sent[0][1]
        assert 'Participant' in sent[0][1]

        assert email_service.send_registration_confirmation(
            dict(participant, email='bgg671lbkbz0p7mt7ywd@fextemp.com'), 'UNASSIGNED') is False
        assert len(sent) == 1


class TestRejectionsAreRecordedForAlerts:
    """Each bot rejection feeds services/bot_attempts.py (history + super-admin alerts)."""

    @pytest.fixture(autouse=True)
    def clean_bot_tables(self):
        from sqlalchemy import text
        from models.db import get_engine

        def wipe():
            with get_engine().begin() as conn:
                for table in ('bot_attempt_hourly', 'bot_attempt_daily', 'bot_attempt_sample'):
                    conn.execute(text(f'DELETE FROM {table}'))
        wipe()
        yield
        wipe()

    @staticmethod
    def _reasons():
        from sqlalchemy import text
        from models.db import get_engine
        with get_engine().connect() as conn:
            return sorted(r[0] for r in conn.execute(text(
                "SELECT value FROM bot_attempt_daily WHERE dimension = 'reason'")))

    def test_each_rejection_type_is_recorded(self, app, client, sent):
        client.post('/register', data=_form(app, fax_number='x'))
        client.post('/register', data=_form(app, first_name='see https://evil.example now'))
        client.post('/register', data=_form(app, email='bgg671lbkbz0p7mt7ywd@fextemp.com'))
        data = _form(app)
        del data['form_token']
        client.post('/register', data=data)
        assert self._reasons() == ['disposable_email', 'honeypot', 'missing', 'spam_name']

    def test_clean_registration_and_stale_form_are_not_recorded(self, app, client, sent, monkeypatch):
        client.post('/register', data=_form(app))
        monkeypatch.setattr(security, 'MAX_FORM_AGE_SECONDS', -1)
        client.post('/register', data=_form(app))
        assert self._reasons() == []
