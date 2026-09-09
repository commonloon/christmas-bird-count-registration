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
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.firefox.service import Service as FirefoxService

# Add project root to Python path for imports
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from tests.test_config import (
    TEST_CONFIG, TEST_ACCOUNTS, TEST_CIRCLE_SLUG,
    get_base_url, get_database_name, LOGGING_CONFIG
)

# Configure logging
logging.basicConfig(
    level=getattr(logging, LOGGING_CONFIG['level']),
    format=LOGGING_CONFIG['format']
)
logger = logging.getLogger(__name__)

_LOCAL_HOSTS = ('localhost', '127.0.0.1')


def _is_safe_test_host(hostname):
    """True for localhost/127.0.0.1 or anything under the IANA-reserved .test TLD
    (RFC 6761 - permanently reserved, can never resolve on the real internet). Used
    to allow the dedicated local 'test' circle (test.cbc.test, see .env.example)
    without opening this guard up to any real-looking hostname."""
    if not hostname:
        return False
    hostname = hostname.lower()
    return hostname in _LOCAL_HOSTS or hostname == 'test' or hostname.endswith('.test')


def pytest_sessionstart(session):
    """Hard-abort the whole run if it isn't pointed at a local database/server.

    Production Postgres lives on a separate host from any app server (SSH-tunnel
    only), so a legitimate local test run's DATABASE_URL host will never be
    anything but localhost/127.0.0.1 - even if this suite were somehow launched
    from the production app server itself. Runs once, before any fixture or
    test executes (stronger than an autouse fixture, which only runs for tests
    that request it).
    """
    from sqlalchemy.engine import make_url
    from dotenv import load_dotenv

    # Nothing has loaded .env yet this early (config.database does it, but only
    # once something imports that module) - load it ourselves so DATABASE_URL
    # is actually populated before we check it.
    load_dotenv()

    database_url = os.environ.get('DATABASE_URL', '')
    if not database_url:
        pytest.exit("Refusing to run: DATABASE_URL is not set.", returncode=1)

    db_host = make_url(database_url).host
    if db_host not in _LOCAL_HOSTS:
        pytest.exit(
            f"Refusing to run: DATABASE_URL host '{db_host}' is not localhost/127.0.0.1. "
            "This test suite deletes and inserts rows and must never run against a "
            "non-local database.",
            returncode=1
        )

    from urllib.parse import urlparse
    from config.cloud import TEST_BASE_URL

    # Check get_base_url() (what get_base_url()-based tests actually navigate to) AND
    # config.cloud.TEST_BASE_URL directly - tests/installation/*.py read TEST_BASE_URL
    # straight from config/cloud.py, bypassing get_base_url()/TEST_TARGET entirely.
    # That gap once let those tests silently send real browser traffic to a live
    # legacy Cloud Run host (cbc-test.naturevancouver.ca) that looked decommissioned
    # but wasn't - checking both constants here closes it structurally rather than
    # trusting every test file to route through the one already-guarded function.
    for url in (get_base_url(), TEST_BASE_URL):
        host = urlparse(url).hostname
        if not _is_safe_test_host(host):
            pytest.exit(
                f"Refusing to run: test target '{url}' (host '{host}') is not "
                "localhost/127.0.0.1 or a *.test hostname. This test suite submits real "
                "registrations/emails and must never run against a remote server "
                "(check TEST_TARGET / config/cloud.py).",
                returncode=1
            )

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
def db_session():
    """Provide the app's real SQLAlchemy session (Postgres) for test setup/teardown.

    Replaces the old Firestore client fixture - this app has been fully off
    Firestore since the FullHost migration. Session-scoped since
    config.database.get_db_session() itself manages a single underlying
    connection; tests needing isolation should scope their own data changes,
    not create a second engine here.
    """
    from config.database import get_db_session
    return get_db_session()

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

    # Cookie handling for OAuth (CRITICAL for login flow)
    options.set_preference('network.cookie.cookieBehavior', 0)  # Accept all cookies
    options.set_preference('network.cookie.lifetimePolicy', 0)  # Use default cookie lifetime
    options.set_preference('privacy.clearOnShutdown.cookies', False)  # Don't clear cookies on shutdown

    # Don't clear site settings that are needed for OAuth flow
    options.set_preference('privacy.clearOnShutdown.offlineApps', False)
    options.set_preference('privacy.clearOnShutdown.passwords', False)
    options.set_preference('privacy.clearOnShutdown.siteSettings', False)

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

@pytest.fixture(scope="session")
def authenticated_browser(chrome_options, firefox_options):
    """Create browser and authenticate once for entire test session.

    Authenticates via a directly-injected signed session cookie (see
    tests/utils/auth_utils.py) rather than a real magic-link email, once per
    session, and reuses the browser across all tests in the session.
    Uses admin_primary credentials by default.
    """
    from tests.utils.auth_utils import admin_login_for_test

    driver = None
    browser_type = TEST_CONFIG.get('browser', 'firefox').lower()

    try:
        if browser_type == 'firefox':
            try:
                driver_service = FirefoxService()
                driver = webdriver.Firefox(service=driver_service, options=firefox_options)
                logger.info("Class-scoped Firefox browser instance created using system geckodriver")
            except Exception as system_error:
                logger.info(f"System geckodriver not found, using webdriver-manager: {system_error}")
                from webdriver_manager.firefox import GeckoDriverManager
                from webdriver_manager.core.driver_cache import DriverCacheManager
                cache_manager = DriverCacheManager(valid_range=30)
                driver_service = FirefoxService(GeckoDriverManager(cache_manager=cache_manager).install())
                driver = webdriver.Firefox(service=driver_service, options=firefox_options)
                logger.info("Class-scoped Firefox browser instance created using webdriver-manager")
        else:
            try:
                driver_service = ChromeService()
                driver = webdriver.Chrome(service=driver_service, options=chrome_options)
                logger.info("Class-scoped Chrome browser instance created using system chromedriver")
            except Exception as system_error:
                logger.info(f"System chromedriver not found, using webdriver-manager: {system_error}")
                from webdriver_manager.chrome import ChromeDriverManager
                from webdriver_manager.core.driver_cache import DriverCacheManager
                cache_manager = DriverCacheManager(valid_range=30)
                driver_service = ChromeService(ChromeDriverManager(cache_manager=cache_manager).install())
                driver = webdriver.Chrome(service=driver_service, options=chrome_options)
                logger.info("Class-scoped Chrome browser instance created using webdriver-manager")

        driver.implicitly_wait(3)
        driver.set_page_load_timeout(15)

        # Perform authentication ONCE for the entire class
        logger.info("Performing one-time session-cookie authentication for test class")
        admin_login_for_test(driver, get_base_url(), TEST_ACCOUNTS['admin_primary'])
        logger.info("Authentication successful - session will be reused across all tests")

        yield driver

    finally:
        if driver:
            driver.quit()
            logger.info("Class-scoped browser instance closed")

# Database State Management Fixtures
@pytest.fixture
def clean_database(db_session):
    """Provide a clean database state for tests (Postgres - replaces the old
    per-year Firestore collection wipe with row deletes scoped to the dedicated
    test circle, since every circle's data now lives in shared participants/
    removal_log tables)."""
    from models.db import Participant, RemovalLog

    circle_slug = TEST_CIRCLE_SLUG
    current_year = TEST_CONFIG['current_year']
    isolation_year = TEST_CONFIG['isolation_test_year']

    def clear_years():
        """Delete participants/removal_log rows for the test/isolation years."""
        for year in (current_year, isolation_year):
            try:
                db_session.query(Participant).filter_by(circle_slug=circle_slug, year=year).delete()
                db_session.query(RemovalLog).filter_by(circle_slug=circle_slug, year=year).delete()
            except Exception as e:
                logger.warning(f"Error clearing year {year} for {circle_slug}: {e}")
        db_session.commit()
        logger.info(f"Cleared {circle_slug} participants/removal_log for years {current_year}, {isolation_year}")

    # Clear before test
    clear_years()
    logger.info("Database cleaned for test")

    yield db_session

    # Optionally clear after test (uncomment if needed)
    # clear_years()
    # logger.info("Database cleaned after test")

@pytest.fixture(scope="class")
def populated_database(db_session):
    """Provide a database with realistic test data loaded from CSV fixture.

    Class-scoped: Loads test data once per test class, allowing related tests
    to share the same dataset. Tests within a class should use different
    participants to avoid interference.
    """
    from tests.utils.load_test_data import load_csv_participants, load_participants_to_postgres

    current_year = datetime.now().year
    circle_slug = TEST_CIRCLE_SLUG

    csv_path = os.path.join(os.path.dirname(__file__), 'fixtures', 'test_participants_2025.csv')
    logger.info(f"Loading test participants from {csv_path}")
    participants = load_csv_participants(csv_path)

    load_participants_to_postgres(db_session, current_year, participants, clear_first=True, circle_slug=circle_slug)
    logger.info(f"Successfully loaded {len(participants)} test participants into Postgres")

    yield participants

    # Clean up test participants
    from models.db import Participant, RemovalLog
    logger.info(f"Cleaning up CSV test participants for {circle_slug} {current_year}")
    db_session.query(Participant).filter_by(circle_slug=circle_slug, year=current_year).delete()
    db_session.query(RemovalLog).filter_by(circle_slug=circle_slug, year=current_year).delete()
    db_session.commit()

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

# Coverage download fixture (session-scoped, runs after all tests)
@pytest.fixture(scope="session", autouse=True)
def download_coverage_after_tests():
    """Download coverage data from test server after all Selenium tests complete.

    This fixture automatically runs at the end of the test session if coverage
    is enabled on the server. It authenticates as admin and downloads the
    coverage file for merging with local test coverage.
    """
    yield  # Let all tests run first

    # After all tests complete, download coverage if enabled
    try:
        import requests
        from tests.test_config import get_base_url

        base_url = get_base_url()

        # Check if coverage is enabled on server
        status_response = requests.get(f"{base_url}/test/coverage/status", timeout=10)
        if status_response.status_code != 200:
            logger.info("Coverage status endpoint not available - coverage not enabled")
            return

        status_data = status_response.json()
        if not status_data.get('enabled'):
            logger.info("Coverage not enabled on server - skipping download")
            return

        logger.info("Coverage enabled on server - downloading coverage data")

        # Create session and authenticate
        session = requests.Session()

        # Note: This requires manual cookie/session handling since we can't reuse Selenium session
        # For now, we'll use the simpler approach of requiring manual download
        # TODO: Implement automated session transfer from Selenium to requests

        logger.info("Coverage download requires manual step:")
        logger.info(f"1. Visit {base_url}/test/coverage/save in your browser while logged in as admin")
        logger.info(f"2. Save the .coverage.server file to the tests/ directory")
        logger.info(f"3. Run: coverage combine .coverage .coverage.server")
        logger.info(f"4. Run: coverage html")
        logger.info(f"5. Open htmlcov/index.html to view combined coverage")

    except Exception as e:
        logger.warning(f"Could not download coverage data: {e}")

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
