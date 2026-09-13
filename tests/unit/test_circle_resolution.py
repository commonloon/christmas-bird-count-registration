# Updated by Claude AI on 2026-09-09
"""
Tests for app.py's resolve_circle() - the Host-header-based multi-circle
routing this whole platform depends on. This is a multi-circle platform with
NO default/fallback circle: an unresolvable host must fail loudly (400), not
silently serve any one circle's data. See PROMPT.md's "Plan: Multi-Circle
Test Coverage" for the full rationale - this file covers items 1-2 of that
plan (resolution itself); tests/unit/test_multi_circle_isolation.py covers
items 3+ (data isolation once two circles are both resolvable).
"""

# Every test in this file passes an explicit Host header per request - that's
# the whole point (resolve_circle() reads request.host, not SERVER_NAME) - so
# the local app/client fixtures below override tests/unit/conftest.py's
# shared ones (same names, per that module's own documented override
# mechanism). The shared fixtures' SERVER_NAME='test.cbc.test' is NOT just
# irrelevant here - it's actively wrong: Flask always compares every
# request's Host against that fixed value regardless of what a given request
# actually sends, and a mismatch makes Werkzeug fail to match ANY route at
# all (see conftest.py's app_any_host docstring for the full mechanism),
# which is exactly what every test below other than the
# 'test.cbc.test'/'test.test' ones would hit. This reimplements the same
# "clear SERVER_NAME" fix as app_any_host/client_any_host directly, rather
# than depending on those fixtures, since depending on a conftest fixture
# that itself takes a parameter named `app` from a module that also defines
# a local `app` fixture creates a self-referential cycle (both resolve to
# this module's override).
import pytest


@pytest.fixture
def app():
    import app as app_module
    flask_app = app_module.app
    flask_app.config['TESTING'] = True
    flask_app.config['WTF_CSRF_ENABLED'] = False
    original = flask_app.config['SERVER_NAME']
    flask_app.config['SERVER_NAME'] = None
    yield flask_app
    flask_app.config['SERVER_NAME'] = original


@pytest.fixture
def client(app):
    return app.test_client()


def _get(client, host, path='/'):
    return client.get(path, headers={'Host': host})


class TestUnresolvableHost:
    """The single most important case: no default/fallback circle. A host
    matching no known pattern must hard-fail, never silently serve any one
    circle's data - this is the real production-safety property the
    no-default-circle migration work depends on."""

    def test_raw_ip_returns_400(self, client):
        assert _get(client, '203.0.113.5').status_code == 400

    def test_bare_hostname_returns_400(self, client):
        assert _get(client, 'localhost').status_code == 400

    def test_typo_domain_returns_400(self, client):
        # A host that doesn't match ANY of CIRCLE_SUBDOMAIN_PATTERNS at all
        # (wrong TLD shape) - distinct from a misspelled-but-pattern-shaped
        # subdomain like "vancover.cbc.birdcount.ca", which correctly 404s
        # instead (see TestUnknownCircleSubdomain) since it DOES match the
        # pattern, just names no real circle.
        assert _get(client, 'vancouver.cbc.wrongdomain.example').status_code == 400

    def test_unresolvable_host_response_does_not_leak_any_circle_data(self, client):
        """Not just the status code - confirm the 400 body doesn't happen to
        render any real circle's registration form (would indicate a partial
        fallback rather than a clean abort)."""
        resp = _get(client, '203.0.113.5')
        assert resp.status_code == 400
        assert b'Register' not in resp.data


class TestUnknownCircleSubdomain:
    """A host that matches a known PATTERN but has no corresponding circles
    row - distinct from "no pattern matched at all" (400 above)."""

    def test_unknown_circle_slug_returns_404(self, client):
        assert _get(client, 'nosuchcircle.cbc.test').status_code == 404

    def test_unknown_circle_slug_non_cbc_level_returns_404(self, client):
        assert _get(client, 'nosuchcircle.test').status_code == 404


class TestLandingHosts:
    """cbc.birdcount.ca (CBC circle listing) and birdcount.ca (bare apex,
    non-CBC listing) are deliberately not circle subdomains - no circle
    context, but also not a 404/400, since they're real pages (see
    routes/main.py's index())."""

    def test_landing_host_resolves_with_no_circle(self, client):
        resp = _get(client, 'cbc.birdcount.ca')
        assert resp.status_code == 200

    def test_apex_landing_host_resolves_with_no_circle(self, client):
        resp = _get(client, 'birdcount.ca')
        assert resp.status_code == 200

    def test_landing_host_sets_g_state_correctly(self, app, client):
        """Directly inspect g.circle_slug/is_landing_host/is_apex_landing_host,
        not just the HTTP status - the plan specifically calls these three
        out since other code (config/organization.py's _circle_value(),
        routes/admin.py's CIRCLE_CONSOLE_ENDPOINTS redirect) branches on them."""
        from flask import g
        with app.test_request_context('/', headers={'Host': 'cbc.birdcount.ca'}):
            app.preprocess_request()
            assert g.circle_slug is None
            assert g.is_landing_host is True
            assert g.is_apex_landing_host is False

    def test_apex_landing_host_sets_g_state_correctly(self, app):
        from flask import g
        with app.test_request_context('/', headers={'Host': 'birdcount.ca'}):
            app.preprocess_request()
            assert g.circle_slug is None
            assert g.is_landing_host is True
            assert g.is_apex_landing_host is True


def _super_admin_client_for_host(client, host):
    """A logged-in-as-super-admin session scoped to `host` specifically - the
    test client's cookiejar matches cookies against the request host used
    when the cookie was set, so session_transaction()'s own headers must
    match whatever host the real request will use (a documented gotcha from
    this session - see PROMPT.md's "Hard-won operational facts")."""
    with client.session_transaction(headers={'Host': host}) as sess:
        sess['user_email'] = 'cbc-test-admin1@naturevancouver.ca'
        sess['user_name'] = 'Test Super Admin'
    return client


class TestCircleConsoleEndpointsReachableFromLandingHost:
    """routes/admin.py's CIRCLE_CONSOLE_ENDPOINTS take their circle as an
    explicit URL <slug>, not from g.circle_slug - they must stay reachable
    from a non-circle host (the landing host, or any unresolvable host)
    without tripping resolve_circle()'s 400/404 path."""

    def test_list_circles_reachable_from_landing_host(self, client):
        host = 'cbc.birdcount.ca'
        client = _super_admin_client_for_host(client, host)
        resp = client.get('/bigbird/circles', headers={'Host': host})
        assert resp.status_code == 200

    def test_list_circles_reachable_from_unresolvable_host(self, client):
        """Even a host that would 400 for a normal route - CIRCLE_CONSOLE_ENDPOINTS
        are exempted from resolve_circle()'s pattern-match requirement entirely."""
        host = '203.0.113.5'
        client = _super_admin_client_for_host(client, host)
        resp = client.get('/bigbird/circles', headers={'Host': host})
        assert resp.status_code == 200

    def test_non_console_admin_route_still_400s_from_unresolvable_host(self, client):
        """The exemption is specific to CIRCLE_CONSOLE_ENDPOINTS, not a blanket
        pass for every authenticated admin route."""
        host = '203.0.113.5'
        client = _super_admin_client_for_host(client, host)
        resp = client.get('/bigbird/participants', headers={'Host': host})
        assert resp.status_code == 400


class TestSubdomainLevelsAndCaseInsensitivity:
    """Both CBC (<slug>.cbc.birdcount.ca / .cbc.test) and non-CBC
    (<slug>.birdcount.ca / .test) subdomain levels resolve the same slug -
    resolve_circle() itself doesn't gate on a circle's own is_cbc flag, only
    on which pattern matches and whether that slug exists in circles."""

    def test_cbc_level_test_domain_resolves(self, client):
        assert _get(client, 'test.cbc.test').status_code == 200

    def test_non_cbc_level_test_domain_resolves_the_same_circle(self, client):
        assert _get(client, 'test.test').status_code == 200

    def test_hostname_matching_is_case_insensitive(self, client):
        assert _get(client, 'TEST.CBC.TEST').status_code == 200
        assert _get(client, 'Test.Cbc.Test').status_code == 200

    def test_g_circle_slug_is_lowercased_regardless_of_host_case(self, app):
        from flask import g
        with app.test_request_context('/', headers={'Host': 'TEST.CBC.TEST'}):
            app.preprocess_request()
            assert g.circle_slug == 'test'
