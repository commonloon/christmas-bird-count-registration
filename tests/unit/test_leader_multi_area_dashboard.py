# Created by Claude AI on 2026-09-28
"""
Tests for the multi-area leader dashboard (routes/leader.py's dashboard()) -
a person leading more than one area in the same circle/year via a separate
participant record per area (same email, a distinguishing name - see
docs/LEADER_GUIDE.md's "Leading more than one area"). Flask-test-client-based,
no live server needed (see tests/unit/conftest.py).
"""

from datetime import datetime

import pytest
from bs4 import BeautifulSoup

from config.database import get_db_session
from models.circle import CircleAreaModel
from models.participant import ParticipantModel
from tests.test_config import TEST_CIRCLE_SLUG, TEST_CIRCLE_SLUG_2
from tests.utils.database_utils import create_database_manager

MULTI_AREA_EMAIL = 'multi.area.leader@example.com'
SINGLE_AREA_EMAIL = 'single.area.leader@example.com'
ADMIN_ACTOR = 'test-admin@example.com'


@pytest.fixture
def db_session():
    return get_db_session()


@pytest.fixture(autouse=True)
def cleanup_test_data(db_session):
    """Same convention as tests/test_leader_area_assignment_bug.py."""
    db_manager = create_database_manager(db_session)
    db_manager.clear_test_collections()
    yield
    db_manager.clear_test_collections()


@pytest.fixture
def participant_model(db_session):
    current_year = datetime.now().year
    return ParticipantModel(db_session, current_year, TEST_CIRCLE_SLUG)


def _leader_session(client, email):
    with client.session_transaction() as sess:
        sess['user_email'] = email
        sess['user_name'] = 'Test Leader'


def _make_leader(participant_model, first_name, last_name, email, area, phone='250-555-0000'):
    pid = participant_model.add_participant({
        'first_name': first_name, 'last_name': last_name, 'email': email,
        'preferred_area': area, 'participation_type': 'regular', 'phone': phone,
    })
    participant_model.assign_area_leadership(pid, area, ADMIN_ACTOR)
    return pid


def _make_member(participant_model, first_name, area, participation_type='regular'):
    return participant_model.add_participant({
        'first_name': first_name, 'last_name': 'TeamTest',
        'email': f'{first_name.lower()}@example.com',
        'preferred_area': area, 'participation_type': participation_type,
    })


@pytest.fixture
def two_area_leader(participant_model):
    """HarveyA Dueck leads Area A, Harvey Dueck leads Area B, same email -
    the documented two-record workaround. One team member seeded in each
    area so rosters aren't empty."""
    pid_a = _make_leader(participant_model, 'HarveyA', 'Dueck', MULTI_AREA_EMAIL, 'A', phone='250-555-0001')
    pid_b = _make_leader(participant_model, 'Harvey', 'Dueck', MULTI_AREA_EMAIL, 'B', phone='250-555-0002')
    _make_member(participant_model, 'Alice', 'A')
    _make_member(participant_model, 'Bob', 'B')
    return pid_a, pid_b


def _area_tabs(html):
    """Parse the area-tab pills (only rendered when leading >1 area)."""
    soup = BeautifulSoup(html, 'html.parser')
    pills = soup.select('ul.nav-pills a.nav-link')
    return [(a.get_text(strip=True), a.get('href', ''), 'active' in a.get('class', [])) for a in pills]


class TestSingleAreaRegression:
    """Leading exactly one area must behave exactly as before this change."""

    def test_no_area_tabs_rendered(self, client, participant_model):
        _make_leader(participant_model, 'Solo', 'Leader', SINGLE_AREA_EMAIL, 'A')
        _leader_session(client, SINGLE_AREA_EMAIL)
        resp = client.get('/leader')
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert 'Leader Dashboard - Area A' in html
        assert _area_tabs(html) == []

    def test_no_leader_record_redirects_away(self, client):
        _leader_session(client, 'nobody.leads.anything@example.com')
        resp = client.get('/leader')
        assert resp.status_code == 302
        assert '/leader' not in resp.headers.get('Location', '/leader')

    def test_leader_record_with_no_area_assigned_redirects_away(self, client, participant_model):
        pid = participant_model.add_participant({
            'first_name': 'Dangling', 'last_name': 'Leader', 'email': SINGLE_AREA_EMAIL,
            'preferred_area': 'UNASSIGNED', 'participation_type': 'regular',
        })
        participant_model.update_participant(pid, {'is_leader': True, 'assigned_area_leader': None})
        _leader_session(client, SINGLE_AREA_EMAIL)
        resp = client.get('/leader')
        assert resp.status_code == 302
        assert '/leader' not in resp.headers.get('Location', '/leader')

    def test_reassigning_same_record_does_not_stack_areas(self, client, participant_model):
        """Moving one participant's leadership to a different area (existing
        assign_area_leadership behavior) must not be confused with genuinely
        leading two areas - still exactly one tab-less area."""
        pid = _make_leader(participant_model, 'Solo', 'Leader', SINGLE_AREA_EMAIL, 'A')
        participant_model.assign_area_leadership(pid, 'C', ADMIN_ACTOR)
        _leader_session(client, SINGLE_AREA_EMAIL)
        html = client.get('/leader').get_data(as_text=True)
        assert 'Leader Dashboard - Area C' in html
        assert _area_tabs(html) == []


class TestMultiAreaCore:
    def test_default_area_is_alphabetically_first(self, client, two_area_leader):
        _leader_session(client, MULTI_AREA_EMAIL)
        html = client.get('/leader').get_data(as_text=True)
        assert 'Leader Dashboard - Area A' in html
        assert 'Alice' in html
        assert 'Bob' not in html

    def test_switching_to_second_area_shows_only_that_roster(self, client, two_area_leader):
        _leader_session(client, MULTI_AREA_EMAIL)
        html = client.get('/leader?area=B').get_data(as_text=True)
        assert 'Leader Dashboard - Area B' in html
        assert 'Bob' in html
        assert 'Alice' not in html

    def test_both_area_tabs_render(self, client, two_area_leader):
        _leader_session(client, MULTI_AREA_EMAIL)
        html = client.get('/leader').get_data(as_text=True)
        labels = [label for label, _, _ in _area_tabs(html)]
        assert any('Area A' in l for l in labels)
        assert any('Area B' in l for l in labels)

    def test_identity_card_matches_active_areas_own_record(self, client, two_area_leader):
        _leader_session(client, MULTI_AREA_EMAIL)
        html_a = client.get('/leader?area=A').get_data(as_text=True)
        html_b = client.get('/leader?area=B').get_data(as_text=True)

        assert 'HarveyA Dueck' in html_a
        assert 'HarveyA Dueck' not in html_b
        assert 'Harvey Dueck' in html_b
        assert '250-555-0001' in html_a
        assert '250-555-0002' in html_b

    def test_three_areas_all_tabs_render_sorted_by_code(self, client, participant_model):
        _make_leader(participant_model, 'Cara', 'Three', MULTI_AREA_EMAIL, 'C')
        _make_leader(participant_model, 'Bea', 'Three', MULTI_AREA_EMAIL, 'B')
        _make_leader(participant_model, 'Ann', 'Three', MULTI_AREA_EMAIL, 'A')
        _leader_session(client, MULTI_AREA_EMAIL)
        html = client.get('/leader').get_data(as_text=True)
        labels = [label for label, _, _ in _area_tabs(html)]
        assert len(labels) == 3
        assert [l[:8] for l in labels] == sorted(l[:8] for l in labels)
        assert labels[0].startswith('Area A')
        assert labels[2].startswith('Area C')

    def test_duplicate_records_for_the_same_area_collapse_to_one_tab(self, client, participant_model):
        """Two records under one email both assigned to Area A (bad data, not
        the intended workaround) must not produce a duplicate tab or crash."""
        _make_leader(participant_model, 'First', 'Copy', MULTI_AREA_EMAIL, 'A')
        _make_leader(participant_model, 'Second', 'Copy', MULTI_AREA_EMAIL, 'A')
        _leader_session(client, MULTI_AREA_EMAIL)
        resp = client.get('/leader')
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert html.count('Leader Dashboard - Area A') == 1
        assert _area_tabs(html) == []

    def test_unconfigured_area_code_falls_back_to_bare_name(self, client, participant_model):
        """An area code with no circle_areas row (get_area_info's fallback
        path) must still render, not crash."""
        _make_leader(participant_model, 'Ghost', 'Area', SINGLE_AREA_EMAIL, 'ZZ')
        _leader_session(client, SINGLE_AREA_EMAIL)
        resp = client.get('/leader')
        assert resp.status_code == 200
        assert 'Leader Dashboard - Area ZZ' in resp.get_data(as_text=True)


class TestSecurityIsolation:
    def test_requesting_an_area_not_led_falls_back_to_default(self, client, two_area_leader):
        """Area A/B belong to this email; Area C does not - must not leak."""
        _leader_session(client, MULTI_AREA_EMAIL)
        html = client.get('/leader?area=C').get_data(as_text=True)
        assert 'Leader Dashboard - Area A' in html

    def test_malicious_area_param_falls_back_safely_with_no_reflection(self, client, two_area_leader):
        _leader_session(client, MULTI_AREA_EMAIL)
        payload = '<script>alert(1)</script>'
        resp = client.get('/leader', query_string={'area': payload})
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert 'Leader Dashboard - Area A' in html
        assert payload not in html

    def test_empty_area_param_falls_back_to_default(self, client, two_area_leader):
        _leader_session(client, MULTI_AREA_EMAIL)
        html = client.get('/leader?area=').get_data(as_text=True)
        assert 'Leader Dashboard - Area A' in html

    def test_leader_record_in_a_different_circle_does_not_leak_in(self, client, db_session, participant_model):
        """A leader record under the same email but a DIFFERENT circle must
        never surface as an extra area tab on this circle's dashboard."""
        other_circle_model = ParticipantModel(db_session, datetime.now().year, TEST_CIRCLE_SLUG_2)
        other_mgr = create_database_manager(db_session, TEST_CIRCLE_SLUG_2)
        try:
            _make_leader(other_circle_model, 'Cross', 'Circle', MULTI_AREA_EMAIL, 'Z')
            _make_leader(participant_model, 'Solo', 'Leader', MULTI_AREA_EMAIL, 'A')

            _leader_session(client, MULTI_AREA_EMAIL)
            resp = client.get('/leader')
            assert resp.status_code == 200
            html = resp.get_data(as_text=True)
            assert 'Leader Dashboard - Area A' in html
            assert _area_tabs(html) == []
            assert 'Area Z' not in html
            assert 'Cross Circle' not in html
        finally:
            other_mgr.clear_test_collections()


class TestYearAreaInteraction:
    def test_area_tab_switch_preserves_selected_year(self, client, two_area_leader, db_session):
        historical = ParticipantModel(db_session, 2000, TEST_CIRCLE_SLUG)
        historical.add_participant({
            'first_name': 'OldTimer', 'last_name': 'Test', 'email': 'old@example.com',
            'preferred_area': 'A', 'participation_type': 'regular',
        })
        _leader_session(client, MULTI_AREA_EMAIL)
        html = client.get('/leader?area=A&year=2000').get_data(as_text=True)
        _, href_a, active_a = next((l, h, a) for l, h, a in _area_tabs(html) if l.startswith('Area A'))
        _, href_b, active_b = next((l, h, a) for l, h, a in _area_tabs(html) if l.startswith('Area B'))
        assert active_a and not active_b
        assert 'year=2000' in href_b, "switching to Area B should keep year=2000"

    def test_year_tab_switch_preserves_selected_area(self, client, two_area_leader, db_session):
        historical = ParticipantModel(db_session, 2000, TEST_CIRCLE_SLUG)
        historical.add_participant({
            'first_name': 'OldTimer', 'last_name': 'Test', 'email': 'old@example.com',
            'preferred_area': 'A', 'participation_type': 'regular',
        })
        _leader_session(client, MULTI_AREA_EMAIL)
        html = client.get('/leader?area=B').get_data(as_text=True)
        soup = BeautifulSoup(html, 'html.parser')
        year_links = soup.select('ul.nav-tabs a.nav-link')
        historical_link = next(a for a in year_links if '2000' in a.get_text())
        assert 'area=B' in historical_link.get('href', '')

    def test_led_areas_come_from_current_year_even_when_viewing_history(self, client, two_area_leader, db_session):
        """Area tabs reflect current-year leadership, not whatever that area
        had going on historically - Area B has zero 2000 data, but its tab
        (and an empty-roster page) must still be reachable while browsing 2000."""
        historical = ParticipantModel(db_session, 2000, TEST_CIRCLE_SLUG)
        historical.add_participant({
            'first_name': 'OldTimer', 'last_name': 'Test', 'email': 'old@example.com',
            'preferred_area': 'A', 'participation_type': 'regular',
        })
        _leader_session(client, MULTI_AREA_EMAIL)
        resp = client.get('/leader?area=B&year=2000')
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert 'Leader Dashboard - Area B' in html
        assert 'Historical Data (2000)' in html
        assert 'No participants registered for Area B yet' in html
        labels = [label for label, _, _ in _area_tabs(html)]
        assert any(l.startswith('Area A') for l in labels)
        assert any(l.startswith('Area B') for l in labels)


class TestRosterAndExportScoping:
    def test_withdrawn_participant_excluded_from_csv_script_but_shown_in_table(self, client, participant_model):
        _make_leader(participant_model, 'Solo', 'Leader', SINGLE_AREA_EMAIL, 'A')
        withdrawn_id = _make_member(participant_model, 'Wendy', 'A')
        participant_model.withdraw_participant(withdrawn_id)

        _leader_session(client, SINGLE_AREA_EMAIL)
        html = client.get('/leader').get_data(as_text=True)

        assert 'Wendy' in html  # shown in the withdrawn table
        assert 'WITHDRAWN' in html
        script_start = html.index('function exportTeamCsv')
        script_section = html[script_start:]
        assert 'Wendy' not in script_section, "withdrawn participants must not be in the CSV export data"

    def test_export_filename_and_data_scoped_to_active_area(self, client, two_area_leader):
        _leader_session(client, MULTI_AREA_EMAIL)
        html_a = client.get('/leader?area=A').get_data(as_text=True)
        html_b = client.get('/leader?area=B').get_data(as_text=True)

        assert 'cbc_area_A_participants_' in html_a
        assert 'cbc_area_B_participants_' in html_b

        script_a = html_a[html_a.index('function exportTeamCsv'):]
        script_b = html_b[html_b.index('function exportTeamCsv'):]
        assert 'Alice' in script_a and 'Bob' not in script_a
        assert 'Bob' in script_b and 'Alice' not in script_b


class TestPromotionDemotionLifecycle:
    def test_removing_one_areas_leadership_leaves_single_tab(self, client, participant_model, two_area_leader):
        _, pid_b = two_area_leader
        participant_model.remove_area_leadership(pid_b, ADMIN_ACTOR)
        _leader_session(client, MULTI_AREA_EMAIL)
        html = client.get('/leader').get_data(as_text=True)
        assert 'Leader Dashboard - Area A' in html
        assert _area_tabs(html) == []
        # can no longer reach Area B's roster at all
        html_attempt = client.get('/leader?area=B').get_data(as_text=True)
        assert 'Leader Dashboard - Area A' in html_attempt

    def test_deleting_one_areas_participant_record_leaves_single_tab(self, client, participant_model, two_area_leader):
        _, pid_b = two_area_leader
        participant_model.delete_participant(pid_b)
        _leader_session(client, MULTI_AREA_EMAIL)
        html = client.get('/leader').get_data(as_text=True)
        assert 'Leader Dashboard - Area A' in html
        assert _area_tabs(html) == []


class TestTemplateRenderingNits:
    def test_area_name_with_special_characters_is_escaped_in_tab_label(self, client, db_session, two_area_leader):
        area_model = CircleAreaModel(db_session)
        original = area_model.get_area(TEST_CIRCLE_SLUG, 'A')
        try:
            area_model.update_area(TEST_CIRCLE_SLUG, 'A', name="Stanley's <Park> & Beach")
            _leader_session(client, MULTI_AREA_EMAIL)
            html = client.get('/leader').get_data(as_text=True)
            assert "Stanley's <Park> & Beach" not in html, "raw HTML must not appear unescaped"
            assert '&lt;Park&gt;' in html
            assert '&amp;' in html
        finally:
            area_model.update_area(TEST_CIRCLE_SLUG, 'A', name=original['name'] if original else 'Area A')

    def test_active_class_on_correct_area_and_year_tab_simultaneously(self, client, two_area_leader, db_session):
        historical = ParticipantModel(db_session, 2000, TEST_CIRCLE_SLUG)
        historical.add_participant({
            'first_name': 'OldTimer', 'last_name': 'Test', 'email': 'old@example.com',
            'preferred_area': 'B', 'participation_type': 'regular',
        })
        _leader_session(client, MULTI_AREA_EMAIL)
        html = client.get('/leader?area=B&year=2000').get_data(as_text=True)
        soup = BeautifulSoup(html, 'html.parser')

        area_pills = soup.select('ul.nav-pills a.nav-link')
        active_area_labels = [a.get_text(strip=True) for a in area_pills if 'active' in a.get('class', [])]
        assert len(active_area_labels) == 1
        assert active_area_labels[0].startswith('Area B')

        year_tabs = soup.select('ul.nav-tabs a.nav-link')
        active_year_labels = [a.get_text(strip=True) for a in year_tabs if 'active' in a.get('class', [])]
        assert len(active_year_labels) == 1
        assert '2000' in active_year_labels[0]
