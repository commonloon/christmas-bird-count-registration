# Pytest Configuration and Fixtures for CBC Registration Test Suite
# Updated by Claude AI on 2025-09-22

"""
Central pytest configuration and shared fixtures for the Christmas Bird Count
registration system test suite.
"""

import pytest
import os
import sys
import logging
from datetime import datetime
from google.cloud import firestore, secretmanager
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service as ChromeService

# Add project root to Python path for imports
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from tests.config import (
    TEST_CONFIG, TEST_ACCOUNTS, GCP_CONFIG,
    get_base_url, get_database_name, LOGGING_CONFIG
)

# Configure logging
logging.basicConfig(
    level=getattr(logging, LOGGING_CONFIG['level']),
    format=LOGGING_CONFIG['format']
)
logger = logging.getLogger(__name__)

# Pytest configuration
def pytest_configure(config):
    """Configure pytest with custom markers and options."""
    config.addinivalue_line(
        "markers", "critical: marks tests as critical functionality"
    )
    config.addinivalue_line(
        "markers", "admin: marks tests requiring admin authentication"
    )
    config.addinivalue_line(
        "markers", "slow: marks tests that take longer to run"
    )
    config.addinivalue_line(
        "markers", "security: marks security-related tests"
    )
    config.addinivalue_line(
        "markers", "identity: marks identity-based and family email tests"
    )

def pytest_collection_modifyitems(config, items):
    """Automatically mark tests based on their location/name."""
    for item in items:
        # Mark critical tests
        if any(keyword in item.nodeid for keyword in ['registration', 'auth', 'data_consistency', 'identity_synchronization']):
            item.add_marker(pytest.mark.critical)

        # Mark admin tests
        if 'admin' in item.nodeid or 'admin' in item.name:
            item.add_marker(pytest.mark.admin)

        # Mark slow tests
        if any(keyword in item.name for keyword in ['large', 'export', 'concurrent', 'performance']):
            item.add_marker(pytest.mark.slow)

        # Mark identity tests
        if any(keyword in item.nodeid for keyword in ['identity', 'family_email']):
            item.add_marker(pytest.mark.identity)

# Database Fixtures
@pytest.fixture(scope="session")
def firestore_client():
    """Create Firestore client for test session with correct database."""
    try:
        os.environ['GOOGLE_CLOUD_PROJECT'] = GCP_CONFIG['project_id']
        database_name = get_database_name()
        client = firestore.Client(database=database_name)
        logger.info(f"Connected to Firestore project: {GCP_CONFIG['project_id']}, database: {database_name}")
        return client
    except Exception as e:
        logger.error(f"Failed to connect to Firestore: {e}")
        pytest.fail(f"Cannot run tests without Firestore connection: {e}")

@pytest.fixture(scope="session")
def secret_manager_client():
    """Create Secret Manager client for retrieving test credentials."""
    try:
        client = secretmanager.SecretManagerServiceClient()
        logger.info("Connected to Secret Manager")
        return client
    except Exception as e:
        logger.error(f"Failed to connect to Secret Manager: {e}")
        pytest.fail(f"Cannot run tests without Secret Manager access: {e}")

@pytest.fixture
def test_credentials(secret_manager_client):
    """Retrieve test account credentials from Secret Manager."""
    credentials = {}

    for account_name, account_config in TEST_ACCOUNTS.items():
        try:
            secret_name = f"projects/{GCP_CONFIG['project_id']}/secrets/{account_config['secret_name']}/versions/latest"
            response = secret_manager_client.access_secret_version(request={"name": secret_name})
            password = response.payload.data.decode("UTF-8").strip()

            credentials[account_name] = {
                'email': account_config['email'],
                'password': password,
                'role': account_config['role']
            }
            logger.info(f"Retrieved credentials for {account_config['email']}")
        except Exception as e:
            logger.error(f"Failed to retrieve credentials for {account_name}: {e}")
            pytest.fail(f"Cannot run tests without credentials for {account_name}")

    return credentials

# Browser Fixtures
@pytest.fixture(scope="session")
def chrome_options():
    """Configure Chrome options for testing."""
    options = Options()

    if TEST_CONFIG['headless']:
        options.add_argument('--headless')

    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-extensions')
    options.add_argument(f'--window-size={TEST_CONFIG["window_size"][0]},{TEST_CONFIG["window_size"][1]}')

    # Additional stability options for cloud testing
    options.add_argument('--disable-web-security')
    options.add_argument('--allow-running-insecure-content')
    options.add_argument('--disable-features=VizDisplayCompositor')

    logger.info(f"Chrome configured with headless={TEST_CONFIG['headless']}")
    return options

@pytest.fixture
def browser(chrome_options):
    """Create and manage browser instance for tests."""
    driver = None
    try:
        driver = webdriver.Chrome(options=chrome_options)
        driver.implicitly_wait(10)
        driver.set_page_load_timeout(TEST_CONFIG['page_load_timeout'])
        logger.info("Browser instance created")
        yield driver
    except Exception as e:
        logger.error(f"Failed to create browser instance: {e}")
        pytest.fail(f"Cannot run browser tests: {e}")
    finally:
        if driver:
            try:
                driver.quit()
                logger.info("Browser instance closed")
            except Exception as e:
                logger.warning(f"Error closing browser: {e}")

# Database State Management Fixtures
@pytest.fixture
def clean_database(firestore_client):
    """Provide a clean database state for tests."""
    database_name = get_database_name()
    current_year = TEST_CONFIG['current_year']
    isolation_year = TEST_CONFIG['isolation_test_year']

    collections_to_clear = [
        f'participants_{current_year}',
        f'participants_{isolation_year}',
        f'removal_log_{current_year}',
        f'removal_log_{isolation_year}'
    ]

    # Note: area_leaders collections are preserved for migration utilities
    # Leadership data is now stored in participants collections with is_leader flag

    def clear_collections():
        """Clear specified collections."""
        for collection_name in collections_to_clear:
            try:
                collection_ref = firestore_client.collection(collection_name)
                docs = collection_ref.limit(500).stream()  # Batch delete for efficiency

                for doc in docs:
                    doc.reference.delete()

                logger.info(f"Cleared collection: {collection_name}")
            except Exception as e:
                logger.warning(f"Error clearing collection {collection_name}: {e}")

    # Clear before test
    clear_collections()
    logger.info("Database cleaned for test")

    yield firestore_client

    # Optionally clear after test (uncomment if needed)
    # clear_collections()
    # logger.info("Database cleaned after test")

@pytest.fixture
def populated_database(firestore_client, test_credentials):
    """Provide a database with realistic test data."""
    # This will be implemented when we create the dataset generation utilities
    logger.info("Populated database fixture (to be implemented)")
    yield firestore_client

@pytest.fixture
def identity_test_database(clean_database):
    """Provide a database with family email test scenarios pre-populated."""
    from tests.utils.identity_utils import create_identity_helper, STANDARD_FAMILY_SCENARIOS

    # Create identity helper
    identity_helper = create_identity_helper(clean_database, TEST_CONFIG['current_year'])

    # Create standard family scenarios
    created_families = []
    for scenario in STANDARD_FAMILY_SCENARIOS:
        family_data = identity_helper.create_family_scenario(
            scenario['email'],
            scenario['members']
        )
        created_families.append(family_data)
        logger.info(f"Created family scenario: {scenario['email']} with {len(scenario['members'])} members")

    # Store helper and families in fixture for test access
    clean_database.identity_helper = identity_helper
    clean_database.test_families = created_families

    logger.info(f"Identity test database ready with {len(created_families)} family scenarios")
    yield clean_database

    # Cleanup after test (optional - clean_database fixture handles main cleanup)
    try:
        cleanup_count = identity_helper.cleanup_test_identities("test-scenarios.ca")
        if cleanup_count > 0:
            logger.info(f"Cleaned up {cleanup_count} identity test records")
    except Exception as e:
        logger.warning(f"Error during identity test cleanup: {e}")

@pytest.fixture
def single_identity_test(clean_database):
    """Provide a clean database with utilities for single identity testing."""
    from tests.utils.identity_utils import create_identity_helper

    # Create identity helper
    identity_helper = create_identity_helper(clean_database, TEST_CONFIG['current_year'])

    # Store helper in fixture for test access
    clean_database.identity_helper = identity_helper

    logger.info("Single identity test database ready")
    yield clean_database

    # Cleanup test identities created during the test
    try:
        cleanup_count = identity_helper.cleanup_test_identities("test-")
        if cleanup_count > 0:
            logger.info(f"Cleaned up {cleanup_count} single identity test records")
    except Exception as e:
        logger.warning(f"Error during single identity test cleanup: {e}")

# Application Configuration Fixtures
@pytest.fixture(scope="session")
def test_config():
    """Provide test configuration."""
    return TEST_CONFIG

@pytest.fixture(scope="session")
def base_url():
    """Provide base URL for the test environment."""
    url = get_base_url()
    logger.info(f"Using base URL: {url}")
    return url

# Utility Fixtures
@pytest.fixture
def retry_config():
    """Provide retry configuration for network operations."""
    return {
        'attempts': TEST_CONFIG['retry_attempts'],
        'delay_base': TEST_CONFIG['retry_delay_base'],
        'timeout': TEST_CONFIG['request_timeout']
    }

# Session-level setup and teardown
@pytest.fixture(scope="session", autouse=True)
def test_session_setup():
    """Setup and teardown for the entire test session."""
    logger.info("=" * 50)
    logger.info("CBC Registration Test Suite Starting")
    logger.info(f"Target URL: {get_base_url()}")
    logger.info(f"Database: {get_database_name()}")
    logger.info(f"Test Year: {TEST_CONFIG['current_year']}")
    logger.info(f"Isolation Year: {TEST_CONFIG['isolation_test_year']}")
    logger.info("=" * 50)

    yield

    logger.info("=" * 50)
    logger.info("CBC Registration Test Suite Complete")
    logger.info("=" * 50)

# Error handling for missing dependencies
def pytest_runtest_setup(item):
    """Check for test dependencies before running tests."""
    # Check if browser tests require Chrome
    if 'browser' in item.fixturenames:
        try:
            webdriver.Chrome()
        except Exception:
            pytest.skip("Chrome browser not available for testing")

    # Check for admin tests requiring credentials
    if item.get_closest_marker('admin') and 'test_credentials' not in item.fixturenames:
        pytest.skip("Admin tests require credentials fixture")