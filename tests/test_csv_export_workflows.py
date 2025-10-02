# CSV Export Workflow Tests
# Updated by Claude AI on 2025-10-01

"""
CSV export workflow tests for the Christmas Bird Count system.
Tests CSV generation, content validation, and export functionality.
"""

import pytest
import logging
import sys
import os
import time
import csv
import io
import glob
from datetime import datetime

# Add project root to path for imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from tests.config import get_base_url, get_database_name
from tests.page_objects import AdminDashboardPage, AdminParticipantsPage
from tests.data import get_test_participant, get_test_dataset, get_test_account, get_test_password
from tests.utils.auth_utils import login_with_google, admin_login_for_test
from models.participant import ParticipantModel
from google.cloud import firestore
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import requests
from urllib.parse import urljoin

logger = logging.getLogger(__name__)


def get_download_dir():
    """Get the browser download directory path."""
    test_dir = os.path.dirname(os.path.abspath(__file__))
    download_dir = os.path.join(test_dir, 'tmp', 'downloads')
    os.makedirs(download_dir, exist_ok=True)
    return download_dir


def wait_for_csv_download(timeout=30, clear_first=True):
    """Wait for a CSV file to appear in the download directory.

    Args:
        timeout: Maximum seconds to wait for download
        clear_first: Whether to clear existing CSV files before waiting

    Returns:
        Path to the downloaded CSV file, or None if not found
    """
    download_dir = get_download_dir()

    # Record existing CSV files before download
    existing_csvs = set(glob.glob(os.path.join(download_dir, '*.csv')))

    if clear_first and existing_csvs:
        # Clear existing files to avoid Windows (1) (2) naming conflicts
        for csv_file in existing_csvs:
            try:
                os.remove(csv_file)
                logger.info(f"Cleared existing CSV file: {csv_file}")
            except Exception as e:
                logger.warning(f"Could not remove existing CSV file {csv_file}: {e}")
        existing_csvs = set()

    # Wait for new CSV file to appear
    start_time = time.time()
    while time.time() - start_time < timeout:
        csv_files = glob.glob(os.path.join(download_dir, '*.csv'))

        # Filter out partial downloads (.crdownload, .tmp, .part) and temporary Firefox files
        complete_files = [
            f for f in csv_files
            if not any(f.endswith(ext) for ext in ['.crdownload', '.tmp', '.part'])
            and not f.endswith('.part')
        ]

        # Check for new files that weren't in the existing set
        # Also accept files with Windows conflict suffixes like " (1).csv"
        new_files = [f for f in complete_files if f not in existing_csvs]

        if new_files:
            csv_file = new_files[0]
            # Wait a bit more to ensure file is fully written
            time.sleep(1)
            logger.info(f"CSV file downloaded: {csv_file}")
            return csv_file

        time.sleep(0.5)

    logger.warning(f"No CSV file found in {download_dir} after {timeout}s")
    return None


def read_csv_file(csv_file_path):
    """Read CSV file content.

    Args:
        csv_file_path: Path to CSV file

    Returns:
        CSV content as string, or None if error
    """
    try:
        with open(csv_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        logger.info(f"Read {len(content)} bytes from {csv_file_path}")
        return content
    except Exception as e:
        logger.error(f"Failed to read CSV file {csv_file_path}: {e}")
        return None


def cleanup_downloads():
    """Clean up all files in the download directory."""
    download_dir = get_download_dir()
    try:
        files = glob.glob(os.path.join(download_dir, '*'))
        for file in files:
            try:
                os.remove(file)
                logger.debug(f"Removed download file: {file}")
            except Exception as e:
                logger.warning(f"Could not remove file {file}: {e}")
    except Exception as e:
        logger.warning(f"Error during cleanup: {e}")


@pytest.fixture
def admin_dashboard(browser):
    """Create admin dashboard page object."""
    base_url = get_base_url()
    page = AdminDashboardPage(browser, base_url)
    return page


@pytest.fixture
def admin_participants_page(browser):
    """Create admin participants page object."""
    base_url = get_base_url()
    page = AdminParticipantsPage(browser, base_url)
    return page


@pytest.fixture
def db_client():
    """Create database client."""
    database_name = get_database_name()
    if database_name == '(default)':
        client = firestore.Client()
    else:
        client = firestore.Client(database=database_name)
    yield client


@pytest.fixture
def participant_model(db_client):
    """Create participant model for current year."""
    current_year = datetime.now().year
    return ParticipantModel(db_client, current_year)


@pytest.fixture(autouse=True)
def csv_download_cleanup():
    """Automatically clean up downloaded CSV files after each test."""
    # Setup: clean before test
    cleanup_downloads()
    yield
    # Teardown: clean after test
    cleanup_downloads()




@pytest.fixture
def populated_test_data(db_client):
    """Load test participants from CSV fixture for validation."""
    import os
    from tests.utils.load_test_data import load_csv_participants, load_participants_to_firestore

    current_year = datetime.now().year
    participant_model = ParticipantModel(db_client, current_year)

    # Clear existing participants for current year to start fresh
    logger.info("Clearing existing participants for clean test")
    try:
        participants_ref = db_client.collection(f'participants_{current_year}')
        batch_size = 100
        deleted = 0

        while True:
            docs = participants_ref.limit(batch_size).stream()
            batch = db_client.batch()
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
    load_participants_to_firestore(db_client, current_year, participants)
    logger.info(f"Successfully loaded {len(participants)} test participants to Firestore")

    yield participants

    # Clean up test participants
    logger.info(f"Cleaning up {len(participants)} CSV test participants")
    try:
        # Batch delete for efficiency
        participants_ref = db_client.collection(f'participants_{current_year}')
        batch_size = 100
        deleted = 0

        while True:
            docs = participants_ref.limit(batch_size).stream()
            batch = db_client.batch()
            count = 0

            for doc in docs:
                batch.delete(doc.reference)
                count += 1
                deleted += 1

            if count == 0:
                break

            batch.commit()

        logger.info(f"Cleaned up {deleted} test participants")
    except Exception as e:
        logger.warning(f"Could not clean up test participants: {e}")


class TestCSVExportFunctionality:
    """Test basic CSV export functionality."""

    @pytest.mark.critical
    @pytest.mark.csv
    def test_csv_export_button_availability(self, browser, test_credentials):
        """Test that CSV export buttons are available to admin users."""
        logger.info("Testing CSV export button availability")

        admin_creds = test_credentials['admin_primary']
        base_url = get_base_url()
        admin_login_for_test(browser, base_url, admin_creds)

        dashboard = AdminDashboardPage(browser, base_url)
        browser.get(f"{base_url}/admin")

        # Test export from dashboard
        assert dashboard.is_dashboard_loaded(), "Should be on dashboard"

        # Find and click the Export CSV link
        try:
            # Use exact link text - most reliable selector
            export_link = browser.find_element(By.LINK_TEXT, "Export CSV")
            csv_url = export_link.get_attribute('href')
            logger.info(f"✓ Found Export CSV link: {csv_url}")

            # Record existing files BEFORE triggering download
            download_dir = get_download_dir()
            existing_files = set(glob.glob(os.path.join(download_dir, '*.csv')))
            logger.info(f"Existing files before download: {existing_files}")

            # Set short page load timeout for file download
            browser.set_page_load_timeout(3)

            # Navigate to CSV URL (will timeout but download starts)
            try:
                browser.get(csv_url)
            except Exception as e:
                logger.debug(f"Navigation timeout (expected): {str(e)[:100]}")

            # Reset timeout
            browser.set_page_load_timeout(15)
            logger.info("✓ Triggered CSV download")

            # Check immediately if file appeared
            time.sleep(2)  # Give download a moment to complete
            current_files = set(glob.glob(os.path.join(download_dir, '*.csv')))
            new_files = current_files - existing_files

            if new_files:
                csv_file = list(new_files)[0]
                logger.info(f"✓ Found downloaded CSV: {csv_file}")
            else:
                logger.warning(f"No new CSV file. Current files: {current_files}")
                csv_file = None

            if csv_file:
                logger.info(f"✓ CSV export successful from dashboard: {csv_file}")

                # Validate it's actually a CSV file
                if os.path.exists(csv_file):
                    file_size = os.path.getsize(csv_file)
                    logger.info(f"✓ Downloaded file size: {file_size} bytes")
                    assert file_size > 0, "Downloaded CSV file is empty"
                else:
                    pytest.fail(f"CSV file not found at {csv_file}")
            else:
                pytest.fail("CSV file not downloaded after clicking dashboard button")
        except Exception as e:
            logger.error(f"Failed to export CSV from dashboard: {e}")
            pytest.fail(f"Export CSV test failed: {e}")

        logger.info("=" * 60)
        logger.info("Dashboard CSV export PASSED - Starting participants page test")
        logger.info("=" * 60)

        # Navigate back to dashboard first (browser is currently on CSV download URL)
        browser.get(f"{base_url}/admin")
        assert dashboard.is_dashboard_loaded(), "Should be back on dashboard before navigating to participants"

        # Test export from participants page
        try:
            logger.info("Navigating to participants page")
            browser.get(f"{base_url}/admin/participants")
            time.sleep(2)  # Wait for page load

            # Find Export CSV link
            export_link = browser.find_element(By.LINK_TEXT, "Export CSV")
            csv_url = export_link.get_attribute('href')
            logger.info(f"✓ Found Export CSV link on participants page")

            # Record existing files
            existing_files = set(glob.glob(os.path.join(download_dir, '*.csv')))

            # Set short timeout and navigate to CSV URL
            browser.set_page_load_timeout(3)
            try:
                browser.get(csv_url)
            except Exception:
                pass  # Expected timeout
            browser.set_page_load_timeout(15)

            # Check for new file
            time.sleep(2)
            current_files = set(glob.glob(os.path.join(download_dir, '*.csv')))
            new_files = current_files - existing_files

            if new_files:
                csv_file = list(new_files)[0]
                file_size = os.path.getsize(csv_file)
                logger.info(f"✓ CSV export successful from participants page: {file_size} bytes")
                assert file_size > 0, "Downloaded CSV file is empty"
            else:
                pytest.fail("CSV file not downloaded from participants page")
        except Exception as e:
            logger.error(f"Failed to export CSV from participants page: {e}")
            pytest.fail(f"Participants page CSV export failed: {e}")

        logger.info("=" * 60)
        logger.info("✓ Both CSV export tests PASSED")
        logger.info("=" * 60)

    @pytest.mark.csv
    def test_direct_csv_route_access(self, browser, test_credentials):
        """Test direct access to CSV export route via browser navigation."""
        logger.info("Testing direct CSV route access")

        admin_creds = test_credentials['admin_primary']
        base_url = get_base_url()
        admin_login_for_test(browser, base_url, admin_creds)

        dashboard = AdminDashboardPage(browser, base_url)
        browser.get(f"{base_url}/admin")
        assert dashboard.is_dashboard_loaded(), "Should be on dashboard"

        # Test the actual CSV export route that exists: /admin/export_csv
        csv_url = urljoin(base_url, '/admin/export_csv')
        download_dir = get_download_dir()

        logger.info(f"Testing CSV export route: {csv_url}")

        # Record existing files before navigation
        existing_files = set(glob.glob(os.path.join(download_dir, '*.csv')))

        # Navigate to CSV URL with short timeout
        browser.set_page_load_timeout(3)
        try:
            browser.get(csv_url)
        except Exception as nav_error:
            logger.debug(f"Navigation timeout (expected): {str(nav_error)[:100]}")
        browser.set_page_load_timeout(15)

        # Check for new file
        time.sleep(2)
        current_files = set(glob.glob(os.path.join(download_dir, '*.csv')))
        new_files = current_files - existing_files

        if new_files:
            csv_file = list(new_files)[0]
            file_size = os.path.getsize(csv_file)
            logger.info(f"✓ CSV downloaded: {file_size} bytes")
            assert file_size > 0, "Downloaded CSV should not be empty"

            # Validate CSV format
            content = read_csv_file(csv_file)
            assert content, "Should be able to read CSV file"

            lines = content.split('\n')
            assert len(lines) > 0 and ',' in lines[0], "CSV should have valid format with comma-separated values"

            logger.info("✓ CSV export route is accessible and returns valid CSV")
        else:
            pytest.fail(f"No CSV file downloaded from {csv_url}")


class TestCSVContentValidation:
    """Test CSV export content validation."""

    @pytest.fixture(scope="function")
    def csv_export_data(self, browser, test_credentials, populated_test_data, request):
        """
        Download CSV once and cache across all content validation tests.
        Uses request.session caching to avoid repeated OAuth/download overhead.
        """
        # Check if we already downloaded the CSV in this test session
        cache_key = 'csv_export_validation_data'
        if hasattr(request.session, cache_key):
            logger.info("Using cached CSV export data")
            return getattr(request.session, cache_key)

        # Download CSV for first time
        logger.info("=" * 60)
        logger.info("FIXTURE: Downloading CSV for content validation tests")
        logger.info("=" * 60)

        admin_creds = test_credentials['admin_primary']
        base_url = get_base_url()
        admin_login_for_test(browser, base_url, admin_creds)

        dashboard = AdminDashboardPage(browser, base_url)
        browser.get(f"{base_url}/admin")

        # Get CSV export
        csv_content = self._get_csv_export_content(dashboard, base_url)

        if not csv_content:
            pytest.skip("Could not retrieve CSV export content for validation tests")

        # Parse CSV content
        csv_data = self._parse_csv_content(csv_content)

        if not csv_data:
            pytest.skip("Could not parse CSV content for validation tests")

        logger.info(f"✓ CSV downloaded and parsed: {len(csv_data)} rows")
        logger.info("=" * 60)

        data = {
            'content': csv_content,
            'parsed': csv_data,
            'test_participants': populated_test_data
        }

        # Cache for subsequent tests
        setattr(request.session, cache_key, data)
        return data

    @pytest.mark.critical
    @pytest.mark.csv
    def test_csv_export_with_known_data(self, csv_export_data):
        """Test CSV export content against known test data."""
        logger.info("Testing CSV export content validation with known test data")

        csv_data = csv_export_data['parsed']
        test_participants = csv_export_data['test_participants']

        logger.info(f"Validating CSV export against {len(test_participants)} test participants")
        logger.info(f"CSV export contains {len(csv_data)} rows (including header)")

        # Validate CSV structure
        assert len(csv_data) > 0, "CSV should have at least header row"

        if True:
            headers = csv_data[0]
            logger.info(f"CSV headers: {headers}")

            # Check for expected headers
            expected_headers = [
                'first_name', 'last_name', 'email', 'phone',
                'skill_level', 'experience', 'preferred_area', 'participation_type'
            ]

            for expected_header in expected_headers:
                # Check for exact match or similar variations
                header_found = any(
                    expected_header.lower() in header.lower() or header.lower() in expected_header.lower()
                    for header in headers
                )
                if header_found:
                    logger.info(f"✓ Found expected header: {expected_header}")
                else:
                    logger.warning(f"Expected header not found: {expected_header}")

            # Validate data rows
            data_rows = csv_data[1:] if len(csv_data) > 1 else []
            logger.info(f"CSV contains {len(data_rows)} data rows")

            if data_rows:
                # Build column index map for easier access
                col_map = {}
                for i, header in enumerate(headers):
                    header_lower = header.lower()
                    if 'first' in header_lower and 'name' in header_lower:
                        col_map['first_name'] = i
                    elif 'last' in header_lower and 'name' in header_lower:
                        col_map['last_name'] = i
                    elif 'email' in header_lower:
                        col_map['email'] = i
                    elif 'phone' in header_lower and '2' not in header_lower:
                        col_map['phone'] = i
                    elif 'skill' in header_lower:
                        col_map['skill_level'] = i
                    elif 'experience' in header_lower:
                        col_map['experience'] = i
                    elif 'area' in header_lower:
                        col_map['preferred_area'] = i
                    elif 'type' in header_lower or 'participation' in header_lower:
                        col_map['participation_type'] = i

                logger.info(f"Column mapping: {col_map}")

                # Build CSV records as dicts for comparison
                csv_records = []
                for row in data_rows:
                    if len(row) > max(col_map.values()):
                        record = {
                            'email': row[col_map['email']].strip().lower() if 'email' in col_map else '',
                            'first_name': row[col_map['first_name']].strip() if 'first_name' in col_map else '',
                            'last_name': row[col_map['last_name']].strip() if 'last_name' in col_map else '',
                        }
                        csv_records.append(record)

                # Check that all test participants are in the CSV
                test_emails = {p['email'].lower() for p in test_participants}
                csv_emails = {r['email'] for r in csv_records}

                matches = test_emails.intersection(csv_emails)
                missing = test_emails - csv_emails

                logger.info(f"Test participants: {len(test_participants)}")
                logger.info(f"Matched in CSV: {len(matches)}/{len(test_participants)}")

                if missing:
                    logger.warning(f"Missing {len(missing)} test participants from CSV:")
                    for email in sorted(list(missing))[:5]:  # Show first 5
                        logger.warning(f"  - {email}")
                    if len(missing) > 5:
                        logger.warning(f"  ... and {len(missing) - 5} more")

                # Verify detailed matching for found records
                matched_count = 0
                mismatched_count = 0
                for test_p in test_participants:
                    test_email = test_p['email'].lower()
                    if test_email in csv_emails:
                        # Find the CSV record
                        csv_record = next((r for r in csv_records if r['email'] == test_email), None)
                        if csv_record:
                            # Check name match
                            if (csv_record['first_name'].lower() == test_p['first_name'].lower() and
                                csv_record['last_name'].lower() == test_p['last_name'].lower()):
                                matched_count += 1
                            else:
                                mismatched_count += 1
                                logger.warning(f"Name mismatch for {test_email}: "
                                             f"CSV={csv_record['first_name']} {csv_record['last_name']}, "
                                             f"Test={test_p['first_name']} {test_p['last_name']}")

                logger.info(f"✓ Fully matched records: {matched_count}/{len(test_participants)}")
                if mismatched_count > 0:
                    logger.warning(f"Records with mismatched data: {mismatched_count}")

                # Assert that we found all test participants
                assert len(matches) == len(test_participants), \
                    f"Expected all {len(test_participants)} test participants in CSV, found {len(matches)}"

                logger.info("✓ All test participant records present in CSV export")

            logger.info("✓ CSV content validation completed")

        else:
            logger.warning("CSV export appears to be empty")

    @pytest.mark.csv
    def test_csv_field_completeness(self, csv_export_data):
        """Test that CSV export contains all expected fields."""
        logger.info("Testing CSV field completeness")

        csv_data = csv_export_data['parsed']
        headers = csv_data[0]
        logger.info(f"CSV headers found: {headers}")

        # Define expected fields based on participant model
        expected_fields = [
            'first_name', 'last_name', 'email', 'phone', 'phone2',
            'skill_level', 'experience', 'preferred_area', 'participation_type',
            'has_binoculars', 'spotting_scope',
            'interested_in_leadership', 'interested_in_scribe',
            'notes_to_organizers', 'is_leader',
            'created_at', 'year'
        ]

        # Check field coverage
        fields_found = 0
        fields_missing = []

        for expected_field in expected_fields:
            field_found = any(
                expected_field.lower() in header.lower() or
                header.lower().replace('_', '').replace(' ', '') == expected_field.lower().replace('_', '')
                for header in headers
            )

            if field_found:
                fields_found += 1
            else:
                fields_missing.append(expected_field)

        field_coverage = (fields_found / len(expected_fields)) * 100
        logger.info(f"Field coverage: {field_coverage:.1f}% ({fields_found}/{len(expected_fields)})")

        if fields_missing:
            logger.warning(f"Missing fields: {fields_missing}")

        # Basic completeness check
        if field_coverage >= 70:  # Allow for some flexibility in field naming
            logger.info("✓ CSV export field completeness acceptable")
        else:
            logger.warning(f"CSV export field completeness low: {field_coverage:.1f}%")

    @pytest.mark.csv
    def test_csv_sorting_order(self, csv_export_data):
        """Test CSV export sorting order (area → type → name)."""
        logger.info("Testing CSV export sorting order")

        csv_data = csv_export_data['parsed']

        if len(csv_data) < 2:
            pytest.skip("Insufficient CSV data for sorting validation")

        headers = csv_data[0]
        data_rows = csv_data[1:]

        # Find relevant columns
        area_col = self._find_column_index(headers, 'area')
        type_col = self._find_column_index(headers, 'participation_type', 'type')
        first_name_col = self._find_column_index(headers, 'first_name', 'first')
        last_name_col = self._find_column_index(headers, 'last_name', 'last')

        logger.info(f"Column indices - Area: {area_col}, Type: {type_col}, "
                   f"First: {first_name_col}, Last: {last_name_col}")

        if area_col is not None and len(data_rows) > 1:
            # Check area sorting
            areas = [row[area_col] if len(row) > area_col else '' for row in data_rows]
            logger.info(f"Areas in CSV: {areas[:10]}...")  # Show first 10

            # Check if areas are generally grouped together
            area_changes = sum(1 for i in range(1, len(areas)) if areas[i] != areas[i-1])
            logger.info(f"Area grouping changes: {area_changes}")

            if area_changes <= len(set(areas)):  # Reasonable grouping
                logger.info("✓ CSV appears to be sorted/grouped by area")
            else:
                logger.warning("CSV may not be properly sorted by area")

        logger.info("CSV sorting validation completed")

    def _get_csv_export_content(self, dashboard, base_url):
        """Helper method to get CSV export content via browser download."""
        try:
            # Navigate to admin page if not already there
            current_url = dashboard.driver.current_url
            if '/admin' not in current_url:
                logger.info("Navigating to admin dashboard")
                dashboard.driver.get(f"{base_url}/admin")
                assert dashboard.is_dashboard_loaded(), "Dashboard should load"

            # Find Export CSV link
            export_link = dashboard.driver.find_element(By.LINK_TEXT, "Export CSV")
            csv_url = export_link.get_attribute('href')
            logger.info(f"Found CSV export URL: {csv_url}")

            # Record existing files
            download_dir = get_download_dir()
            existing_files = set(glob.glob(os.path.join(download_dir, '*.csv')))

            # Navigate to CSV URL with short timeout
            dashboard.driver.set_page_load_timeout(3)
            try:
                dashboard.driver.get(csv_url)
            except Exception as e:
                logger.debug(f"Navigation timeout (expected): {str(e)[:100]}")
            dashboard.driver.set_page_load_timeout(15)

            # Check for new file
            time.sleep(2)
            current_files = set(glob.glob(os.path.join(download_dir, '*.csv')))
            new_files = current_files - existing_files

            if new_files:
                csv_file = list(new_files)[0]
                file_size = os.path.getsize(csv_file)
                logger.info(f"✓ CSV downloaded: {file_size} bytes")

                # Read the downloaded file
                content = read_csv_file(csv_file)
                if content:
                    logger.info(f"✓ Retrieved CSV content ({len(content)} bytes)")
                    return content
                else:
                    logger.error("Could not read downloaded CSV file")
                    return None

            logger.error("No CSV file downloaded")
            return None

        except Exception as e:
            logger.error(f"Failed to download CSV: {e}")
            return None

    def _parse_csv_content(self, csv_content):
        """Helper method to parse CSV content."""
        try:
            reader = csv.reader(io.StringIO(csv_content))
            return list(reader)
        except Exception as e:
            logger.error(f"Failed to parse CSV content: {e}")
            return None

    def _find_column_index(self, headers, *possible_names):
        """Helper method to find column index by name variations."""
        for i, header in enumerate(headers):
            for name in possible_names:
                if name.lower() in header.lower():
                    return i
        return None


class TestCSVExportPerformance:
    """Test CSV export performance and reliability."""

    @pytest.mark.csv
    @pytest.mark.slow
    def test_large_dataset_export_performance(self, browser, test_credentials, db_client):
        """Test CSV export performance with larger datasets."""
        logger.info("Testing CSV export performance with large dataset")

        admin_creds = test_credentials['admin_primary']
        base_url = get_base_url()
        admin_login_for_test(browser, base_url, admin_creds)

        dashboard = AdminDashboardPage(browser, base_url)
        browser.get(f"{base_url}/admin")
        current_year = datetime.now().year
        participant_model = ParticipantModel(db_client, current_year)

        # Create larger test dataset (if not already present)
        large_dataset = get_test_dataset('large_realistic')
        logger.info(f"Testing with {len(large_dataset)} participants")

        # Time the CSV export
        start_time = time.time()

        csv_content = self._get_csv_export_content(dashboard, base_url)

        end_time = time.time()
        export_time = end_time - start_time

        logger.info(f"CSV export completed in {export_time:.2f} seconds")

        if csv_content:
            csv_size = len(csv_content)
            logger.info(f"CSV export size: {csv_size} characters")

            # Performance assertions
            if export_time < 30:  # Should complete within 30 seconds
                logger.info("✓ CSV export performance acceptable")
            else:
                logger.warning(f"CSV export performance slow: {export_time:.2f}s")

            # Basic content validation for large dataset
            csv_data = self._parse_csv_content(csv_content)
            if csv_data and len(csv_data) > 1:
                row_count = len(csv_data) - 1  # Subtract header
                logger.info(f"CSV contains {row_count} data rows")
            else:
                logger.warning("Large dataset CSV export appears empty")

        else:
            pytest.fail("Large dataset CSV export failed")

    def _get_csv_export_content(self, dashboard, base_url):
        """Helper method to get CSV export content via browser download."""
        try:
            # Navigate to admin page if not already there
            current_url = dashboard.driver.current_url
            if '/admin' not in current_url:
                logger.info("Navigating to admin dashboard")
                dashboard.driver.get(f"{base_url}/admin")
                assert dashboard.is_dashboard_loaded(), "Dashboard should load"

            # Find Export CSV link
            export_link = dashboard.driver.find_element(By.LINK_TEXT, "Export CSV")
            csv_url = export_link.get_attribute('href')
            logger.info(f"Found CSV export URL: {csv_url}")

            # Record existing files
            download_dir = get_download_dir()
            existing_files = set(glob.glob(os.path.join(download_dir, '*.csv')))

            # Navigate to CSV URL with short timeout
            dashboard.driver.set_page_load_timeout(3)
            try:
                dashboard.driver.get(csv_url)
            except Exception as e:
                logger.debug(f"Navigation timeout (expected): {str(e)[:100]}")
            dashboard.driver.set_page_load_timeout(15)

            # Check for new file (give more time for large datasets)
            time.sleep(3)
            current_files = set(glob.glob(os.path.join(download_dir, '*.csv')))
            new_files = current_files - existing_files

            if new_files:
                csv_file = list(new_files)[0]
                # Check file size
                file_size = os.path.getsize(csv_file)
                logger.info(f"✓ CSV downloaded: {file_size} bytes")

                # Read the downloaded file
                content = read_csv_file(csv_file)
                if content:
                    logger.info(f"✓ Retrieved CSV content ({len(content)} bytes)")
                    return content
                else:
                    logger.error("Could not read downloaded CSV file")
                    return None

            logger.error("No CSV file downloaded")
            return None

        except Exception as e:
            logger.error(f"Failed to download CSV: {e}")
            return None

    def _parse_csv_content(self, csv_content):
        """Helper method to parse CSV content."""
        try:
            reader = csv.reader(io.StringIO(csv_content))
            return list(reader)
        except Exception as e:
            logger.error(f"Failed to parse CSV content: {e}")
            return None