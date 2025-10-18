"""
Pytest fixtures for installation validation tests.
Updated by Claude AI on 2025-10-18
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
    from config.areas import get_public_areas, get_all_areas, AREA_CONFIG
    from config.organization import get_organization_variables
    from config.cloud import (
        TEST_BASE_URL, PRODUCTION_BASE_URL,
        TEST_DATABASE, PRODUCTION_DATABASE,
        GCP_PROJECT_ID, GCP_LOCATION,
        BASE_DOMAIN, TEST_SERVICE, PRODUCTION_SERVICE
    )

    return {
        # Area configuration
        'all_areas': get_all_areas(),
        'public_areas': get_public_areas(),
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
