# Updated by Claude AI on 2026-09-09
"""
Shared Flask test-client fixtures for tests/unit/ (Postgres-backed, no live
server/Selenium needed - see docs/TEST_SETUP.md). A local fixture of the same
name in an individual test file overrides these for that file, per normal
pytest scoping.
"""

import pytest

# Flask-Limiter's storage is in-memory (config/rate_limits.py's
# LIMITER_STORAGE_URL) and persists for the life of this pytest PROCESS, not
# per test file - every test_client() request shares one counter keyed by
# '127.0.0.1' (config/rate_limits.py's get_rate_limit_key()). Enough
# tests/unit/ files hitting admin routes in one run exhausts a route's
# per-minute budget partway through collection, 429ing whichever test happens
# to run later - not a bug in any individual test, just an artifact of real
# rate limiting sharing state across unrelated files. Disabled here, once,
# for the whole tests/unit/ tier, since nothing in it tests rate-limiting
# behavior itself (confirmed via grep before adding this).
#
# app.config['RATELIMIT_ENABLED'] = False does NOT work for this - Flask-
# Limiter reads that flag once, at Limiter.init_app(app) time (which already
# ran during `import app`, long before any fixture runs), not per-request -
# setting it afterward from a fixture is silently too late. The Limiter
# instance's own .enabled attribute IS checked per-request, so toggle that
# directly instead (confirmed empirically - the config-flag approach was
# tried first and measured to still 429).
from services.limiter import limiter
limiter.enabled = False


@pytest.fixture
def app():
    """The real Flask app in test mode, backed by the local Postgres dev
    database. SERVER_NAME is the dedicated test circle's *.test hostname so
    every test_client() request's Host header resolves to the 'test' circle
    via the app's normal Host-header-based resolve_circle() - there's no
    default circle to fall back on otherwise (see app.py's resolve_circle())."""
    import app as app_module
    flask_app = app_module.app
    flask_app.config['TESTING'] = True
    flask_app.config['WTF_CSRF_ENABLED'] = False
    flask_app.config['SERVER_NAME'] = 'test.cbc.test'
    return flask_app


@pytest.fixture
def client(app):
    """Test client with no session (anonymous/public)."""
    return app.test_client()


# Deliberately NOT one of config/admins.py's TEST_ADMIN_EMAILS/
# PRODUCTION_ADMIN_EMAILS - those are global super-admins, so a session
# claiming 'admin' for one of them gets silently promoted back to
# 'super_admin' on the very next request (app.py's before_request
# recomputes session['user_role'] from the email every request - it doesn't
# trust whatever a previous request, or a test fixture, put there).
CIRCLE_ADMIN_TEST_EMAIL = 'cbc-test-circle-admin@example.com'


@pytest.fixture
def circle_admin_row():
    """Insert a real circle_admins row for the 'test' circle so a session
    logged in as CIRCLE_ADMIN_TEST_EMAIL resolves to role 'admin' scoped to
    that circle only, via the actual get_user_role() lookup - not a
    hardcoded session value (see the note on CIRCLE_ADMIN_TEST_EMAIL above)."""
    from config.database import get_db_session
    from models.circle import CircleAdminModel
    from tests.test_config import TEST_CIRCLE_SLUG

    model = CircleAdminModel(get_db_session())
    model.add_admin(CIRCLE_ADMIN_TEST_EMAIL, TEST_CIRCLE_SLUG)
    yield
    model.remove_admin(CIRCLE_ADMIN_TEST_EMAIL, TEST_CIRCLE_SLUG)


@pytest.fixture
def admin_client(client, circle_admin_row):
    """Test client authenticated as a genuine circle-admin (role 'admin') for
    the 'test' circle only - real circle_admins-backed, not a hardcoded
    session role, since that gets recomputed from the email every request
    anyway (see CIRCLE_ADMIN_TEST_EMAIL above)."""
    with client.session_transaction() as sess:
        sess['user_email'] = CIRCLE_ADMIN_TEST_EMAIL
        sess['user_name'] = 'Test Circle Admin'
    return client


@pytest.fixture
def super_admin_client(client):
    """Test client authenticated as a super-admin (any circle) - one of
    config/admins.py's TEST_ADMIN_EMAILS, auto-active whenever
    config/admins.py's is_test_environment() is true."""
    with client.session_transaction() as sess:
        sess['user_email'] = 'cbc-test-admin1@naturevancouver.ca'
        sess['user_name'] = 'Test Super Admin'
    return client
