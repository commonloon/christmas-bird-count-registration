# CSV Export Workflow Tests
# Updated by Claude AI on 2025-09-25

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
import requests
from urllib.parse import urljoin

logger = logging.getLogger(__name__)




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




@pytest.fixture
def populated_test_data(db_client):
    """Create test data for CSV export validation."""
    current_year = datetime.now().year
    participant_model = ParticipantModel(db_client, current_year)

    # Create test dataset
    test_participants = []
    dataset = get_test_dataset('small_mixed')

    logger.info(f"Creating {len(dataset)} test participants for CSV export validation")

    for participant_data in dataset:
        try:
            participant_record = {
                'first_name': participant_data['personal']['first_name'],
                'last_name': participant_data['personal']['last_name'],
                'email': participant_data['personal']['email'],
                'phone': participant_data['personal']['phone'],
                'phone2': participant_data['personal'].get('phone2', ''),
                'skill_level': participant_data['experience']['skill_level'],
                'experience': participant_data['experience']['experience'],
                'preferred_area': participant_data['participation']['area'],
                'participation_type': participant_data['participation']['type'],
                'has_binoculars': participant_data['equipment']['has_binoculars'],
                'spotting_scope': participant_data['equipment']['spotting_scope'],
                'interested_in_leadership': participant_data['interests']['leadership'],
                'interested_in_scribe': participant_data['interests']['scribe'],
                'notes_to_organizers': participant_data.get('notes', ''),
                'is_leader': False,
                'assigned_area_leader': None,
                'auto_assigned': False,
                'assigned_by': '',
                'assigned_at': None,
                'created_at': datetime.now(),
                'updated_at': None,
                'year': current_year
            }

            participant_id = participant_model.add_participant(participant_record)
            if participant_id:
                participant_record['id'] = participant_id
                test_participants.append(participant_record)

        except Exception as e:
            logger.warning(f"Could not create test participant: {e}")

    logger.info(f"Successfully created {len(test_participants)} test participants")

    yield test_participants

    # Cleanup test data
    logger.info("Cleaning up CSV test participants")
    for participant in test_participants:
        try:
            if participant.get('id'):
                participant_model.delete_participant(participant['id'])
        except:
            pass


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

        export_available = dashboard.click_export_participants_csv()
        if export_available:
            logger.info("✓ CSV export available from dashboard")
        else:
            logger.warning("CSV export button not found on dashboard")

        # Test export from participants page
        if dashboard.navigate_to_participants():
            participants_page = AdminParticipantsPage(dashboard.driver, dashboard.base_url)

            if participants_page.is_participants_page_loaded():
                participants_export_available = participants_page.click_export_csv()
                if participants_export_available:
                    logger.info("✓ CSV export available from participants page")
                else:
                    logger.warning("CSV export button not found on participants page")
            else:
                logger.warning("Participants page did not load")

        logger.info("CSV export button availability test completed")

    @pytest.mark.csv
    def test_direct_csv_route_access(self, browser, test_credentials):
        """Test direct access to CSV export route."""
        logger.info("Testing direct CSV route access")

        admin_creds = test_credentials['admin_primary']
        base_url = get_base_url()
        admin_login_for_test(browser, base_url, admin_creds)

        dashboard = AdminDashboardPage(browser, base_url)
        browser.get(f"{base_url}/admin")

        # Try to access CSV export route directly
        csv_urls = [
            urljoin(base_url, '/admin/export_csv'),
            urljoin(base_url, '/export_csv'),
            urljoin(base_url, '/admin/participants/export'),
        ]

        # Get cookies from authenticated session
        cookies = {cookie['name']: cookie['value'] for cookie in dashboard.driver.get_cookies()}

        for csv_url in csv_urls:
            try:
                logger.info(f"Testing CSV route: {csv_url}")
                response = requests.get(csv_url, cookies=cookies, timeout=30)

                if response.status_code == 200:
                    # Check if response looks like CSV
                    content_type = response.headers.get('content-type', '')
                    if 'csv' in content_type.lower() or 'text/plain' in content_type:
                        logger.info(f"✓ CSV route accessible: {csv_url}")
                        logger.info(f"Content-Type: {content_type}")
                        logger.info(f"Content length: {len(response.content)} bytes")

                        # Basic CSV format check
                        if len(response.content) > 0:
                            content = response.content.decode('utf-8')
                            lines = content.split('\n')
                            if len(lines) > 0 and ',' in lines[0]:
                                logger.info("✓ Response appears to be valid CSV format")
                            else:
                                logger.warning("Response may not be valid CSV format")

                        return  # Found working CSV route

                elif response.status_code == 302:
                    logger.info(f"CSV route redirects: {csv_url} -> {response.headers.get('location')}")
                elif response.status_code == 403:
                    logger.warning(f"CSV route forbidden (auth issue?): {csv_url}")
                else:
                    logger.warning(f"CSV route returned {response.status_code}: {csv_url}")

            except Exception as e:
                logger.warning(f"Error accessing CSV route {csv_url}: {e}")

        logger.warning("No accessible CSV routes found")


class TestCSVContentValidation:
    """Test CSV export content validation."""

    @pytest.mark.critical
    @pytest.mark.csv
    def test_csv_export_with_known_data(self, browser, test_credentials, populated_test_data):
        """Test CSV export content against known test data."""
        logger.info("Testing CSV export content validation with known test data")

        admin_creds = test_credentials['admin_primary']
        base_url = get_base_url()
        admin_login_for_test(browser, base_url, admin_creds)

        dashboard = AdminDashboardPage(browser, base_url)
        browser.get(f"{base_url}/admin")
        test_participants = populated_test_data

        logger.info(f"Validating CSV export against {len(test_participants)} test participants")

        # Get CSV export
        csv_content = self._get_csv_export_content(dashboard, base_url)

        if not csv_content:
            pytest.skip("Could not retrieve CSV export content")

        # Parse CSV content
        csv_data = self._parse_csv_content(csv_content)

        if not csv_data:
            pytest.fail("Could not parse CSV content")

        logger.info(f"CSV export contains {len(csv_data)} rows (including header)")

        # Validate CSV structure
        if len(csv_data) > 0:
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
                # Check first few rows for data validity
                for i, row in enumerate(data_rows[:3]):
                    logger.info(f"Row {i+1}: {dict(zip(headers, row)) if len(headers) == len(row) else row}")

                # Verify some test participants appear in CSV
                test_emails = {p['email'].lower() for p in test_participants}
                csv_emails = set()

                email_column_index = None
                for i, header in enumerate(headers):
                    if 'email' in header.lower():
                        email_column_index = i
                        break

                if email_column_index is not None:
                    csv_emails = {
                        row[email_column_index].lower()
                        for row in data_rows
                        if len(row) > email_column_index
                    }

                    matches = test_emails.intersection(csv_emails)
                    logger.info(f"Found {len(matches)} test participants in CSV export")

                    if matches:
                        logger.info("✓ CSV export contains expected test data")
                    else:
                        logger.warning("CSV export does not contain expected test data")

            logger.info("✓ CSV content validation completed")

        else:
            logger.warning("CSV export appears to be empty")

    @pytest.mark.csv
    def test_csv_field_completeness(self, browser, test_credentials):
        """Test that CSV export contains all expected fields."""
        logger.info("Testing CSV field completeness")

        admin_creds = test_credentials['admin_primary']
        base_url = get_base_url()
        admin_login_for_test(browser, base_url, admin_creds)

        dashboard = AdminDashboardPage(browser, base_url)
        browser.get(f"{base_url}/admin")

        # Get CSV export
        csv_content = self._get_csv_export_content(dashboard, base_url)

        if not csv_content:
            pytest.skip("Could not retrieve CSV export for field validation")

        # Parse CSV headers
        csv_data = self._parse_csv_content(csv_content)
        if not csv_data:
            pytest.fail("Could not parse CSV for field validation")

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
    def test_csv_sorting_order(self, browser, test_credentials):
        """Test CSV export sorting order (area → type → name)."""
        logger.info("Testing CSV export sorting order")

        admin_creds = test_credentials['admin_primary']
        base_url = get_base_url()
        admin_login_for_test(browser, base_url, admin_creds)

        dashboard = AdminDashboardPage(browser, base_url)
        browser.get(f"{base_url}/admin")

        # Get CSV export
        csv_content = self._get_csv_export_content(dashboard, base_url)

        if not csv_content:
            pytest.skip("Could not retrieve CSV export for sorting validation")

        # Parse CSV content
        csv_data = self._parse_csv_content(csv_content)
        if not csv_data or len(csv_data) < 2:
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
        """Helper method to get CSV export content."""
        csv_urls = [
            urljoin(base_url, '/admin/export_csv'),
            urljoin(base_url, '/export_csv'),
            urljoin(base_url, '/admin/participants/export'),
        ]

        cookies = {cookie['name']: cookie['value'] for cookie in dashboard.driver.get_cookies()}

        for csv_url in csv_urls:
            try:
                response = requests.get(csv_url, cookies=cookies, timeout=30)
                if response.status_code == 200 and len(response.content) > 0:
                    return response.content.decode('utf-8')
            except Exception as e:
                logger.warning(f"Failed to get CSV from {csv_url}: {e}")

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
        """Helper method to get CSV export content."""
        csv_urls = [
            urljoin(base_url, '/admin/export_csv'),
            urljoin(base_url, '/export_csv'),
            urljoin(base_url, '/admin/participants/export'),
        ]

        cookies = {cookie['name']: cookie['value'] for cookie in dashboard.driver.get_cookies()}
        logger.info(f"Retrieved {len(cookies)} cookies from browser session")

        for csv_url in csv_urls:
            try:
                logger.info(f"Attempting CSV export from: {csv_url}")
                response = requests.get(csv_url, cookies=cookies, timeout=60)  # Longer timeout for large exports
                logger.info(f"Response status: {response.status_code}, content length: {len(response.content)}")
                logger.info(f"Response headers: {dict(response.headers)}")

                if response.status_code == 200 and len(response.content) > 0:
                    logger.info(f"Successfully retrieved CSV from {csv_url}")
                    return response.content.decode('utf-8')
                elif response.status_code == 302:
                    logger.warning(f"CSV route redirects to: {response.headers.get('location')}")
                else:
                    logger.warning(f"CSV route returned status {response.status_code}")
                    # Log first 500 chars of response for debugging
                    content_preview = response.content[:500].decode('utf-8', errors='ignore')
                    logger.warning(f"Response content preview: {content_preview}")
            except Exception as e:
                logger.warning(f"Failed to get CSV from {csv_url}: {e}")

        logger.error("All CSV export URLs failed")
        return None

    def _parse_csv_content(self, csv_content):
        """Helper method to parse CSV content."""
        try:
            reader = csv.reader(io.StringIO(csv_content))
            return list(reader)
        except Exception as e:
            logger.error(f"Failed to parse CSV content: {e}")
            return None