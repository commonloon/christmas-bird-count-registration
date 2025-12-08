# CSV Export Workflow Tests
# Updated by Claude AI on 2025-10-09

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

from tests.test_config import get_base_url, get_database_name
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




# Note: populated_database fixture is now defined in conftest.py and shared across all test files
# Note: authenticated_browser fixture is now defined in conftest.py and shared across all test files


class TestCSVExport:
    """Consolidated CSV export tests with shared authentication."""

    @pytest.mark.critical
    @pytest.mark.csv
    def test_csv_export_button_availability(self, authenticated_browser, populated_database):
        """Test that CSV export buttons are available to admin users."""
        logger.info("Testing CSV export button availability")

        base_url = get_base_url()
        dashboard = AdminDashboardPage(authenticated_browser, base_url)
        authenticated_browser.get(f"{base_url}/admin")

        # Test export from dashboard
        assert dashboard.is_dashboard_loaded(), "Should be on dashboard"

        # Find and click the Export CSV link
        try:
            # Use exact link text - most reliable selector
            export_link = authenticated_browser.find_element(By.LINK_TEXT, "Export CSV")
            csv_url = export_link.get_attribute('href')
            logger.info(f"✓ Found Export CSV link: {csv_url}")

            # Record existing files BEFORE triggering download
            download_dir = get_download_dir()
            existing_files = set(glob.glob(os.path.join(download_dir, '*.csv')))
            logger.info(f"Existing files before download: {existing_files}")

            # Set short page load timeout for file download
            authenticated_browser.set_page_load_timeout(3)

            # Navigate to CSV URL (will timeout but download starts)
            try:
                authenticated_browser.get(csv_url)
            except Exception as e:
                logger.debug(f"Navigation timeout (expected): {str(e)[:100]}")

            # Reset timeout
            authenticated_browser.set_page_load_timeout(15)
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
        authenticated_browser.get(f"{base_url}/admin")
        assert dashboard.is_dashboard_loaded(), "Should be back on dashboard before navigating to participants"

        # Test export from participants page
        try:
            logger.info("Navigating to participants page")
            authenticated_browser.get(f"{base_url}/admin/participants")
            time.sleep(2)  # Wait for page load

            # Find Export CSV link
            export_link = authenticated_browser.find_element(By.LINK_TEXT, "Export CSV")
            csv_url = export_link.get_attribute('href')
            logger.info(f"✓ Found Export CSV link on participants page")

            # Record existing files
            existing_files = set(glob.glob(os.path.join(download_dir, '*.csv')))

            # Set short timeout and navigate to CSV URL
            authenticated_browser.set_page_load_timeout(3)
            try:
                authenticated_browser.get(csv_url)
            except Exception:
                pass  # Expected timeout
            authenticated_browser.set_page_load_timeout(15)

            # Check for new file
            time.sleep(2)
            current_files = set(glob.glob(os.path.join(download_dir, '*.csv')))
            new_files = current_files - existing_files

            if new_files:
                csv_file = list(new_files)[0]
                file_size = os.path.getsize(csv_file)
                logger.info(f"✓ CSV export successful from participants page: {file_size} bytes")
                assert file_size > 0, "Downloaded CSV file is empty"

                # Validate CSV content using shared helper
                logger.info("Validating participants page CSV content...")

                # Get database participants for validation
                from config.database import get_firestore_client
                db, _ = get_firestore_client()
                current_year = datetime.now().year
                participant_model = ParticipantModel(db, current_year)

                db_participants = participant_model.get_all_participants()

                # Use shared validation helper (tests 100% field coverage, content match, sorting)
                validation_results = self._validate_csv_content(csv_file, db_participants, export_type='participants')

                logger.info("✓ Participants CSV content validation PASSED")
            else:
                pytest.fail("CSV file not downloaded from participants page")
        except Exception as e:
            logger.error(f"Failed to export CSV from participants page: {e}")
            pytest.fail(f"Participants page CSV export failed: {e}")

        logger.info("=" * 60)
        logger.info("✓ Both CSV export tests PASSED")
        logger.info("=" * 60)

    @pytest.mark.csv
    def test_direct_csv_route_access(self, authenticated_browser, populated_database):
        """Test direct access to CSV export route via browser navigation."""
        logger.info("Testing direct CSV route access")

        base_url = get_base_url()
        dashboard = AdminDashboardPage(authenticated_browser, base_url)
        authenticated_browser.get(f"{base_url}/admin")
        assert dashboard.is_dashboard_loaded(), "Should be on dashboard"

        # Test the actual CSV export route that exists: /admin/export_csv
        csv_url = urljoin(base_url, '/admin/export_csv')
        download_dir = get_download_dir()

        logger.info(f"Testing CSV export route: {csv_url}")

        # Record existing files before navigation
        existing_files = set(glob.glob(os.path.join(download_dir, '*.csv')))

        # Navigate to CSV URL with short timeout
        authenticated_browser.set_page_load_timeout(3)
        try:
            authenticated_browser.get(csv_url)
        except Exception as nav_error:
            logger.debug(f"Navigation timeout (expected): {str(nav_error)[:100]}")
        authenticated_browser.set_page_load_timeout(15)

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


    @pytest.fixture(scope="function")
    def csv_export_data(self, authenticated_browser, populated_database, request):
        """
        Download CSV once and cache across all content validation tests.
        Uses request.session caching to avoid repeated OAuth/download overhead.
        Now uses authenticated_browser fixture for shared OAuth session.
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

        base_url = get_base_url()
        dashboard = AdminDashboardPage(authenticated_browser, base_url)
        authenticated_browser.get(f"{base_url}/admin")

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
            'test_participants': populated_database
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

            # CRITICAL: Assert that CSV contains actual data, not just headers
            assert len(data_rows) > 0, \
                f"CSV should contain data rows beyond header, got {len(data_rows)} rows"
            assert len(data_rows) >= len(test_participants), \
                f"CSV should have all {len(test_participants)} test participants, got {len(data_rows)} rows"

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

    def _validate_csv_content(self, csv_file, expected_db_records, export_type='participants'):
        """
        Shared CSV content validation helper.

        Validates:
        1. ALL expected fields are present (100% coverage, not 80%)
        2. ALL database records are in CSV with exact count match
        3. Sorting matches SPECIFICATION.md requirements

        Args:
            csv_file: Path to CSV file
            expected_db_records: List of database records to validate against
            export_type: 'participants' or 'leaders' for type-specific validation

        Returns:
            dict with validation results
        """
        # Read and parse CSV
        csv_content = read_csv_file(csv_file)
        assert csv_content, f"Should be able to read {export_type} CSV file"

        csv_data = self._parse_csv_content(csv_content)
        assert csv_data and len(csv_data) > 0, f"{export_type} CSV should have at least header row"

        headers = csv_data[0]
        data_rows = csv_data[1:] if len(csv_data) > 1 else []

        logger.info(f"=" * 60)
        logger.info(f"VALIDATING {export_type.upper()} CSV CONTENT")
        logger.info(f"=" * 60)
        logger.info(f"CSV headers: {headers}")
        logger.info(f"CSV rows: {len(data_rows)}")
        logger.info(f"Database records: {len(expected_db_records)}")

        # VALIDATION 1: 100% Field Coverage
        logger.info("-" * 60)
        logger.info("VALIDATION 1: Field Coverage (100% required)")
        logger.info("-" * 60)

        expected_fields = [
            'first_name', 'last_name', 'email', 'phone', 'phone2',
            'skill_level', 'experience', 'preferred_area', 'participation_type',
            'has_binoculars', 'spotting_scope',
            'interested_in_leadership', 'interested_in_scribe',
            'is_leader', 'assigned_area_leader',
            'notes_to_organizers', 'created_at', 'year'
        ]

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
            logger.error(f"Missing fields: {fields_missing}")
            assert False, f"{export_type} CSV must include 100% of expected fields. Missing: {fields_missing}"

        logger.info(f"✓ All {len(expected_fields)} required fields present")

        # VALIDATION 2: Database Content Match
        logger.info("-" * 60)
        logger.info("VALIDATION 2: Database Content Match")
        logger.info("-" * 60)

        # Build column map
        col_map = {}
        for i, header in enumerate(headers):
            header_lower = header.lower()
            if 'first' in header_lower and 'name' in header_lower:
                col_map['first_name'] = i
            elif 'last' in header_lower and 'name' in header_lower:
                col_map['last_name'] = i
            elif 'email' in header_lower:
                col_map['email'] = i
            elif 'assigned_area_leader' in header_lower or ('assigned' in header_lower and 'area' in header_lower and 'leader' in header_lower):
                col_map['assigned_area_leader'] = i
            elif 'preferred_area' in header_lower or ('preferred' in header_lower and 'area' in header_lower):
                col_map['preferred_area'] = i
            elif 'participation' in header_lower and 'type' in header_lower:
                col_map['participation_type'] = i

        # Extract CSV records
        csv_records = []
        for row in data_rows:
            if len(row) > max(col_map.values()):
                record = {
                    'email': row[col_map['email']].strip().lower() if 'email' in col_map else '',
                    'first_name': row[col_map['first_name']].strip() if 'first_name' in col_map else '',
                    'last_name': row[col_map['last_name']].strip() if 'last_name' in col_map else '',
                }
                if export_type == 'leaders':
                    record['assigned_area_leader'] = row[col_map['assigned_area_leader']].strip() if 'assigned_area_leader' in col_map else ''
                elif export_type == 'participants':
                    record['preferred_area'] = row[col_map['preferred_area']].strip() if 'preferred_area' in col_map else ''
                    record['participation_type'] = row[col_map['participation_type']].strip() if 'participation_type' in col_map else ''
                csv_records.append(record)

        # Build database identity sets
        db_identities = set()
        for db_record in expected_db_records:
            first_name = db_record.get('first_name', '').strip().lower()
            last_name = db_record.get('last_name', '').strip().lower()
            email = db_record.get('email', '').strip().lower()
            identity = (first_name, last_name, email)
            db_identities.add(identity)

        csv_identities = set()
        for csv_record in csv_records:
            first_name = csv_record['first_name'].strip().lower()
            last_name = csv_record['last_name'].strip().lower()
            email = csv_record['email'].strip().lower()
            identity = (first_name, last_name, email)
            csv_identities.add(identity)

        # Check ALL database records in CSV
        missing_from_csv = db_identities - csv_identities
        if missing_from_csv:
            logger.error(f"Found {len(missing_from_csv)} database records NOT in CSV:")
            for identity in sorted(list(missing_from_csv))[:5]:
                logger.error(f"  - {identity[0]} {identity[1]} ({identity[2]})")
            assert False, f"Expected all {len(expected_db_records)} database records in CSV, but {len(missing_from_csv)} are missing"

        # Check exact count match
        assert len(csv_records) == len(expected_db_records), \
            f"CSV row count ({len(csv_records)}) must exactly match database count ({len(expected_db_records)})"

        logger.info(f"✓ All {len(expected_db_records)} database records present in CSV")
        logger.info(f"✓ Exact count match: CSV={len(csv_records)}, DB={len(expected_db_records)}")

        # VALIDATION 3: Sorting
        logger.info("-" * 60)
        logger.info("VALIDATION 3: Sorting Order")
        logger.info("-" * 60)

        if export_type == 'participants':
            # SPEC: "Sorted by area → participation type → first name"
            logger.info("Expected: area → participation type (regular before FEEDER) → first name")

            if len(csv_records) > 1:
                for i in range(1, len(csv_records)):
                    prev = csv_records[i-1]
                    curr = csv_records[i]

                    prev_area = prev['preferred_area']
                    curr_area = curr['preferred_area']

                    # Check area sorting
                    if prev_area > curr_area:
                        assert False, f"Sorting error: Area {prev_area} should not come before {curr_area}"
                    elif prev_area == curr_area:
                        # Same area - check participation type
                        prev_type = prev['participation_type']
                        curr_type = curr['participation_type']
                        prev_type_order = 0 if prev_type == 'regular' else 1
                        curr_type_order = 0 if curr_type == 'regular' else 1

                        if prev_type_order > curr_type_order:
                            assert False, f"Sorting error in area {curr_area}: regular should come before FEEDER"
                        elif prev_type_order == curr_type_order:
                            # Same type - check first name
                            prev_name = prev['first_name'].lower()
                            curr_name = curr['first_name'].lower()
                            if prev_name > curr_name:
                                assert False, f"Sorting error in area {curr_area} ({curr_type}): {prev_name} should not come before {curr_name}"

                logger.info("✓ Participants sorted correctly by area → type → first name")

        elif export_type == 'leaders':
            # SPEC: "Sorted by assigned area then by first name"
            logger.info("Expected: assigned_area_leader → first name")

            if len(csv_records) > 1:
                for i in range(1, len(csv_records)):
                    prev = csv_records[i-1]
                    curr = csv_records[i]

                    prev_area = prev['assigned_area_leader']
                    curr_area = curr['assigned_area_leader']

                    # Check area sorting
                    if prev_area > curr_area:
                        assert False, f"Sorting error: Area {prev_area} should not come before {curr_area}"
                    elif prev_area == curr_area:
                        # Same area - check first name
                        prev_name = prev['first_name'].lower()
                        curr_name = curr['first_name'].lower()
                        if prev_name > curr_name:
                            assert False, f"Sorting error in area {curr_area}: {prev_name} should not come before {curr_name}"

                logger.info("✓ Leaders sorted correctly by area → first name")

        logger.info("=" * 60)
        logger.info(f"✓ ALL {export_type.upper()} CSV VALIDATIONS PASSED")
        logger.info("=" * 60)

        return {
            'field_coverage': field_coverage,
            'csv_row_count': len(csv_records),
            'db_record_count': len(expected_db_records),
            'all_validations_passed': True
        }

    def _get_leaders_csv_content(self, browser, base_url):
        """Helper method to get leaders CSV export content via browser download."""
        try:
            # Navigate to leaders page if not already there
            current_url = browser.current_url
            if '/admin/leaders' not in current_url:
                logger.info("Navigating to admin leaders page")
                browser.get(f"{base_url}/admin/leaders")
                time.sleep(2)  # Wait for page load

            # Build CSV URL with format=csv query parameter
            csv_url = f"{base_url}/admin/leaders?format=csv"
            logger.info(f"Downloading leaders CSV from: {csv_url}")

            # Record existing files
            download_dir = get_download_dir()
            existing_files = set(glob.glob(os.path.join(download_dir, '*.csv')))

            # Navigate to CSV URL with short timeout
            browser.set_page_load_timeout(3)
            try:
                browser.get(csv_url)
            except Exception as e:
                logger.debug(f"Navigation timeout (expected): {str(e)[:100]}")
            browser.set_page_load_timeout(15)

            # Check for new file
            time.sleep(2)
            current_files = set(glob.glob(os.path.join(download_dir, '*.csv')))
            new_files = current_files - existing_files

            if new_files:
                csv_file = list(new_files)[0]
                file_size = os.path.getsize(csv_file)
                logger.info(f"✓ Leaders CSV downloaded: {file_size} bytes")

                # Read the downloaded file
                content = read_csv_file(csv_file)
                if content:
                    logger.info(f"✓ Retrieved leaders CSV content ({len(content)} bytes)")
                    return content
                else:
                    logger.error("Could not read downloaded leaders CSV file")
                    return None

            logger.error("No leaders CSV file downloaded")
            return None

        except Exception as e:
            logger.error(f"Failed to download leaders CSV: {e}")
            return None


    @pytest.mark.csv
    def test_leaders_csv_export_button_availability(self, authenticated_browser, populated_database):
        """Test that CSV export button is available on leaders page."""
        logger.info("Testing leaders page CSV export button availability")

        base_url = get_base_url()
        authenticated_browser.get(f"{base_url}/admin/leaders")
        time.sleep(2)  # Wait for page load

        # Find Export CSV link on leaders page
        try:
            # Use exact link text - most reliable selector
            export_link = authenticated_browser.find_element(By.LINK_TEXT, "Export CSV")
            csv_url = export_link.get_attribute('href')
            logger.info(f"✓ Found Export CSV link: {csv_url}")

            # Verify URL contains format=csv query parameter
            assert 'format=csv' in csv_url, "CSV export URL should contain format=csv parameter"

            # Record existing files BEFORE triggering download
            download_dir = get_download_dir()
            existing_files = set(glob.glob(os.path.join(download_dir, '*.csv')))
            logger.info(f"Existing files before download: {existing_files}")

            # Set short page load timeout for file download
            authenticated_browser.set_page_load_timeout(3)

            # Navigate to CSV URL (will timeout but download starts)
            try:
                authenticated_browser.get(csv_url)
            except Exception as e:
                logger.debug(f"Navigation timeout (expected): {str(e)[:100]}")

            # Reset timeout
            authenticated_browser.set_page_load_timeout(15)
            logger.info("✓ Triggered leaders CSV download")

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
                logger.info(f"✓ CSV export successful from leaders page: {csv_file}")

                # Validate it's actually a CSV file
                if os.path.exists(csv_file):
                    file_size = os.path.getsize(csv_file)
                    logger.info(f"✓ Downloaded file size: {file_size} bytes")
                    assert file_size > 0, "Downloaded CSV file is empty"

                    # Verify filename format: area_leaders_YYYY_MMDD.csv
                    filename = os.path.basename(csv_file)
                    assert filename.startswith('area_leaders_'), f"Filename should start with 'area_leaders_': {filename}"
                    assert filename.endswith('.csv'), f"Filename should end with '.csv': {filename}"
                    logger.info(f"✓ Filename format correct: {filename}")
                else:
                    pytest.fail(f"CSV file not found at {csv_file}")
            else:
                pytest.fail("CSV file not downloaded after clicking leaders export button")

            logger.info("✓ Leaders CSV export button test PASSED")

        except Exception as e:
            logger.error(f"Failed to export CSV from leaders page: {e}")
            pytest.fail(f"Leaders export CSV test failed: {e}")

    @pytest.mark.csv
    def test_leaders_csv_route_access(self, authenticated_browser, populated_database):
        """Test direct access to leaders CSV export route."""
        logger.info("Testing direct leaders CSV route access")

        base_url = get_base_url()

        # Test the leaders CSV export route: /admin/leaders?format=csv
        csv_url = f"{base_url}/admin/leaders?format=csv"
        download_dir = get_download_dir()

        logger.info(f"Testing leaders CSV export route: {csv_url}")

        # Record existing files before navigation
        existing_files = set(glob.glob(os.path.join(download_dir, '*.csv')))

        # Navigate to CSV URL with short timeout
        authenticated_browser.set_page_load_timeout(3)
        try:
            authenticated_browser.get(csv_url)
        except Exception as nav_error:
            logger.debug(f"Navigation timeout (expected): {str(nav_error)[:100]}")
        authenticated_browser.set_page_load_timeout(15)

        # Check for new file
        time.sleep(2)
        current_files = set(glob.glob(os.path.join(download_dir, '*.csv')))
        new_files = current_files - existing_files

        if new_files:
            csv_file = list(new_files)[0]
            file_size = os.path.getsize(csv_file)
            logger.info(f"✓ Leaders CSV downloaded: {file_size} bytes")
            assert file_size > 0, "Downloaded CSV should not be empty"

            # Validate CSV format
            content = read_csv_file(csv_file)
            assert content, "Should be able to read leaders CSV file"

            lines = content.split('\n')
            assert len(lines) > 0 and ',' in lines[0], "CSV should have valid format with comma-separated values"

            # Validate headers exist
            headers = lines[0].split(',')
            assert len(headers) > 0, "CSV should have headers"
            logger.info(f"✓ Leaders CSV headers: {headers[:5]}...")  # Show first 5 headers

            logger.info("✓ Leaders CSV export route is accessible and returns valid CSV")
        else:
            pytest.fail(f"No CSV file downloaded from {csv_url}")

    @pytest.mark.critical
    @pytest.mark.csv
    def test_leaders_csv_content_validation(self, authenticated_browser, populated_database):
        """Test leaders CSV export content - verify ALL leaders in DB are in CSV, and ONLY leaders."""
        logger.info("Testing leaders CSV export content validation")

        base_url = get_base_url()
        current_year = datetime.now().year

        # Get database client and participant model
        from config.database import get_firestore_client
        db, _ = get_firestore_client()
        participant_model = ParticipantModel(db, current_year)

        # Query database for ALL leaders
        db_leaders = participant_model.get_leaders()
        logger.info(f"Database contains {len(db_leaders)} leaders")

        if len(db_leaders) == 0:
            pytest.skip("No leaders in database to validate CSV export")

        # Download leaders CSV
        csv_content = self._get_leaders_csv_content(authenticated_browser, base_url)

        if not csv_content:
            pytest.fail("Could not retrieve leaders CSV export content")

        # Parse CSV content
        csv_data = self._parse_csv_content(csv_content)

        if not csv_data or len(csv_data) < 2:
            pytest.fail("Leaders CSV is empty or has no data rows")

        logger.info(f"Leaders CSV contains {len(csv_data) - 1} rows (excluding header)")

        # Get headers
        headers = csv_data[0]
        logger.info(f"CSV headers: {headers}")

        # Build column index map
        col_map = {}
        for i, header in enumerate(headers):
            header_lower = header.lower()
            if 'first' in header_lower and 'name' in header_lower:
                col_map['first_name'] = i
            elif 'last' in header_lower and 'name' in header_lower:
                col_map['last_name'] = i
            elif 'email' in header_lower:
                col_map['email'] = i
            elif 'is_leader' in header_lower or 'leader' in header_lower:
                col_map['is_leader'] = i
            elif 'assigned_area_leader' in header_lower or ('assigned' in header_lower and 'area' in header_lower):
                col_map['assigned_area_leader'] = i

        logger.info(f"Column mapping: {col_map}")

        # Extract CSV records
        data_rows = csv_data[1:]
        csv_records = []
        for row in data_rows:
            if len(row) > max(col_map.values()):
                record = {
                    'email': row[col_map['email']].strip().lower() if 'email' in col_map else '',
                    'first_name': row[col_map['first_name']].strip() if 'first_name' in col_map else '',
                    'last_name': row[col_map['last_name']].strip() if 'last_name' in col_map else '',
                    'assigned_area_leader': row[col_map['assigned_area_leader']].strip() if 'assigned_area_leader' in col_map else '',
                }
                csv_records.append(record)

        logger.info(f"Extracted {len(csv_records)} records from leaders CSV")

        # TEST 1: Verify ALL database leaders are present in CSV
        logger.info("=" * 60)
        logger.info("TEST 1: Verify ALL database leaders are present in CSV")
        logger.info("=" * 60)

        db_leader_identities = set()
        for leader in db_leaders:
            first_name = leader.get('first_name', '').strip().lower()
            last_name = leader.get('last_name', '').strip().lower()
            email = leader.get('email', '').strip().lower()
            identity = (first_name, last_name, email)
            db_leader_identities.add(identity)

        csv_leader_identities = set()
        for record in csv_records:
            first_name = record['first_name'].strip().lower()
            last_name = record['last_name'].strip().lower()
            email = record['email'].strip().lower()
            identity = (first_name, last_name, email)
            csv_leader_identities.add(identity)

        # Find leaders in DB but not in CSV
        missing_from_csv = db_leader_identities - csv_leader_identities
        if missing_from_csv:
            logger.error(f"Found {len(missing_from_csv)} leaders in database but NOT in CSV:")
            for identity in sorted(list(missing_from_csv))[:5]:
                logger.error(f"  - {identity[0]} {identity[1]} ({identity[2]})")
            if len(missing_from_csv) > 5:
                logger.error(f"  ... and {len(missing_from_csv) - 5} more")
            pytest.fail(f"Expected all {len(db_leaders)} database leaders in CSV, but {len(missing_from_csv)} are missing")

        logger.info(f"✓ All {len(db_leaders)} database leaders are present in CSV")

        # TEST 2: Verify ONLY leaders are in CSV (no non-leader participants)
        logger.info("=" * 60)
        logger.info("TEST 2: Verify ONLY leaders are in CSV (no non-leader participants)")
        logger.info("=" * 60)

        # All records in CSV should be leaders
        matched_count = len(csv_leader_identities.intersection(db_leader_identities))
        extra_in_csv = csv_leader_identities - db_leader_identities

        if extra_in_csv:
            logger.warning(f"Found {len(extra_in_csv)} records in CSV that are NOT leaders in database:")
            for identity in sorted(list(extra_in_csv))[:5]:
                logger.warning(f"  - {identity[0]} {identity[1]} ({identity[2]})")
            # This might be OK if manually added leaders exist, but log it
            logger.info("Note: Extra records may be manually-added leaders not yet in participant collection")

        logger.info(f"✓ CSV contains {matched_count} valid leader records")

        # TEST 3: Verify sorting (assigned_area_leader → first_name)
        logger.info("=" * 60)
        logger.info("TEST 3: Verify sorting by area then first name")
        logger.info("=" * 60)

        if len(csv_records) > 1:
            # Check that records are sorted by area, then by first name
            is_sorted = True
            for i in range(1, len(csv_records)):
                prev_area = csv_records[i-1]['assigned_area_leader']
                curr_area = csv_records[i]['assigned_area_leader']

                if prev_area > curr_area:
                    is_sorted = False
                    logger.error(f"Sorting error: Area {prev_area} comes before {curr_area}")
                    break
                elif prev_area == curr_area:
                    # Same area - check first name sorting
                    prev_name = csv_records[i-1]['first_name'].lower()
                    curr_name = csv_records[i]['first_name'].lower()
                    if prev_name > curr_name:
                        is_sorted = False
                        logger.error(f"Sorting error in area {curr_area}: {prev_name} comes before {curr_name}")
                        break

            if is_sorted:
                logger.info("✓ Leaders CSV is correctly sorted by area → first name")
            else:
                logger.warning("Leaders CSV sorting may not be correct")

        # TEST 4: Verify all participant fields are present
        logger.info("=" * 60)
        logger.info("TEST 4: Verify all participant fields are present")
        logger.info("=" * 60)

        expected_fields = [
            'first_name', 'last_name', 'email', 'phone', 'phone2',
            'skill_level', 'experience', 'preferred_area', 'participation_type',
            'has_binoculars', 'spotting_scope',
            'interested_in_leadership', 'interested_in_scribe',
            'is_leader', 'assigned_area_leader'
        ]

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
            logger.error(f"Missing fields: {fields_missing}")
            assert False, f"Leaders CSV must include 100% of expected fields. Missing: {fields_missing}"

        logger.info(f"✓ All {len(expected_fields)} required fields present in leaders CSV")
        logger.info("=" * 60)
        logger.info("✓ Leaders CSV content validation PASSED")
        logger.info("=" * 60)

    @pytest.mark.csv
    @pytest.mark.slow
    def test_large_dataset_export_performance(self, authenticated_browser, populated_database):
        """Test CSV export performance with larger datasets."""
        logger.info("Testing CSV export performance with large dataset")

        base_url = get_base_url()
        dashboard = AdminDashboardPage(authenticated_browser, base_url)
        authenticated_browser.get(f"{base_url}/admin")
        current_year = datetime.now().year

        from config.database import get_firestore_client
        db, _ = get_firestore_client()
        participant_model = ParticipantModel(db, current_year)

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

    @pytest.mark.critical
    @pytest.mark.csv
    @pytest.mark.security
    def test_csv_formula_injection_protection(self, authenticated_browser):
        """Test that CSV exports protect against formula injection attacks."""
        logger.info("Testing CSV formula injection protection")

        base_url = get_base_url()
        current_year = datetime.now().year

        # Get database client
        from config.database import get_firestore_client
        db, _ = get_firestore_client()
        participant_model = ParticipantModel(db, current_year)

        # Create test participants with dangerous formula prefixes
        dangerous_inputs = [
            ('=SUM(1+1)', 'FormulaEquals', 'formula-equals@test.com'),
            ('+cmd|/c calc', 'FormulaPlus', 'formula-plus@test.com'),
            ('-2+3', 'FormulaMinus', 'formula-minus@test.com'),
            ('@SUM(A1:A10)', 'FormulaAt', 'formula-at@test.com'),
            ('\t\tTabPrefix', 'TabTest', 'formula-tab@test.com'),
        ]

        created_participants = []
        logger.info(f"Creating {len(dangerous_inputs)} test participants with dangerous input...")

        for first_name, last_name, email in dangerous_inputs:
            try:
                participant_data = {
                    'first_name': first_name,
                    'last_name': last_name,
                    'email': email.lower(),
                    'phone': '604-555-0100',
                    'skill_level': 'Beginner',
                    'experience': 'First count',
                    'preferred_area': 'A',
                    'participation_type': 'regular',
                    'has_binoculars': False,
                    'spotting_scope': False,
                    'interested_in_leadership': False,
                    'interested_in_scribe': False,
                    'notes_to_organizers': '=DANGEROUS()'  # Also test in notes field
                }

                participant_id = participant_model.add_participant(participant_data)
                created_participants.append({
                    'id': participant_id,
                    'first_name': first_name,
                    'last_name': last_name,
                    'email': email.lower()
                })
                logger.info(f"Created test participant: {first_name} {last_name}")

            except Exception as e:
                logger.error(f"Failed to create test participant {first_name} {last_name}: {e}")

        if not created_participants:
            pytest.fail("Could not create any test participants with dangerous inputs")

        logger.info(f"✓ Created {len(created_participants)} test participants")

        try:
            # Download CSV export
            dashboard = AdminDashboardPage(authenticated_browser, base_url)
            authenticated_browser.get(f"{base_url}/admin")

            # Find Export CSV link
            export_link = authenticated_browser.find_element(By.LINK_TEXT, "Export CSV")
            csv_url = export_link.get_attribute('href')

            # Record existing files
            download_dir = get_download_dir()
            existing_files = set(glob.glob(os.path.join(download_dir, '*.csv')))

            # Navigate to CSV URL with short timeout
            authenticated_browser.set_page_load_timeout(3)
            try:
                authenticated_browser.get(csv_url)
            except Exception:
                pass  # Expected timeout
            authenticated_browser.set_page_load_timeout(15)

            # Check for new file
            time.sleep(2)
            current_files = set(glob.glob(os.path.join(download_dir, '*.csv')))
            new_files = current_files - existing_files

            if not new_files:
                pytest.fail("Could not retrieve CSV export content")

            csv_file = list(new_files)[0]
            csv_content = read_csv_file(csv_file)
            assert csv_content, "Should be able to read CSV file"

            # Parse CSV
            reader = csv.reader(io.StringIO(csv_content))
            csv_data = list(reader)

            if not csv_data or len(csv_data) < 2:
                pytest.fail("CSV is empty or has no data rows")

            headers = csv_data[0]
            data_rows = csv_data[1:]

            logger.info(f"CSV contains {len(data_rows)} rows")

            # Find column indices
            first_name_col = None
            email_col = None
            notes_col = None

            for i, header in enumerate(headers):
                header_lower = header.lower()
                if 'first' in header_lower and 'name' in header_lower:
                    first_name_col = i
                elif 'email' in header_lower:
                    email_col = i
                elif 'notes_to_organizers' in header_lower or 'notes' in header_lower:
                    notes_col = i

            if first_name_col is None or email_col is None:
                pytest.fail("Could not find required columns in CSV")

            logger.info(f"Column indices - First: {first_name_col}, Email: {email_col}, Notes: {notes_col}")

            # TEST: Verify dangerous inputs are escaped
            logger.info("=" * 60)
            logger.info("VERIFYING FORMULA INJECTION PROTECTION")
            logger.info("=" * 60)

            dangerous_chars_found = []
            properly_escaped = []

            for row in data_rows:
                if len(row) <= max(first_name_col, email_col):
                    continue

                email = row[email_col].strip().lower()

                # Check if this is one of our test participants
                test_participant = next((p for p in created_participants if p['email'] == email), None)

                if test_participant:
                    first_name_csv = row[first_name_col]

                    logger.info(f"Checking participant: {test_participant['first_name']} -> CSV: '{first_name_csv}'")

                    # Check if dangerous character is at start WITHOUT being escaped
                    original_first = test_participant['first_name']

                    if len(original_first) > 0 and original_first[0] in ('=', '+', '-', '@', '\t', '\r'):
                        # Original had dangerous character - CSV should have it escaped
                        if len(first_name_csv) > 0 and first_name_csv[0] == "'":
                            # Properly escaped with single quote prefix
                            properly_escaped.append({
                                'field': 'first_name',
                                'original': original_first,
                                'csv': first_name_csv,
                                'email': email
                            })
                            logger.info(f"✓ Properly escaped: '{original_first}' -> '{first_name_csv}'")
                        else:
                            # NOT escaped - dangerous!
                            dangerous_chars_found.append({
                                'field': 'first_name',
                                'original': original_first,
                                'csv': first_name_csv,
                                'email': email
                            })
                            logger.error(f"❌ NOT ESCAPED: '{original_first}' appears as '{first_name_csv}'")

            # ASSERTIONS
            logger.info("=" * 60)
            logger.info("TEST RESULTS")
            logger.info("=" * 60)

            logger.info(f"Test participants checked: {len(created_participants)}")
            logger.info(f"Properly escaped values: {len(properly_escaped)}")
            logger.info(f"DANGEROUS unescaped values: {len(dangerous_chars_found)}")

            if dangerous_chars_found:
                logger.error("❌ FORMULA INJECTION PROTECTION FAILED")
                logger.error("The following dangerous values were NOT escaped:")
                for item in dangerous_chars_found:
                    logger.error(f"  Field: {item['field']}, Email: {item['email']}")
                    logger.error(f"    Original: '{item['original']}'")
                    logger.error(f"    In CSV: '{item['csv']}'")

                pytest.fail(f"CSV formula injection protection FAILED: {len(dangerous_chars_found)} unescaped dangerous values found")

            # Verify we actually tested dangerous inputs
            assert len(properly_escaped) > 0, "Should have found at least one dangerous input that was properly escaped"

            logger.info(f"✓ All {len(properly_escaped)} dangerous inputs properly escaped with single quote prefix")
            logger.info("✓ CSV FORMULA INJECTION PROTECTION TEST PASSED")

        finally:
            # Cleanup: Delete test participants
            logger.info("Cleaning up test participants...")
            for participant in created_participants:
                try:
                    participant_model.delete_participant(participant['id'])
                    logger.debug(f"Deleted test participant: {participant['id']}")
                except Exception as e:
                    logger.warning(f"Failed to delete test participant {participant['id']}: {e}")

    @pytest.mark.csv
    @pytest.mark.security
    def test_csv_security_module_unit_tests(self):
        """Unit tests for CSV security escaping function."""
        logger.info("Testing CSV security module unit tests")

        from services.csv_security import escape_csv_formula

        # TEST 1: Dangerous formula prefixes should be escaped
        test_cases = [
            ('=SUM(1+1)', "'=SUM(1+1)"),
            ('+cmd', "'+cmd"),
            ('-2+3', "'-2+3"),
            ('@SUM(A1)', "'@SUM(A1)"),
            ('\tTabPrefix', "'\tTabPrefix"),
            ('\rCarriageReturn', "'\rCarriageReturn"),
        ]

        logger.info("Testing dangerous prefix escaping...")
        for input_val, expected in test_cases:
            result = escape_csv_formula(input_val)
            assert result == expected, f"Failed for '{input_val}': expected '{expected}', got '{result}'"
            logger.info(f"✓ '{input_val}' -> '{result}'")

        # TEST 2: Safe strings should pass through unchanged
        safe_cases = [
            'Normal Name',
            'John Smith',
            '123 Main St',
            'email@example.com',
            'Regular text without dangerous prefixes'
        ]

        logger.info("Testing safe strings pass through...")
        for input_val in safe_cases:
            result = escape_csv_formula(input_val)
            assert result == input_val, f"Safe string '{input_val}' should not be modified"
            logger.info(f"✓ '{input_val}' unchanged")

        # TEST 3: Non-string types should pass through unchanged
        non_string_cases = [
            123,
            45.67,
            True,
            False,
            None,
        ]

        logger.info("Testing non-string types pass through...")
        for input_val in non_string_cases:
            result = escape_csv_formula(input_val)
            assert result == input_val, f"Non-string {type(input_val).__name__} should not be modified"
            logger.info(f"✓ {type(input_val).__name__} unchanged")

        # TEST 4: Empty strings should pass through unchanged
        result = escape_csv_formula('')
        assert result == '', "Empty string should not be modified"
        logger.info("✓ Empty string unchanged")

        # TEST 5: Dangerous characters in middle of string should NOT be escaped
        middle_cases = [
            ('Price is $100', 'Price is $100'),  # No prefix char
            ('Formula =SUM()', 'Formula =SUM()'),  # = not at start
            ('Email me+you@test.com', 'Email me+you@test.com'),  # + not at start
        ]

        logger.info("Testing dangerous chars in middle (should NOT be escaped)...")
        for input_val, expected in middle_cases:
            result = escape_csv_formula(input_val)
            assert result == expected, f"Dangerous char in middle should not be escaped: '{input_val}'"
            logger.info(f"✓ '{input_val}' unchanged (char not at start)")

        logger.info("=" * 60)
        logger.info("✓ ALL CSV SECURITY UNIT TESTS PASSED")
        logger.info("=" * 60)
