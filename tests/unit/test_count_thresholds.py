# Updated by Claude AI on 2026-10-20
"""
Per-circle map colour thresholds (migration 0015): the tier maths, the feeder-excluding
area counts, the /api/areas payload, the unassigned page's map and tier-coloured
buttons, and the circle form field.
"""

from datetime import datetime

import pytest

from config.database import get_db_session
from models.circle import CircleModel
from models.participant import ParticipantModel
from services.count_thresholds import (
    DEFAULT_HIGH_FROM, DEFAULT_MEDIUM_FROM, MAX_THRESHOLD,
    get_thresholds, parse_thresholds, tier_for_count,
)
from tests.test_config import TEST_CIRCLE_SLUG
from tests.unit.test_circle_admin_permissions import EDIT_URL, _full_form

YEAR = datetime.now().year


class TestTierMaths:
    def test_defaults_when_unset(self):
        assert get_thresholds(None) == (DEFAULT_MEDIUM_FROM, DEFAULT_HIGH_FROM) == (4, 8)
        assert get_thresholds({'map_medium_from': None, 'map_high_from': None}) == (4, 8)
        assert get_thresholds({'map_medium_from': 1}) == (4, 8)  # half-set falls back whole

    def test_circle_values_used(self):
        assert get_thresholds({'map_medium_from': 1, 'map_high_from': 3}) == (1, 3)

    @pytest.mark.parametrize('count,tier', [
        (0, 'low'), (3, 'low'), (4, 'med'), (7, 'med'), (8, 'high'), (50, 'high'),
    ])
    def test_default_ranges_never_overlap(self, count, tier):
        # 8 belongs to the highest tier only (the old legend showed 4-8 and 8+)
        assert tier_for_count(count, 4, 8) == tier

    def test_issue_23_example(self):
        # 0 people / 1-2 people / 3+ people
        assert [tier_for_count(n, 1, 3) for n in (0, 1, 2, 3, 9)] == ['low', 'med', 'med', 'high', 'high']


class TestParseThresholds:
    def test_blank_means_defaults(self):
        assert parse_thresholds('', '') == (None, None, None)
        assert parse_thresholds(None, ' ') == (None, None, None)

    def test_valid_pair(self):
        assert parse_thresholds('1', '3') == (1, 3, None)

    @pytest.mark.parametrize('medium,high', [
        ('1', ''), ('', '5'), ('abc', '5'), ('4.5', '8'), ('0', '5'), ('-1', '5'),
        ('5', '5'), ('6', '5'), ('1', str(MAX_THRESHOLD + 1)),
    ])
    def test_invalid_pairs_rejected(self, medium, high):
        assert parse_thresholds(medium, high)[2]


@pytest.fixture
def participants():
    """Active participants in 'test' circle area A: 2 regular, 1 leader, 1 feeder, plus
    a withdrawn regular - removed afterward. Yields the model and the counted total
    (regular + leader) so tests don't depend on other data in the area."""
    model = ParticipantModel(get_db_session(), YEAR, TEST_CIRCLE_SLUG)
    baseline = model.get_area_counts(include_feeders=False).get('A', 0)

    def make(first_name, **extra):
        return model.add_participant({
            'first_name': first_name, 'last_name': 'ThresholdTest',
            'email': f'{first_name.lower()}-threshold-test@example.com', 'phone': '555-0100',
            'preferred_area': 'A', 'status': 'active', 'skill_level': 'Beginner',
            'experience': 'None', **extra,
        })

    ids = [
        make('Rita'), make('Rob'),
        make('Lena', is_leader=True, assigned_area_leader='A'),
        make('Fern', participation_type='FEEDER'),
        make('Wes', status='withdrawn'),
    ]
    yield model, baseline
    for participant_id in ids:
        model.delete_participant(participant_id)


class TestAreaCounts:
    def test_feeders_excluded_leaders_kept_withdrawn_ignored(self, participants):
        model, baseline = participants
        # Rita + Rob + Lena (leader) counted; Fern (feeder) and Wes (withdrawn) not
        assert model.get_area_counts(include_feeders=False)['A'] == baseline + 3

    def test_feeders_included_by_default(self, participants):
        model, _ = participants
        # Differences are independent of any feeders already in area A: ours adds one
        assert model.get_area_counts()['A'] - model.get_area_counts(include_feeders=False)['A'] >= 1


class TestApiAreas:
    def test_payload_carries_thresholds_and_slug(self, client):
        data = client.get('/api/areas').get_json()
        assert data['circle_slug'] == TEST_CIRCLE_SLUG
        assert set(data['thresholds']) == {'medium_from', 'high_from'}


@pytest.fixture
def circle_thresholds():
    """Set the 'test' circle's thresholds for a test; restore the row afterward."""
    model = CircleModel(get_db_session())
    original = model.get_by_slug(TEST_CIRCLE_SLUG)

    def set_values(medium, high):
        model.update(TEST_CIRCLE_SLUG, {'map_medium_from': medium, 'map_high_from': high})

    yield set_values
    model.update(TEST_CIRCLE_SLUG, original)


class TestCircleValues:
    def test_api_reports_circle_values(self, client, circle_thresholds):
        circle_thresholds(1, 3)
        assert client.get('/api/areas').get_json()['thresholds'] == {'medium_from': 1, 'high_from': 3}

    def test_unset_circle_reports_defaults(self, client, circle_thresholds):
        circle_thresholds(None, None)
        assert client.get('/api/areas').get_json()['thresholds'] == {'medium_from': 4, 'high_from': 8}


class TestUnassignedPage:
    def test_map_container_and_scripts(self, super_admin_client, circle_thresholds):
        circle_thresholds(1, 3)
        html = super_admin_client.get(f'/bigbird/unassigned?year={YEAR}').get_data(as_text=True)
        assert 'id="unassigned-map"' in html
        assert 'id="capacity-legend"' in html  # key repeated beside the area buttons
        assert 'data-medium-from="1"' in html and 'data-high-from="3"' in html
        assert 'js/count-thresholds.js' in html and 'js/unassigned-map.js' in html

    def test_buttons_use_circle_tiers(self, super_admin_client, participants, circle_thresholds):
        # Area A has at least 3 counted participants: high when high starts at 3
        circle_thresholds(1, 3)
        html = super_admin_client.get(f'/bigbird/unassigned?year={YEAR}').get_data(as_text=True)
        assert 'btn-tier-high' in html
        circle_thresholds(1, 99)
        html = super_admin_client.get(f'/bigbird/unassigned?year={YEAR}').get_data(as_text=True)
        assert 'btn-tier-med' in html and 'btn-tier-high' not in html


class TestCircleFormField:
    def test_circle_admin_can_set_thresholds(self, admin_client, circle_thresholds):
        resp = admin_client.post(EDIT_URL, data=_full_form({'map_medium_from': '1', 'map_high_from': '3'}))
        assert resp.status_code == 302
        updated = CircleModel(get_db_session()).get_by_slug(TEST_CIRCLE_SLUG)
        assert (updated['map_medium_from'], updated['map_high_from']) == (1, 3)

    def test_blank_resets_to_defaults(self, admin_client, circle_thresholds):
        circle_thresholds(1, 3)
        resp = admin_client.post(EDIT_URL, data=_full_form({'map_medium_from': '', 'map_high_from': ''}))
        assert resp.status_code == 302
        updated = CircleModel(get_db_session()).get_by_slug(TEST_CIRCLE_SLUG)
        assert updated['map_medium_from'] is None and updated['map_high_from'] is None

    def test_invalid_values_rejected_and_not_saved(self, admin_client, circle_thresholds):
        circle_thresholds(None, None)
        resp = admin_client.post(EDIT_URL, data=_full_form({'map_medium_from': '5', 'map_high_from': '5'}))
        assert resp.status_code == 200
        assert 'Map colour thresholds' in resp.get_data(as_text=True)
        updated = CircleModel(get_db_session()).get_by_slug(TEST_CIRCLE_SLUG)
        assert updated['map_medium_from'] is None

    def test_form_renders_fields_without_none(self, admin_client, circle_thresholds):
        circle_thresholds(None, None)
        html = admin_client.get(EDIT_URL).get_data(as_text=True)
        assert 'name="map_medium_from"' in html and 'name="map_high_from"' in html
        assert 'value="None"' not in html
