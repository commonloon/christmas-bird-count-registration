# Updated by Claude AI on 2026-10-16
"""
Landing-page behaviour for externally-managed counts (circles.is_external /
external_url, migration 0014): link target, no-link when external_url is empty,
the next-count-date column, and the managing-organization link. Also covers the
two helpers behind them: services/count_dates.py and security.sanitize_http_url().
"""

import json
import re
from datetime import date

import pytest

from config.database import get_db_session
from models.circle import CircleModel
from models.db import Circle, CircleEmailSchedule
from services.count_dates import next_count_date
from services.security import sanitize_http_url

LANDING_HOST = 'cbc.test'

EXT_LINKED = 'zz-ext-linked'
EXT_NO_URL = 'zz-ext-nourl'
INTERNAL = 'zz-int-dated'


class TestNextCountDate:
    TODAY = date(2026, 10, 16)

    def test_picks_earliest_upcoming(self):
        dates = {2026: '2026-12-20', 2027: '2027-12-18', 2025: '2025-12-20'}
        assert next_count_date(dates, 'America/Vancouver', self.TODAY) == ('Dec 20, 2026', False)

    def test_today_counts_as_upcoming(self):
        assert next_count_date({2026: '2026-10-16'}, 'America/Vancouver', self.TODAY) == ('Oct 16, 2026', False)

    def test_falls_back_to_most_recent_past(self):
        dates = {2024: '2024-12-14', 2025: '2025-12-20'}
        assert next_count_date(dates, 'America/Vancouver', self.TODAY) == ('Dec 20, 2025', True)

    def test_tba_when_empty_or_unusable(self):
        assert next_count_date({}, 'America/Vancouver', self.TODAY) == ('TBA', False)
        assert next_count_date(None, 'America/Vancouver', self.TODAY) == ('TBA', False)
        assert next_count_date({2026: 'not-a-date', 2027: None}, 'America/Vancouver', self.TODAY) == ('TBA', False)

    def test_day_not_zero_padded(self):
        assert next_count_date({2026: '2026-11-05'}, 'America/Vancouver', self.TODAY)[0] == 'Nov 5, 2026'


class TestSanitizeHttpUrl:
    @pytest.mark.parametrize('url', [
        'https://example.org/count', 'http://example.org', ' https://example.org/x?a=1&b=2 ',
    ])
    def test_accepts_http_and_https(self, url):
        assert sanitize_http_url(url) == url.strip()

    @pytest.mark.parametrize('url', [
        '', '   ', None, 123, 'javascript:alert(1)', 'data:text/html,hi', 'ftp://example.org',
        '//example.org', 'example.org', 'https://', 'https:///path',
        'https://exa mple.org', 'https://example.org/"onmouseover="x', 'https://example.org/<b>',
        'https://example.org/\nx', 'https://' + 'a' * 500 + '.org',
    ])
    def test_rejects_everything_else(self, url):
        assert sanitize_http_url(url) == ''


def _delete_test_circles(db):
    db.rollback()
    for slug in (EXT_LINKED, EXT_NO_URL, INTERNAL):
        # CircleModel.create() adds default email-schedule rows (FK to circles)
        db.query(CircleEmailSchedule).filter_by(circle_slug=slug).delete()
        db.query(Circle).filter_by(slug=slug).delete()
    db.commit()


@pytest.fixture
def listed_circles(app_any_host):
    """Two external CBC circles (one with a URL, one without) and one internal
    circle with a future date, all removed again afterwards."""
    db = get_db_session()
    _delete_test_circles(db)  # leftovers from an interrupted earlier run
    model = CircleModel(db)
    common = dict(is_cbc=True, display_timezone='America/Vancouver',
                  latitude=49.0, longitude=-123.0, yearly_count_dates={})
    model.create(dict(common, slug=EXT_LINKED, circle_name='Zz Linked External',
                      name='Zz Birds Org', website='https://org.example/',
                      is_external=True, external_url='https://reg.example/zz',
                      yearly_count_dates={'2099': '2099-12-20'}))
    model.create(dict(common, slug=EXT_NO_URL, circle_name='Zz Unlinked External',
                      name=None, is_external=True, external_url=None))
    model.create(dict(common, slug=INTERNAL, circle_name='Zz Internal',
                      name='Zz Internal Org', website='javascript:alert(1)',
                      yearly_count_dates={'2099': '2099-12-19'}))
    yield
    _delete_test_circles(db)


def _landing(app):
    resp = app.test_client().get('/', headers={'Host': LANDING_HOST})
    assert resp.status_code == 200
    return resp.get_data(as_text=True)


def _row(html, circle_name):
    start = html.index(circle_name)
    return html[html.rindex('<tr>', 0, start):html.index('</tr>', start)]


class TestLandingExternalCircles:
    def test_external_with_url_links_out_in_new_tab(self, app_any_host, listed_circles):
        row = _row(_landing(app_any_host), 'Zz Linked External')
        assert 'href="https://reg.example/zz"' in row
        assert 'target="_blank"' in row and 'rel="noopener noreferrer"' in row
        assert 'Dec 20, 2099' in row

    def test_external_without_url_has_no_link_and_no_org(self, app_any_host, listed_circles):
        row = _row(_landing(app_any_host), 'Zz Unlinked External')
        before_button = row[:row.index('show-contact-btn')]
        assert '<a ' not in before_button
        assert 'TBA' in row

    def test_external_json_payload_has_no_link_target(self, app_any_host, listed_circles):
        html = _landing(app_any_host)
        payload = {}
        for slug in (EXT_LINKED, EXT_NO_URL, INTERNAL):
            match = re.search(r'\{[^{}]*"slug":\s*"%s"[^{}]*\}' % slug, html)
            assert match, slug
            payload[slug] = json.loads(match.group(0))
        assert payload[EXT_NO_URL]['url'] is None
        assert payload[EXT_NO_URL]['is_external'] is True
        assert payload[EXT_LINKED]['url'] == 'https://reg.example/zz'
        assert payload[INTERNAL]['url'].endswith('zz-int-dated.cbc.test/')

    def test_internal_circle_links_to_its_own_host(self, app_any_host, listed_circles):
        row = _row(_landing(app_any_host), 'Zz Internal')
        assert 'zz-int-dated.cbc.test' in row
        assert 'target="_blank"' not in row.split('Zz Internal Org')[0]
        assert 'Dec 19, 2099' in row

    def test_organization_links_only_for_http_urls(self, app_any_host, listed_circles):
        html = _landing(app_any_host)
        assert 'href="https://org.example/"' in _row(html, 'Zz Linked External')
        assert 'javascript:' not in _row(html, 'Zz Internal')
