"""
Pytest fixtures for installation validation tests.
Updated by Claude AI on 2025-12-02
Updated by Claude AI on 2026-09-08 (area data is DB-backed per circle now, not a static file)
"""

import pytest
from datetime import datetime


@pytest.fixture(scope="session")
def installation_config():
    """
    Provide installation configuration loaded from config files.

    This fixture dynamically loads all configuration without hardcoding,
    making tests portable across different bird count installations.
    """
    from config.areas import AREA_CONFIG
    from config.organization import get_organization_variables
    from config.cloud import (
        TEST_BASE_URL, PRODUCTION_BASE_URL,
        TEST_DATABASE, PRODUCTION_DATABASE,
        GCP_PROJECT_ID, GCP_LOCATION,
        BASE_DOMAIN, TEST_SERVICE, PRODUCTION_SERVICE
    )
    from config.database import get_db_session
    from models.area_signup_type import AreaSignupTypeModel
    from models.circle import CircleAreaModel
    from tests.test_config import TEST_CIRCLE_SLUG

    # config.areas.get_all_areas()/get_organization_variables() both raise when no
    # circle is resolved (this is a multi-circle platform with no default circle -
    # see config/areas.py's _get_circle_areas()/config/organization.py's
    # _circle_value()), which is correct in the real app but means this fixture,
    # which runs as plain pytest setup with no request in flight, must resolve
    # the test circle itself first. Areas are queried directly (no request needed);
    # org_vars needs a real resolved-circle request context, built the same way
    # test/email_generator.py's _push_circle_context() does for the scheduler.
    db = get_db_session()
    area_signup_model = AreaSignupTypeModel(db, circle_slug=TEST_CIRCLE_SLUG)
    public_areas = area_signup_model.get_public_areas()
    all_areas = [a['code'] for a in CircleAreaModel(db).get_areas_for_circle(TEST_CIRCLE_SLUG)]

    from app import app as flask_app
    with flask_app.test_request_context('/', headers={'Host': f'{TEST_CIRCLE_SLUG}.cbc.test'}):
        flask_app.preprocess_request()
        org_vars = get_organization_variables()

    return {
        # Area configuration
        'all_areas': all_areas,
        'public_areas': public_areas,
        'area_config': AREA_CONFIG,

        # Organization configuration
        'org_vars': org_vars,

        # Cloud configuration
        'test_url': TEST_BASE_URL,
        'prod_url': PRODUCTION_BASE_URL,
        'test_db': TEST_DATABASE,
        'prod_db': PRODUCTION_DATABASE,
        'gcp_project': GCP_PROJECT_ID,
        'gcp_location': GCP_LOCATION,
        'base_domain': BASE_DOMAIN,
        'test_service': TEST_SERVICE,
        'prod_service': PRODUCTION_SERVICE,

        # Runtime information
        'current_year': datetime.now().year
    }


@pytest.fixture(scope="session")
def area_boundaries_data():
    """
    The test circle's area boundaries + map config - replaces the old static
    static/data/area_boundaries.json file, which nothing in the real app has read
    since area boundaries moved into the DB-backed circle_areas table (see
    models/circle.py's CircleAreaModel.get_boundary_data(), also what /api/areas
    serves). Returns the same {'areas': [...], 'map_config': {...}} shape the old
    file had, for the dedicated test circle (see tests/test_config.py's
    TEST_CIRCLE_SLUG and .env.example's hosts-file setup).
    """
    from config.database import get_db_session
    from models.circle import CircleAreaModel
    from tests.test_config import TEST_CIRCLE_SLUG

    return CircleAreaModel(get_db_session()).get_boundary_data(TEST_CIRCLE_SLUG)


@pytest.fixture(scope="session")
def configured_areas(installation_config):
    """Shortcut fixture for getting all configured area codes."""
    return installation_config['all_areas']


@pytest.fixture(scope="session")
def public_areas(installation_config):
    """Shortcut fixture for getting public area codes."""
    return installation_config['public_areas']


@pytest.fixture(scope="session")
def org_config(installation_config):
    """Shortcut fixture for organization variables."""
    return installation_config['org_vars']


# Fixtures inherited from parent conftest.py (tests/conftest.py):
#
# - browser (function-scoped):
#     Creates browser instance with download directory configured at tests/tmp/downloads
#     Uses chrome_options/firefox_options from parent conftest
#
# - authenticated_browser (class-scoped):
#     Creates browser authenticated via a directly-injected signed session cookie
#     (see tests/utils/auth_utils.py's login_as_test_user()) - there is no
#     test_credentials fixture/Secret Manager lookup anymore, since this app's auth
#     is magic-link based with no password/OAuth credential to store.
#
# Installation tests can use these fixtures directly - no need to redefine them here.
