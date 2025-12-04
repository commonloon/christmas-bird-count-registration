"""
Pytest fixtures for installation validation tests.
Updated by Claude AI on 2025-12-02
"""

import pytest
import json
import os
from datetime import datetime


@pytest.fixture(scope="session")
def installation_config():
    """
    Provide installation configuration loaded from config files.

    This fixture dynamically loads all configuration without hardcoding,
    making tests portable across different bird count installations.
    """
    from config.areas import get_all_areas, AREA_CONFIG
    from config.organization import get_organization_variables
    from config.cloud import (
        TEST_BASE_URL, PRODUCTION_BASE_URL,
        TEST_DATABASE, PRODUCTION_DATABASE,
        GCP_PROJECT_ID, GCP_LOCATION,
        BASE_DOMAIN, TEST_SERVICE, PRODUCTION_SERVICE
    )
    from config.database import get_firestore_client
    from models.area_signup_type import AreaSignupTypeModel

    # Get public areas from model
    db, _ = get_firestore_client()
    area_signup_model = AreaSignupTypeModel(db)
    public_areas = area_signup_model.get_public_areas()

    return {
        # Area configuration
        'all_areas': get_all_areas(),
        'public_areas': public_areas,
        'area_config': AREA_CONFIG,

        # Organization configuration
        'org_vars': get_organization_variables(),

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
    Load area_boundaries.json for validation.

    Returns None if file doesn't exist (tests can handle this).
    """
    path = 'static/data/area_boundaries.json'
    if not os.path.exists(path):
        return None

    with open(path, 'r') as f:
        return json.load(f)


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
# - test_credentials (session-scoped):
#     Retrieves test account credentials from Secret Manager.
#     Automatically uses values from tests/test_config.py which now imports from config/*.py
#
# - authenticated_browser (session-scoped):
#     Creates browser with OAuth authentication performed once for entire test session.
#     Uses test_credentials fixture and admin_login_for_test() from tests/utils/auth_utils.py
#     Download directory: tests/tmp/downloads (configured in parent conftest chrome_options/firefox_options)
#
# Installation tests can use these fixtures directly - no need to redefine them here.
