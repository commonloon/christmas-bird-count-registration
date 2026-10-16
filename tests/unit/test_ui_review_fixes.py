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
from sqlalchemy import text

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

    def test_bootstrap_icons_used_for_export_button(self, super_admin_client):
        soup = BeautifulSoup(
            super_admin_client.get(LEADERS_URL).get_data(as_text=True), "html.parser")
        export = soup.select_one('a[href*="format=csv"]')
        assert export is not None
        assert export.select_one("i.bi.bi-download") is not None

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
            assert re.search(rf'{var}\s*:\s*(#[0-9a-fA-F]{{6}}|var\(--bs-\w+\))', css), var
        for selector in ('.withdrawn-header', '.withdrawn-title', '.withdrawn-row'):
            assert selector in css


# --- B5, B6, B10-B12: button, badge and table conventions ------------------

def _template_files():
    templates = os.path.join(PROJECT_ROOT, 'templates')
    for root, _dirs, files in os.walk(templates):
        if os.sep + 'emails' in root:
            continue
        for name in files:
            if name.endswith('.html'):
                yield os.path.join(root, name)


class TestButtonConventions:
    @pytest.mark.parametrize('url', [f'/bigbird/?year={YEAR}', f'/bigbird/participants?year={YEAR}'])
    def test_export_csv_is_outline_secondary_with_icon(self, super_admin_client, url):
        soup = BeautifulSoup(super_admin_client.get(url).get_data(as_text=True), 'html.parser')
        link = soup.select_one('a[href*="export_csv"], a[href*="export-csv"], a[href*="/export"]')
        assert link is not None, url
        assert 'btn-outline-secondary' in link['class']
        assert not {'btn-primary', 'btn-success'} & set(link['class'])
        assert link.select_one('i.bi.bi-download') is not None

    def test_leaders_and_leader_dashboard_export_buttons(self):
        leaders = _read('templates', 'admin', 'leaders.html')
        assert re.search(r"format='csv'\) \}\}\" class=\"btn btn-outline-secondary", leaders)
        leader = _read('templates', 'leader', 'dashboard.html')
        assert re.search(r'id="exportCsvBtn" class="btn btn-outline-secondary', leader)

    def test_dashboard_has_one_primary_quick_action(self, super_admin_client):
        soup = BeautifulSoup(
            super_admin_client.get(f'/bigbird/?year={YEAR}').get_data(as_text=True), 'html.parser')
        header = next(h for h in soup.select('.card-header h5') if h.get_text(strip=True) == 'Quick Actions')
        body = header.find_parent(class_='card').select_one('.card-body')
        assert {'d-flex', 'flex-wrap', 'gap-2'} <= set(body['class'])
        primaries = [a for a in body.select('a.btn') if 'btn-primary' in a['class']]
        assert len(primaries) == 1

    def test_participants_quick_actions_use_no_status_colours(self, super_admin_client):
        soup = BeautifulSoup(
            super_admin_client.get(f'/bigbird/participants?year={YEAR}').get_data(as_text=True),
            'html.parser')
        header = next(h for h in soup.select('.card-header h5') if h.get_text(strip=True) == 'Quick Actions')
        buttons = header.find_parent(class_='card').select('.card-body a.btn')
        assert len(buttons) == 3
        assert all('btn-outline-secondary' in b['class'] for b in buttons)

    def test_no_solid_info_buttons_outside_attention_cards(self):
        offenders = []
        for path in _template_files():
            text = open(path, encoding='utf-8').read()
            for match in re.finditer(r'class="[^"]*\bbtn-(?:outline-)?info\b[^"]*"', text):
                offenders.append((os.path.basename(path), match.group(0)))
        # The two solid btn-info buttons live inside bg-info/border-info cards on the dashboard
        assert [o for o in offenders if o[0] != 'dashboard.html'] == []


class TestBadgeConventions:
    def test_year_badge_is_neutral_everywhere(self):
        for path in _template_files():
            text = open(path, encoding='utf-8').read()
            assert not re.search(r'badge bg-info">\{\{ selected_year', text), path

    def test_skill_level_badge_is_not_colour_coded(self):
        for path in _template_files():
            text = open(path, encoding='utf-8').read()
            assert "badge bg-{% if participant.skill_level" not in text, path
        participants = _read('templates', 'admin', 'participants.html')
        assert "skillDisplay.className" not in participants

    def test_warning_and_info_badges_get_dark_text(self):
        css = _read('static', 'css', 'main.css')
        assert re.search(r'\.badge\.bg-warning,\s*\.badge\.bg-info\s*\{\s*color:\s*#000', css)


class TestTableConventions:
    def test_every_table_uses_the_standard_classes(self):
        checked = 0
        for path in _template_files():
            text = open(path, encoding='utf-8').read()
            for match in re.finditer(r'<table class="([^"]*)"', text):
                classes = match.group(1).split()
                if 'participant-table' in classes:
                    continue
                checked += 1
                assert {'table', 'table-striped', 'table-hover', 'align-middle'} <= set(classes), (path, classes)
                assert 'table-info' not in classes, path
        assert checked >= 20


# --- B7-B9, D24: shared page header, navbar, breadcrumbs, year tabs --------

ADMIN_PAGES = {
    'Dashboard': f'/bigbird/?year={YEAR}',
    'Participants': f'/bigbird/participants?year={YEAR}',
    'Unassigned': f'/bigbird/unassigned?year={YEAR}',
    'Leaders': f'/bigbird/leaders?year={YEAR}',
    'Registrations': f'/bigbird/recent-registrations?year={YEAR}',
    'Open/Close Areas': f'/bigbird/area-signup-type?year={YEAR}',
}
CIRCLE_PAGES = [
    f'/bigbird/circles/{TEST_CIRCLE_SLUG}/edit',
    f'/bigbird/circles/{TEST_CIRCLE_SLUG}/admins',
    f'/bigbird/circles/{TEST_CIRCLE_SLUG}/areas',
    f'/bigbird/circles/{TEST_CIRCLE_SLUG}/email-content',
    f'/bigbird/circles/{TEST_CIRCLE_SLUG}/email-schedule',
]
CONSOLE_PAGES = ['/bigbird/circles', '/bigbird/circles/new', '/bigbird/scheduler',
                 '/bigbird/email-content/defaults'] + CIRCLE_PAGES


def _soup(client, url):
    response = client.get(url)
    assert response.status_code == 200, url
    return BeautifulSoup(response.get_data(as_text=True), 'html.parser')


def _nav_labels(soup):
    return [a.get_text(strip=True) for a in soup.select('#mainNav .navbar-nav.me-auto a.nav-link')]


class TestNavbar:
    @pytest.mark.parametrize('label,url', list(ADMIN_PAGES.items()))
    def test_admin_nav_links_and_active_state(self, super_admin_client, label, url):
        soup = _soup(super_admin_client, url)
        assert _nav_labels(soup) == list(ADMIN_PAGES)
        active = [a.get_text(strip=True) for a in soup.select('#mainNav a.nav-link.active')]
        assert active == [label]

    def test_nav_links_carry_the_selected_year(self, super_admin_client):
        soup = _soup(super_admin_client, f'/bigbird/participants?year={YEAR}')
        hrefs = [a['href'] for a in soup.select('#mainNav .navbar-nav.me-auto a.nav-link')]
        assert all(f'year={YEAR}' in h for h in hrefs)

    def test_email_and_logout_live_in_the_navbar_only(self, super_admin_client):
        soup = _soup(super_admin_client, f'/bigbird/participants?year={YEAR}')
        logout = soup.select('a[href*="/auth/logout"]')
        assert len(logout) == 1
        assert logout[0].find_parent(class_='navbar') is not None
        assert 'cbc-test-admin1@naturevancouver.ca' in soup.select_one('.navbar-text').get_text()

    def test_collapsible_on_small_screens(self, super_admin_client):
        soup = _soup(super_admin_client, f'/bigbird/?year={YEAR}')
        toggler = soup.select_one('button.navbar-toggler')
        assert toggler['data-bs-target'] == '#mainNav'
        assert soup.select_one('#mainNav.navbar-collapse') is not None

    def test_circle_admin_gets_circle_menu(self, admin_client):
        soup = _soup(admin_client, f'/bigbird/?year={YEAR}')
        menu = soup.select_one('#mainNav .dropdown-menu')
        assert [a.get_text(strip=True) for a in menu.select('a')] == [
            'Circle Settings', 'Email Content', 'Email Schedule']

    def test_super_admin_has_no_circle_menu_on_circle_pages(self, super_admin_client):
        soup = _soup(super_admin_client, f'/bigbird/?year={YEAR}')
        assert soup.select_one('#mainNav .dropdown-menu') is None

    @pytest.mark.parametrize('url', CONSOLE_PAGES)
    def test_console_pages_get_console_nav(self, super_admin_client, url):
        soup = _soup(super_admin_client, url)
        assert _nav_labels(soup) == ['Circles', 'Scheduler', 'Email Defaults']
        assert soup.select_one('.navbar-brand').get_text(strip=True) == 'Count Super-Admin'
        assert soup.select_one('#mainNav a.nav-link.active') is not None

    def test_public_page_has_no_admin_nav_or_logout(self, client):
        soup = _soup(client, '/')
        assert _nav_labels(soup) == []
        assert soup.select_one('a[href*="/auth/logout"]') is None


class TestPageHeader:
    @pytest.mark.parametrize('url', list(ADMIN_PAGES.values()) + CONSOLE_PAGES)
    def test_header_has_no_user_chrome(self, super_admin_client, url):
        soup = _soup(super_admin_client, url)
        header = soup.select_one('main .page-header')
        assert header is not None, url
        assert header.select_one('h1') is not None
        assert header.select_one('a[href*="/auth/logout"]') is None

    @pytest.mark.parametrize('url', list(ADMIN_PAGES.values()))
    def test_year_scoped_pages_show_year_badge(self, super_admin_client, url):
        header = _soup(super_admin_client, url).select_one('main .page-header')
        assert header.select_one('.badge.bg-secondary').get_text(strip=True) == str(YEAR)


class TestBreadcrumbs:
    @pytest.mark.parametrize('url', list(ADMIN_PAGES.values())[1:] + ['/bigbird/blocked-ips'])
    def test_circle_admin_pages_lead_back_to_dashboard(self, super_admin_client, url):
        soup = _soup(super_admin_client, url)
        crumbs = soup.select('main nav[aria-label="breadcrumb"] li.breadcrumb-item')
        assert len(crumbs) >= 2, url
        assert crumbs[0].get_text(strip=True) == 'Dashboard'
        assert 'active' in crumbs[-1]['class']

    @pytest.mark.parametrize('url', CIRCLE_PAGES)
    def test_super_admin_circle_pages_trail_through_circles(self, super_admin_client, url):
        soup = _soup(super_admin_client, url)
        crumbs = [c.get_text(strip=True) for c in
                  soup.select('main nav[aria-label="breadcrumb"] li.breadcrumb-item')]
        assert crumbs[0] == 'Circles'
        assert len(crumbs) >= 2

    def test_circle_admin_trail_starts_at_dashboard(self, admin_client):
        soup = _soup(admin_client, f'/bigbird/circles/{TEST_CIRCLE_SLUG}/email-schedule')
        crumbs = [c.get_text(strip=True) for c in
                  soup.select('main nav[aria-label="breadcrumb"] li.breadcrumb-item')]
        assert crumbs == ['Dashboard', 'Email Schedule']

    def test_no_template_uses_a_back_button_instead(self):
        offenders = [os.path.basename(p) for p in _template_files()
                     if re.search(r'>\s*Back to (Circles|Circle Settings|Email Content)\s*<',
                                  open(p, encoding='utf-8').read())]
        assert offenders == []


class TestYearTabs:
    def test_no_template_has_a_year_dropdown(self):
        for path in _template_files():
            text = open(path, encoding='utf-8').read()
            assert '<select name="year"' not in text, path
            assert 'Year Selection' not in text, path

    @pytest.fixture
    def two_years(self, cleanup_participants):
        # cleanup_participants only clears the current year (and a fixed historical
        # one), so this prior-year row is removed explicitly, before and after.
        def remove():
            session = get_db_session()
            session.execute(text(
                'DELETE FROM participants WHERE circle_slug = :c AND year = :y AND email = :e'),
                {'c': TEST_CIRCLE_SLUG, 'y': YEAR - 1, 'e': 'past.yeartab@example.com'})
            session.commit()
        remove()
        previous = ParticipantModel(get_db_session(), YEAR - 1, TEST_CIRCLE_SLUG)
        previous.add_participant({
            'first_name': 'Past', 'last_name': 'YearTab', 'email': 'past.yeartab@example.com',
            'preferred_area': 'A', 'participation_type': 'regular',
        })
        yield
        remove()

    @pytest.mark.parametrize('path', ['/bigbird/', '/bigbird/participants', '/bigbird/leaders',
                                      '/bigbird/recent-registrations', '/bigbird/area/A'])
    def test_tabs_render_with_historical_marker(self, super_admin_client, two_years, path):
        soup = _soup(super_admin_client, f'{path}?year={YEAR}')
        tabs = soup.select('main ul.nav-tabs[aria-label="Select year"] a.nav-link')
        years = [t.get_text(strip=True) for t in tabs]
        assert str(YEAR) in years and str(YEAR - 1) in years, path
        current = [t for t in tabs if t.get_text(strip=True) == str(YEAR)][0]
        assert 'active' in current['class']
        previous = [t for t in tabs if t.get_text(strip=True) == str(YEAR - 1)][0]
        assert previous.select_one('i.bi-archive') is not None
        assert f'year={YEAR - 1}' in previous['href']

    def test_area_detail_year_tab_keeps_the_area(self, super_admin_client, two_years):
        soup = _soup(super_admin_client, f'/bigbird/area/A?year={YEAR}')
        previous = [t for t in soup.select('ul.nav-tabs a.nav-link')
                    if t.get_text(strip=True) == str(YEAR - 1)][0]
        assert '/area/A' in previous['href']
