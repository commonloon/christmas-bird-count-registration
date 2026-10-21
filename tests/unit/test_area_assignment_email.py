# Updated by Claude AI on 2026-10-21
"""
Tests for the optional "notify this person" email sent when an admin assigns a
participant from the unassigned list or reassigns one between areas
(area_assignment / area_reassignment email types, GitHub issue #19).
"""

from datetime import datetime

import pytest

from config.database import get_db_session
from models.participant import ParticipantModel
from services.email_service import email_service
from tests.test_config import TEST_CIRCLE_SLUG

YEAR = datetime.now().year
LEADER_EMAIL = 'area-assign-leader@example.com'
LEADER_PHONE = '555-0142'


def _participant(first_name, area, **extra):
    return {
        'first_name': first_name,
        'last_name': 'AssignEmailTest',
        'email': f'{first_name.lower()}-assign-email-test@example.com',
        'phone': '555-0100',
        'preferred_area': area,
        'status': 'active',
        'skill_level': 'Beginner',
        'experience': 'None',
        **extra,
    }


@pytest.fixture
def seeded():
    """An unassigned participant, an assigned one, and a leader of area A (with
    contact details that must never appear in the email)."""
    model = ParticipantModel(get_db_session(), YEAR, TEST_CIRCLE_SLUG)
    ids = {
        'unassigned': model.add_participant(_participant('Una', 'UNASSIGNED')),
        'assigned': model.add_participant(_participant('Asa', 'B')),
        'leader': model.add_participant(_participant(
            'Lee', 'A', is_leader=True, assigned_area_leader='A',
            email=LEADER_EMAIL, phone=LEADER_PHONE)),
    }
    yield ids
    for participant_id in ids.values():
        model.delete_participant(participant_id)


@pytest.fixture
def sent(monkeypatch):
    """Captures send_email calls instead of sending."""
    calls = []

    def fake_send_email(to_addresses, subject, body, *args, **kwargs):
        calls.append({'to': to_addresses, 'subject': subject, 'body': body})
        return True

    monkeypatch.setattr(email_service, 'send_email', fake_send_email)
    return calls


def _assign(client, participant_id, notify):
    data = {'participant_id': str(participant_id), 'area_code': 'A', 'year': YEAR}
    if notify:
        data['notify'] = '1'
    return client.post('/bigbird/assign_participant', data=data)


def _reassign(client, participant_id, notify, **extra):
    return client.post('/bigbird/edit_participant', json={
        'participant_id': str(participant_id),
        'first_name': 'Asa',
        'last_name': 'AssignEmailTest',
        'email': 'asa-assign-email-test@example.com',
        'preferred_area': 'A',
        'notify': notify,
        'year': YEAR,
        **extra,
    })


def test_assign_with_notify_emails_participant_area_and_leader(super_admin_client, seeded, sent):
    _assign(super_admin_client, seeded['unassigned'], notify=True)

    assert len(sent) == 1
    assert sent[0]['to'] == ['una-assign-email-test@example.com']
    assert 'Lee AssignEmailTest' in sent[0]['body']
    assert 'will be in touch' in sent[0]['body']
    assert 'moved from' not in sent[0]['body']


def test_assign_email_never_includes_leader_contact_details(super_admin_client, seeded, sent):
    _assign(super_admin_client, seeded['unassigned'], notify=True)

    assert LEADER_EMAIL not in sent[0]['body']
    assert LEADER_PHONE not in sent[0]['body']


def test_assign_without_notify_sends_nothing_but_still_assigns(super_admin_client, seeded, sent):
    _assign(super_admin_client, seeded['unassigned'], notify=False)

    assert sent == []
    model = ParticipantModel(get_db_session(), YEAR, TEST_CIRCLE_SLUG)
    assert model.get_participant(seeded['unassigned'])['preferred_area'] == 'A'


def test_reassign_with_notify_names_old_and_new_area(super_admin_client, seeded, sent):
    response = _reassign(super_admin_client, seeded['assigned'], notify=True)

    assert response.get_json()['success'] is True
    assert len(sent) == 1
    assert 'moved from' in sent[0]['body']
    assert 'Area B' in sent[0]['body'] and 'Area A' in sent[0]['body']
    assert LEADER_EMAIL not in sent[0]['body']


def test_reassign_without_notify_sends_nothing(super_admin_client, seeded, sent):
    _reassign(super_admin_client, seeded['assigned'], notify=False)

    assert sent == []


def test_edit_without_area_change_sends_nothing(super_admin_client, seeded, sent):
    _reassign(super_admin_client, seeded['assigned'], notify=True, preferred_area='B')

    assert sent == []


def test_send_failure_does_not_undo_assignment(super_admin_client, seeded, monkeypatch):
    monkeypatch.setattr(email_service, 'send_email', lambda *a, **k: False)

    _assign(super_admin_client, seeded['unassigned'], notify=True)

    model = ParticipantModel(get_db_session(), YEAR, TEST_CIRCLE_SLUG)
    assert model.get_participant(seeded['unassigned'])['preferred_area'] == 'A'


def test_format_leader_names():
    fmt = email_service._format_leader_names
    assert fmt([]) == ''
    assert fmt([{'first_name': 'Ann', 'last_name': 'Lee'}]) == 'Ann Lee'
    assert fmt([{'first_name': 'Ann', 'last_name': 'Lee'},
                {'first_name': 'Bo', 'last_name': 'Ng'}]) == 'Ann Lee and Bo Ng'
    assert fmt([{'first_name': 'A', 'last_name': 'X'}, {'first_name': 'B', 'last_name': 'Y'},
                {'first_name': 'C', 'last_name': 'Z'}]) == 'A X, B Y and C Z'


@pytest.mark.parametrize('email_type', ['area_assignment', 'area_reassignment'])
def test_preview_renders(admin_client, email_type):
    response = admin_client.get(
        f'/bigbird/circles/{TEST_CIRCLE_SLUG}/email-content/preview/{email_type}')

    assert response.status_code == 200
    assert 'Sample Leader' in response.get_data(as_text=True)
