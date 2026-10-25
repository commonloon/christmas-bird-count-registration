# Updated by Claude AI on 2026-10-04
"""
Tests that unassigned participants (active and withdrawn) appear on the admin
All Participants page in their own section ahead of the area sections, and
that they can be edited through the same admin.edit_participant endpoint as
participants assigned to an area.
"""

from datetime import datetime

import pytest

from config.database import get_db_session
from models.participant import ParticipantModel
from tests.test_config import TEST_CIRCLE_SLUG

YEAR = datetime.now().year
PARTICIPANTS_URL = f'/bigbird/participants?year={YEAR}'


def _participant(first_name, area, status='active'):
    return {
        'first_name': first_name,
        'last_name': 'UnassignedTest',
        'email': f'{first_name.lower()}-unassigned-test@example.com',
        'phone': '555-0100',
        'preferred_area': area,
        'status': status,
        'skill_level': 'Beginner',
        'experience': 'None',
    }


@pytest.fixture
def seeded():
    """One active unassigned, one withdrawn unassigned and one assigned
    participant in the 'test' circle's current year; removed afterward."""
    model = ParticipantModel(get_db_session(), YEAR, TEST_CIRCLE_SLUG)
    ids = {
        'active': model.add_participant(_participant('Ursula', 'UNASSIGNED')),
        'withdrawn': model.add_participant(_participant('Wendell', 'UNASSIGNED', status='withdrawn')),
        'assigned': model.add_participant(_participant('Aaron', 'A')),
    }
    yield ids
    for participant_id in ids.values():
        model.delete_participant(participant_id)


def test_unassigned_section_listed_before_areas(super_admin_client, seeded):
    html = super_admin_client.get(PARTICIPANTS_URL).get_data(as_text=True)

    assert 'id="area-UNASSIGNED"' in html
    assert 'Ursula' in html
    assert 'Wendell' in html
    assert html.index('id="area-UNASSIGNED"') < html.index('id="area-A"')
    # Jump-to chip for the unassigned section comes first too
    assert html.index('href="#area-UNASSIGNED"') < html.index('href="#area-A"')


def test_unassigned_participant_is_editable(super_admin_client, seeded):
    response = super_admin_client.post('/bigbird/edit_participant', json={
        'participant_id': str(seeded['active']),
        'first_name': 'Ursula',
        'last_name': 'UnassignedTest',
        'email': 'ursula-unassigned-test@example.com',
        'phone': '555-0199',
        'skill_level': 'Expert',
        'notes_to_organizers': 'Edited while unassigned',
        'year': YEAR,
    })
    assert response.get_json()['success'] is True

    model = ParticipantModel(get_db_session(), YEAR, TEST_CIRCLE_SLUG)
    updated = model.get_participant(seeded['active'])
    assert updated['phone'] == '555-0199'
    assert updated['skill_level'] == 'Expert'
    assert updated['notes_to_organizers'] == 'Edited while unassigned'
    assert updated['preferred_area'] == 'UNASSIGNED'


def _edit(client, participant_id, **extra):
    body = {
        'participant_id': str(participant_id),
        'first_name': 'Aaron',
        'last_name': 'UnassignedTest',
        'email': 'aaron-unassigned-test@example.com',
        'year': YEAR,
    }
    body.update(extra)
    return client.post('/bigbird/edit_participant', json=body).get_json()


def test_admin_can_change_feeder_to_field_and_back(super_admin_client, seeded):
    model = ParticipantModel(get_db_session(), YEAR, TEST_CIRCLE_SLUG)

    assert _edit(super_admin_client, seeded['assigned'], participation_type='FEEDER')['success'] is True
    assert model.get_participant(seeded['assigned'])['participation_type'] == 'FEEDER'

    assert _edit(super_admin_client, seeded['assigned'], participation_type='regular')['success'] is True
    assert model.get_participant(seeded['assigned'])['participation_type'] == 'regular'


def test_invalid_participation_type_rejected(super_admin_client, seeded):
    model = ParticipantModel(get_db_session(), YEAR, TEST_CIRCLE_SLUG)
    before = model.get_participant(seeded['assigned']).get('participation_type')

    result = _edit(super_admin_client, seeded['assigned'], participation_type='bogus')

    assert result['success'] is False
    assert model.get_participant(seeded['assigned']).get('participation_type') == before


def test_participation_type_untouched_when_not_sent(super_admin_client, seeded):
    model = ParticipantModel(get_db_session(), YEAR, TEST_CIRCLE_SLUG)
    _edit(super_admin_client, seeded['assigned'], participation_type='FEEDER')

    assert _edit(super_admin_client, seeded['assigned'], phone='555-0123')['success'] is True
    assert model.get_participant(seeded['assigned'])['participation_type'] == 'FEEDER'


def test_participants_page_has_participation_type_dropdown(super_admin_client, seeded):
    html = super_admin_client.get(PARTICIPANTS_URL).get_data(as_text=True)

    assert 'participation-type-input' in html
    assert '<option value="FEEDER"' in html
