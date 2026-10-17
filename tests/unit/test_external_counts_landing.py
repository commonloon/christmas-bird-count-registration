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


def _get_on(app, slug, path, method='GET'):
    return app.test_client().open(path, method=method, headers={'Host': f'{slug}.cbc.test'})


class TestExternalCircleRedirect:
    def test_public_pages_redirect_to_external_url(self, app_any_host, listed_circles):
        for path, method in (('/', 'GET'), ('/success', 'GET'), ('/area-leader-info', 'GET'),
                             ('/register', 'POST')):
            resp = _get_on(app_any_host, EXT_LINKED, path, method)
            assert resp.status_code == 302, path
            assert resp.headers['Location'] == 'https://reg.example/zz', path

    def test_leader_pages_redirect_too(self, app_any_host, listed_circles):
        resp = _get_on(app_any_host, EXT_LINKED, '/leader/')
        assert resp.status_code == 302

    def test_without_external_url_redirects_to_matching_landing_page(self, app_any_host, listed_circles):
        resp = _get_on(app_any_host, EXT_NO_URL, '/')
        assert resp.status_code == 302
        assert resp.headers['Location'].startswith('http://cbc.test')

    def test_unsafe_stored_url_is_not_followed(self, app_any_host, listed_circles):
        db = get_db_session()
        db.query(Circle).filter_by(slug=EXT_LINKED).update({'external_url': 'javascript:alert(1)'})
        db.commit()
        resp = _get_on(app_any_host, EXT_LINKED, '/')
        assert resp.status_code == 302
        assert 'javascript' not in resp.headers['Location']

    def test_admin_and_auth_stay_available(self, app_any_host, listed_circles):
        assert _get_on(app_any_host, EXT_LINKED, '/auth/login').status_code == 200
        # not redirected to the external site (an anonymous admin hit is sent to log in)
        resp = _get_on(app_any_host, EXT_LINKED, '/bigbird/')
        assert 'reg.example' not in resp.headers.get('Location', '')

    def test_internal_circle_is_not_redirected(self, app_any_host, listed_circles):
        resp = _get_on(app_any_host, INTERNAL, '/')
        assert resp.status_code == 200


class TestReportProblem:
    ADMIN = 'birdcount+report-problem@naturevancouver.ca'

    @pytest.fixture
    def sent(self, monkeypatch):
        import routes.main as main_module
        sent = []
        monkeypatch.setattr(main_module, 'get_admin_emails', lambda: [self.ADMIN])
        monkeypatch.setattr(main_module.email_service, 'send_email',
                            lambda to, subject, body, **kw: sent.append((to, subject, body)) or True)
        return sent

    def _post(self, app, host=LANDING_HOST, **form):
        return app.test_client().post('/report-problem', data=form, headers={'Host': host})

    def test_report_is_emailed_to_super_admins(self, app_any_host, listed_circles, sent):
        resp = self._post(app_any_host, circle_slug=EXT_LINKED,
                          message='The link is dead.', reporter_email='Someone@Example.org')
        assert resp.status_code == 200 and resp.get_json() == {'ok': True}
        (to, subject, body), = sent
        assert to == [self.ADMIN]
        assert 'Zz Linked External' in subject
        assert 'The link is dead.' in body and 'someone@example.org' in body

    def test_honeypot_sends_nothing_but_looks_successful(self, app_any_host, listed_circles, sent):
        resp = self._post(app_any_host, circle_slug=EXT_LINKED, message='buy pills', website='http://spam')
        assert resp.status_code == 200 and sent == []

    @pytest.mark.parametrize('form', [
        {'circle_slug': EXT_LINKED, 'message': ''},
        {'circle_slug': EXT_LINKED, 'message': 'abc'},
        {'circle_slug': 'no-such-circle', 'message': 'Something is wrong'},
    ])
    def test_invalid_reports_rejected(self, app_any_host, listed_circles, sent, form):
        assert self._post(app_any_host, **form).status_code == 400
        assert sent == []

    def test_only_available_on_landing_hosts(self, app_any_host, listed_circles, sent):
        resp = self._post(app_any_host, host=f'{INTERNAL}.cbc.test', circle_slug=INTERNAL,
                          message='Something is wrong')
        assert resp.status_code == 404 and sent == []

    def test_send_failure_is_reported(self, app_any_host, listed_circles, monkeypatch):
        import routes.main as main_module
        monkeypatch.setattr(main_module, 'get_admin_emails', lambda: [self.ADMIN])
        monkeypatch.setattr(main_module.email_service, 'send_email', lambda *a, **k: False)
        resp = self._post(app_any_host, circle_slug=EXT_LINKED, message='The link is dead.')
        assert resp.status_code == 500 and resp.get_json()['ok'] is False

    def test_landing_page_has_report_button_and_disclaimer(self, app_any_host, listed_circles):
        html = _landing(app_any_host)
        assert 'report-problem-btn' in html and 'data-slug="zz-ext-linked"' in html
        assert 'control or endorse those sites' in html


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
