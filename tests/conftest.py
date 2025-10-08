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
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.firefox.service import Service as FirefoxService

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

@pytest.fixture(scope="session")
def test_credentials(secret_manager_client):
    """Retrieve test account credentials from Secret Manager.

    Session-scoped to avoid redundant credential retrieval across all tests.
    Credentials are static for the entire test suite run.
    """
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
    options = ChromeOptions()

    # Set download directory to temporary path under tests/
    test_dir = os.path.dirname(os.path.abspath(__file__))
    download_dir = os.path.join(test_dir, 'tmp', 'downloads')
    os.makedirs(download_dir, exist_ok=True)

    prefs = {
        "download.default_directory": download_dir,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": False
    }
    options.add_experimental_option("prefs", prefs)

    if TEST_CONFIG['headless']:
        options.add_argument('--headless')

    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-extensions')
    options.add_argument(f'--window-size={TEST_CONFIG["window_size"][0]},{TEST_CONFIG["window_size"][1]}')

    # Additional stability options for cloud testing and OAuth
    options.add_argument('--disable-web-security')
    options.add_argument('--allow-running-insecure-content')
    options.add_argument('--disable-features=VizDisplayCompositor')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--disable-background-networking')
    options.add_argument('--disable-background-timer-throttling')
    options.add_argument('--disable-renderer-backgrounding')
    options.add_argument('--disable-backgrounding-occluded-windows')
    options.add_argument('--disable-client-side-phishing-detection')
    options.add_argument('--disable-component-extensions-with-background-pages')
    options.add_argument('--disable-default-apps')
    options.add_argument('--disable-hang-monitor')
    options.add_argument('--disable-ipc-flooding-protection')
    options.add_argument('--disable-popup-blocking')
    options.add_argument('--disable-prompt-on-repost')
    options.add_argument('--disable-sync')
    options.add_argument('--metrics-recording-only')
    options.add_argument('--no-first-run')
    options.add_argument('--safebrowsing-disable-auto-update')
    options.add_argument('--enable-automation')
    options.add_argument('--password-store=basic')
    options.add_argument('--use-mock-keychain')
    options.add_argument('--remote-debugging-port=9222')

    logger.info(f"Chrome configured with headless={TEST_CONFIG['headless']}, download_dir={download_dir}")
    return options

@pytest.fixture(scope="session")
def firefox_options():
    """Configure Firefox options for testing."""
    options = FirefoxOptions()

    # Set download directory to temporary path under tests/
    test_dir = os.path.dirname(os.path.abspath(__file__))
    download_dir = os.path.join(test_dir, 'tmp', 'downloads')
    os.makedirs(download_dir, exist_ok=True)

    options.set_preference("browser.download.folderList", 2)
    options.set_preference("browser.download.dir", download_dir)
    options.set_preference("browser.download.useDownloadDir", True)
    options.set_preference("browser.download.manager.showWhenStarting", False)
    options.set_preference("browser.helperApps.neverAsk.saveToDisk", "text/csv,application/csv,text/plain")

    if TEST_CONFIG['headless']:
        options.add_argument('--headless')

    # Firefox preferences for stability and OAuth compatibility
    options.set_preference('dom.webdriver.enabled', False)
    options.set_preference('useAutomationExtension', False)
    options.set_preference('general.useragent.override', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:91.0) Gecko/20100101 Firefox/91.0')

    # Disable animations and transitions that can cause instability
    options.set_preference('toolkit.cosmeticAnimations.enabled', False)
    options.set_preference('browser.tabs.animate', False)
    options.set_preference('browser.fullscreen.animateUp', 0)

    # OAuth and popup handling
    options.set_preference('dom.popup_maximum', 0)
    options.set_preference('privacy.clearOnShutdown.offlineApps', True)
    options.set_preference('privacy.clearOnShutdown.passwords', True)
    options.set_preference('privacy.clearOnShutdown.siteSettings', True)

    # Disable various Firefox features that can interfere with testing
    options.set_preference('app.update.enabled', False)
    options.set_preference('browser.safebrowsing.enabled', False)
    options.set_preference('browser.safebrowsing.malware.enabled', False)
    options.set_preference('browser.ping-centre.telemetry', False)
    options.set_preference('browser.tabs.remote.autostart', False)
    options.set_preference('extensions.update.enabled', False)
    options.set_preference('media.navigator.enabled', False)
    options.set_preference('network.http.phishy-userpass-length', 255)
    options.set_preference('offline-apps.allow_by_default', False)
    options.set_preference('prompts.tab_modal.enabled', False)
    options.set_preference('security.csp.enable', False)
    options.set_preference('security.notification_enable_delay', 0)

    logger.info(f"Firefox configured with headless={TEST_CONFIG['headless']}, download_dir={download_dir}")
    return options

@pytest.fixture
def browser(chrome_options, firefox_options):
    """Create and manage browser instance for tests."""
    driver = None
    browser_type = TEST_CONFIG.get('browser', 'chrome').lower()

    try:
        if browser_type == 'firefox':
            # Try system-installed geckodriver first, fall back to webdriver-manager with cache
            try:
                # Attempt to use system geckodriver (no download required)
                driver_service = FirefoxService()
                driver = webdriver.Firefox(service=driver_service, options=firefox_options)
                logger.info("Firefox browser instance created using system geckodriver")
            except Exception as system_error:
                logger.info(f"System geckodriver not found, using webdriver-manager: {system_error}")
                from webdriver_manager.firefox import GeckoDriverManager
                from webdriver_manager.core.driver_cache import DriverCacheManager
                # Use cache for 30 days to avoid GitHub API rate limiting
                cache_manager = DriverCacheManager(valid_range=30)
                driver_service = FirefoxService(GeckoDriverManager(cache_manager=cache_manager).install())
                driver = webdriver.Firefox(service=driver_service, options=firefox_options)
                logger.info("Firefox browser instance created using webdriver-manager")
        else:  # Default to Chrome
            # Try system-installed chromedriver first, fall back to webdriver-manager with cache
            try:
                driver_service = ChromeService()
                driver = webdriver.Chrome(service=driver_service, options=chrome_options)
                logger.info("Chrome browser instance created using system chromedriver")
            except Exception as system_error:
                logger.info(f"System chromedriver not found, using webdriver-manager: {system_error}")
                from webdriver_manager.chrome import ChromeDriverManager
                from webdriver_manager.core.driver_cache import DriverCacheManager
                # Use cache for 30 days to avoid GitHub API rate limiting
                cache_manager = DriverCacheManager(valid_range=30)
                driver_service = ChromeService(ChromeDriverManager(cache_manager=cache_manager).install())
                driver = webdriver.Chrome(service=driver_service, options=chrome_options)
                logger.info("Chrome browser instance created using webdriver-manager")

        driver.implicitly_wait(3)  # Reduced for faster element finding
        driver.set_page_load_timeout(15)  # Reduced from 30s for faster navigation
        yield driver

    except Exception as e:
        logger.error(f"Failed to create {browser_type} browser instance: {e}")
        pytest.fail(f"Cannot run browser tests: {e}")
    finally:
        if driver:
            try:
                driver.quit()
                logger.info(f"{browser_type.title()} browser instance closed")
            except Exception as e:
                logger.warning(f"Error closing {browser_type} browser: {e}")

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
def populated_database(firestore_client):
    """Provide a database with realistic test data loaded from CSV fixture."""
    from tests.utils.load_test_data import load_csv_participants, load_participants_to_firestore
    from models.participant import ParticipantModel

    current_year = datetime.now().year
    participant_model = ParticipantModel(firestore_client, current_year)

    # Clear existing participants for current year to start fresh
    logger.info("Clearing existing participants for clean test")
    try:
        participants_ref = firestore_client.collection(f'participants_{current_year}')
        batch_size = 100
        deleted = 0

        while True:
            docs = participants_ref.limit(batch_size).stream()
            batch = firestore_client.batch()
            count = 0

            for doc in docs:
                batch.delete(doc.reference)
                count += 1
                deleted += 1

            if count == 0:
                break

            batch.commit()

        logger.info(f"Cleared {deleted} existing participants")
    except Exception as e:
        logger.warning(f"Could not clear participants: {e}")

    # Load participants from CSV fixture
    csv_path = os.path.join(os.path.dirname(__file__), 'fixtures', 'test_participants_2025.csv')
    logger.info(f"Loading test participants from {csv_path}")

    participants = load_csv_participants(csv_path)
    logger.info(f"Loaded {len(participants)} participants from CSV")

    # Upload to Firestore
    load_participants_to_firestore(firestore_client, current_year, participants)
    logger.info(f"Successfully loaded {len(participants)} test participants to Firestore")

    yield participants

    # Clean up test participants
    logger.info(f"Cleaning up {len(participants)} CSV test participants")
    try:
        # Batch delete for efficiency
        participants_ref = firestore_client.collection(f'participants_{current_year}')
        batch_size = 100
        deleted = 0

        while True:
            docs = participants_ref.limit(batch_size).stream()
            batch = firestore_client.batch()
            count = 0

            for doc in docs:
                batch.delete(doc.reference)
                count += 1
                deleted += 1

            if count == 0:
                break

            batch.commit()

        logger.info(f"Cleaned up {deleted} participants from database")
    except Exception as e:
        logger.warning(f"Error during cleanup: {e}")

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
    # Check if browser tests require configured browser
    if 'browser' in item.fixturenames:
        browser_type = TEST_CONFIG.get('browser', 'firefox').lower()
        try:
            if browser_type == 'firefox':
                # Test Firefox availability - use cached version to avoid GitHub API calls
                from webdriver_manager.firefox import GeckoDriverManager
                from webdriver_manager.core.driver_cache import DriverCacheManager
                from selenium.webdriver.firefox.service import Service as FirefoxService
                # Try system geckodriver first
                try:
                    FirefoxService()
                except:
                    # Fall back to cached webdriver-manager version (30 day cache)
                    cache_manager = DriverCacheManager(valid_range=30)
                    GeckoDriverManager(cache_manager=cache_manager).install()
            else:
                # Test Chrome availability - use cached version to avoid GitHub API calls
                from webdriver_manager.chrome import ChromeDriverManager
                from webdriver_manager.core.driver_cache import DriverCacheManager
                # Try system chromedriver first
                try:
                    from selenium.webdriver.chrome.service import Service as ChromeService
                    ChromeService()
                except:
                    # Fall back to cached webdriver-manager version (30 day cache)
                    cache_manager = DriverCacheManager(valid_range=30)
                    ChromeDriverManager(cache_manager=cache_manager).install()
        except Exception as e:
            pytest.skip(f"{browser_type.title()} browser not available for testing: {e}")

    # Note: Admin tests use get_test_password() for credentials, so no skip needed
