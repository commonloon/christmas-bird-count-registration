# Updated by Claude AI on 2026-10-24
"""
The Manage Leaders page's Delete button posts {participant_id, year} to
admin.delete_leader. The endpoint once read only 'leader_id', so every click
failed with "Leader ID is required" (reported by parksville-qualicum, 2026-10-24).
"""

from datetime import datetime

import pytest

from config.database import get_db_session
from models.participant import ParticipantModel
from tests.test_config import TEST_CIRCLE_SLUG

YEAR = datetime.now().year
DELETE_URL = '/bigbird/delete_leader'


@pytest.fixture
def leader_id():
    """An active participant promoted to leader of area A; removed afterward."""
    model = ParticipantModel(get_db_session(), YEAR, TEST_CIRCLE_SLUG)
    participant_id = model.add_participant({
        'first_name': 'Leona',
        'last_name': 'DeleteLeaderTest',
        'email': 'leona-delete-leader-test@example.com',
        'phone': '555-0100',
        'preferred_area': 'A',
        'status': 'active',
        'skill_level': 'Beginner',
        'experience': 'None',
    })
    assert model.assign_area_leadership(participant_id, 'A', 'test@example.com')
    yield participant_id
    model.delete_participant(participant_id)


def _is_leader(participant_id):
    model = ParticipantModel(get_db_session(), YEAR, TEST_CIRCLE_SLUG)
    return bool(model.get_participant(participant_id).get('is_leader'))


def test_page_payload_removes_leadership_but_keeps_participant(super_admin_client, leader_id):
    """Exact payload sent by templates/admin/leaders.html's deleteLeader()."""
    response = super_admin_client.post(DELETE_URL, json={
        'participant_id': str(leader_id),
        'year': YEAR,
    })

    assert response.get_json()['success'] is True
    assert _is_leader(leader_id) is False
    model = ParticipantModel(get_db_session(), YEAR, TEST_CIRCLE_SLUG)
    assert model.get_participant(leader_id)['status'] == 'active'


def test_legacy_leader_id_key_still_accepted(super_admin_client, leader_id):
    response = super_admin_client.post(DELETE_URL, json={
        'leader_id': str(leader_id),
        'year': YEAR,
    })

    assert response.get_json()['success'] is True
    assert _is_leader(leader_id) is False


def test_missing_id_is_rejected(super_admin_client):
    response = super_admin_client.post(DELETE_URL, json={'year': YEAR})

    body = response.get_json()
    assert body['success'] is False
    assert body['message'] == 'Leader ID is required'
