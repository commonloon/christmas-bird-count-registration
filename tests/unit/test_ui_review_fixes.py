# Created by Claude AI on 2026-10-13
"""
Regression tests for the four bug fixes from UX_REVIEW.md section A:

  A1  Leaders page used Font Awesome icons, but only Bootstrap Icons is loaded
  A2  warning/info flash messages rendered as green success alerts
  A3  .map-legend/.legend-item defined twice (main.css and an inline <style>
      in leaders.html)
  A4  hard-coded withdrawn-participant colours on the leader dashboard

Flask-test-client-based against the local Postgres 'test' circle, no live
server needed (see tests/unit/conftest.py).
"""

import os
import re
from datetime import datetime

import pytest
from bs4 import BeautifulSoup

from config.database import get_db_session
from models.participant import ParticipantModel
from tests.test_config import TEST_CIRCLE_SLUG
from tests.utils.database_utils import create_database_manager

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
YEAR = datetime.now().year
LEADERS_URL = f'/bigbird/leaders?year={YEAR}'
LEADER_EMAIL = 'ui.review.leader@example.com'


def _read(*parts):
    with open(os.path.join(PROJECT_ROOT, *parts), encoding='utf-8') as f:
        return f.read()


def _alert_classes(html):
    soup = BeautifulSoup(html, 'html.parser')
    return [
        next(c for c in alert['class'] if c.startswith('alert-') and c != 'alert-dismissible')
        for alert in soup.select('main .alert')
    ]


@pytest.fixture
def cleanup_participants():
    db_manager = create_database_manager(get_db_session())
    db_manager.clear_test_collections()
    yield
    db_manager.clear_test_collections()


# --- A1: icons -------------------------------------------------------------

class TestLeadersPageIcons:
    def test_no_font_awesome_classes(self, super_admin_client):
        html = super_admin_client.get(LEADERS_URL).get_data(as_text=True)
        assert re.search(r'class="[^"]*\bfa[srb]?\b', html) is None
        assert 'fa-' not in re.sub(r'<script.*?</script>', '', html, flags=re.S)

    def test_bootstrap_icons_used_for_nav_buttons(self, super_admin_client):
        soup = BeautifulSoup(
            super_admin_client.get(LEADERS_URL).get_data(as_text=True), 'html.parser')
        nav = soup.select_one('[aria-label="Admin navigation"]')
        assert nav is not None
        assert nav.select_one('i.bi.bi-people') is not None
        assert nav.select_one('i.bi.bi-bar-chart') is not None

    def test_no_template_references_font_awesome(self):
        templates = os.path.join(PROJECT_ROOT, 'templates')
        offenders = []
        for root, _dirs, files in os.walk(templates):
            for name in files:
                if name.endswith('.html'):
                    text = open(os.path.join(root, name), encoding='utf-8').read()
                    if re.search(r'class="[^"]*\bfa[srb]? fa-', text):
                        offenders.append(name)
        assert offenders == []


# --- A2: flash categories --------------------------------------------------

class TestFlashCategories:
    @pytest.mark.parametrize('category,expected', [
        ('error', 'alert-danger'),
        ('success', 'alert-success'),
        ('warning', 'alert-warning'),
        ('info', 'alert-info'),
        ('message', 'alert-info'),   # Flask's default category
    ])
    def test_category_maps_to_alert_class(self, super_admin_client, category, expected):
        with super_admin_client.session_transaction() as sess:
            sess['_flashes'] = [(category, f'{category} flash text')]
        html = super_admin_client.get(LEADERS_URL).get_data(as_text=True)

        assert f'{category} flash text' in html
        assert _alert_classes(html) == [expected]

    def test_main_css_styles_all_four_alert_borders(self):
        css = _read('static', 'css', 'main.css')
        for cls in ('alert-success', 'alert-danger', 'alert-warning', 'alert-info'):
            assert re.search(rf'\.{cls}\s*\{{[^}}]*border-left', css), cls


# --- A3: map legend --------------------------------------------------------

class TestMapLegendStyles:
    def test_leaders_template_has_no_inline_style_block(self):
        assert '<style' not in _read('templates', 'admin', 'leaders.html')

    @pytest.mark.parametrize('selector', ['.map-legend', '.legend-item'])
    def test_selector_defined_once_in_main_css(self, selector):
        css = _read('static', 'css', 'main.css')
        assert len(re.findall(rf'^{re.escape(selector)}\s*\{{', css, flags=re.M)) == 1

    def test_leaders_map_legend_uses_classes_not_inline_colours(self):
        js = _read('static', 'js', 'leaders-map.js')
        legend_fn = js[js.index('function updateLeadersMapLegend'):]
        assert 'legend-color needs-leader' in legend_fn
        assert 'legend-color has-leader' in legend_fn
        assert 'background-color: #' not in legend_fn

    def test_swatch_and_tooltip_classes_live_in_main_css(self):
        css = _read('static', 'css', 'main.css')
        for selector in ('.legend-color.needs-leader', '.legend-color.has-leader',
                         '.needs-leader-tooltip', '.has-leader-tooltip'):
            assert selector in css

    def test_main_css_is_linked_on_leaders_page(self, super_admin_client):
        html = super_admin_client.get(LEADERS_URL).get_data(as_text=True)
        assert 'css/main.css' in html


# --- A4: withdrawn colours -------------------------------------------------

class TestWithdrawnStyling:
    def test_leader_dashboard_has_no_hardcoded_withdrawn_colours(self, client, cleanup_participants):
        model = ParticipantModel(get_db_session(), YEAR, TEST_CIRCLE_SLUG)
        leader_id = model.add_participant({
            'first_name': 'Uma', 'last_name': 'UiReview', 'email': LEADER_EMAIL,
            'preferred_area': 'A', 'participation_type': 'regular', 'phone': '250-555-0000',
        })
        model.assign_area_leadership(leader_id, 'A', 'test-admin@example.com')
        model.add_participant({
            'first_name': 'Wanda', 'last_name': 'UiReview',
            'email': 'wanda.ui.review@example.com', 'preferred_area': 'A',
            'participation_type': 'regular', 'status': 'withdrawn',
        })
        with client.session_transaction() as sess:
            sess['user_email'] = LEADER_EMAIL
            sess['user_name'] = 'Uma UiReview'

        html = client.get('/leader').get_data(as_text=True)
        soup = BeautifulSoup(html, 'html.parser')

        assert 'Withdrawn Participants (1)' in html
        assert soup.select_one('.card-header.withdrawn-header') is not None
        assert soup.select_one('.withdrawn-title') is not None
        assert soup.select_one('tr.withdrawn-row') is not None
        for hex_colour in ('#fff3cd', '#856404', '#ffc107'):
            assert hex_colour not in html.lower()

    def test_withdrawn_classes_defined_with_variables(self):
        css = _read('static', 'css', 'main.css')
        for var in ('--withdrawn-bg', '--withdrawn-border', '--withdrawn-text'):
            assert re.search(rf'{var}\s*:\s*#[0-9a-fA-F]{{6}}', css), var
        for selector in ('.withdrawn-header', '.withdrawn-title', '.withdrawn-row'):
            assert selector in css
