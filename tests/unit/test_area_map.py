# Updated by Claude AI on 2026-10-21
"""
Tests for the public /map page and the map links in the area assignment and
registration confirmation emails.
"""

from datetime import datetime

import pytest

from config.database import get_db_session
from models.participant import ParticipantModel
from services.email_service import email_service
from tests.test_config import TEST_CIRCLE_SLUG

YEAR = datetime.now().year
LEADER_EMAIL = 'map-leader@example.com'
LEADER_PHONE = '555-0177'


@pytest.fixture
def leader():
    model = ParticipantModel(get_db_session(), YEAR, TEST_CIRCLE_SLUG)
    participant_id = model.add_participant({
        'first_name': 'Mapley', 'last_name': 'Leader', 'email': LEADER_EMAIL,
        'phone': LEADER_PHONE, 'preferred_area': 'A', 'status': 'active',
        'skill_level': 'Expert', 'experience': '10+ counts',
        'is_leader': True, 'assigned_area_leader': 'A',
    })
    yield participant_id
    model.delete_participant(participant_id)


def test_map_page_is_public(client):
    response = client.get('/map?area=A')

    assert response.status_code == 200
    assert 'area-map.js' in response.get_data(as_text=True)


def test_api_areas_lists_leader_names_without_contact_details(client, leader):
    response = client.get('/api/areas')
    body = response.get_data(as_text=True)

    area_a = next(a for a in response.get_json()['areas'] if a['letter_code'] == 'A')
    assert area_a['leaders'] == ['Mapley Leader']
    assert LEADER_EMAIL not in body
    assert LEADER_PHONE not in body


def test_assignment_email_links_to_highlighted_area_map():
    org_vars = {'registration_url': 'https://vancouver.cbc.birdcount.ca'}
    assert email_service._area_map_url(org_vars, 'C') == 'https://vancouver.cbc.birdcount.ca/map?area=C'


@pytest.mark.parametrize('email_type', ['area_assignment', 'area_reassignment'])
def test_assignment_preview_includes_map_link(admin_client, email_type):
    html = admin_client.get(
        f'/bigbird/circles/{TEST_CIRCLE_SLUG}/email-content/preview/{email_type}').get_data(as_text=True)

    assert '/map?area=A' in html


def test_registration_confirmation_links_map_only_when_assigned(admin_client):
    base = f'/bigbird/circles/{TEST_CIRCLE_SLUG}/email-content/preview/registration_confirmation'

    assert '/map?area=A' in admin_client.get(base).get_data(as_text=True)
    assert '/map?area=' not in admin_client.get(base + '?variant=unassigned').get_data(as_text=True)
