"""
Phase 4: Core Functionality Smoke Tests
Updated by Claude AI on 2025-10-18

These tests validate that basic application workflows function correctly after
deployment. They are smoke tests - not comprehensive, but sufficient to catch
major deployment issues.

All tests are portable - they work with any configuration without hardcoded values.

Requirements:
- Deployed test server accessible
- Browser (Firefox or Chrome)
- Admin credentials in Secret Manager (for admin tests only)

Note: Admin tests skip gracefully if credentials not available.
"""

import pytest
import random
import csv
import io
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException


class TestRegistrationWorkflow:
    """Validate basic participant registration workflow."""

    def test_registration_page_renders(self, browser, installation_config):
        """Verify registration page loads and contains registration form."""
        url = installation_config['test_url']

        browser.get(url)

        try:
            # Wait for form to load
            wait = WebDriverWait(browser, 10)
            form = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'form[action*="register"]'))
            )

            assert form is not None, \
                f"Registration form not found on {url}\n" \
                f"Check that routes/main.py has registration route"

            # Verify key form fields exist
            required_fields = ['first_name', 'last_name', 'email', 'preferred_area', 'skill_level']
            for field_name in required_fields:
                field = browser.find_element(By.NAME, field_name)
                assert field is not None, \
                    f"Required field '{field_name}' not found in registration form\n" \
                    f"Check templates/index.html"

        except TimeoutException:
            pytest.fail(
                f"Registration page failed to load within 10 seconds: {url}\n"
                f"Check deployment: ./deploy.sh test\n"
                f"Check service logs: gcloud run services logs tail {installation_config['test_service']} "
                f"--region={installation_config['gcp_location']}"
            )

    def test_map_renders_on_registration_page(self, browser, installation_config):
        """Verify Leaflet map renders on registration page."""
        url = installation_config['test_url']

        browser.get(url)

        try:
            wait = WebDriverWait(browser, 10)

            # Wait for map container
            map_container = wait.until(
                EC.presence_of_element_located((By.ID, 'count-area-map'))
            )

            assert map_container is not None, \
                "Map container div not found\n" \
                "Check templates/index.html for #count-area-map"

            # Verify Leaflet loaded by checking for Leaflet classes
            # Leaflet adds classes to the map div when it initializes
            wait.until(
                lambda driver: 'leaflet' in map_container.get_attribute('class').lower() or
                              len(driver.find_elements(By.CSS_SELECTOR, '.leaflet-container')) > 0
            )

            # Check that map has actually rendered (has child elements)
            leaflet_elements = browser.find_elements(By.CSS_SELECTOR, '.leaflet-container, .leaflet-map-pane')
            assert len(leaflet_elements) > 0, \
                "Leaflet map did not initialize\n" \
                "Check static/js/map.js loads correctly\n" \
                "Check browser console for JavaScript errors"

        except TimeoutException:
            pytest.fail(
                "Map failed to render within 10 seconds\n"
                "Possible causes:\n"
                "- static/js/map.js not loading\n"
                "- static/data/area_boundaries.json not accessible\n"
                "- JavaScript error preventing map initialization\n"
                "Check browser console and network tab"
            )

    def test_area_dropdown_populated_from_config(self, browser, installation_config):
        """Verify area dropdown contains all public areas from configuration."""
        url = installation_config['test_url']
        expected_areas = set(installation_config['public_areas'])

        browser.get(url)

        try:
            wait = WebDriverWait(browser, 10)
            area_select = wait.until(
                EC.presence_of_element_located((By.NAME, 'preferred_area'))
            )

            select = Select(area_select)
            options = select.options

            # Get area codes from dropdown (exclude empty and UNASSIGNED)
            dropdown_areas = {
                opt.get_attribute('value')
                for opt in options
                if opt.get_attribute('value') and opt.get_attribute('value') != 'UNASSIGNED'
            }

            missing = expected_areas - dropdown_areas

            assert not missing, \
                f"Public areas missing from dropdown:\n" \
                f"Expected (from config/areas.py): {sorted(expected_areas)}\n" \
                f"Got from dropdown: {sorted(dropdown_areas)}\n" \
                f"Missing: {sorted(missing)}\n" \
                f"Check routes/main.py passes public_areas to template"

        except TimeoutException:
            pytest.fail("Area dropdown not found or did not load in time")


class TestAdminAccess:
    """Validate admin authentication and dashboard access."""

    def test_admin_login_redirects_when_not_authenticated(self, browser, installation_config):
        """Verify /admin redirects to login when not authenticated."""
        url = f"{installation_config['test_url']}/admin"

        browser.get(url)

        # Give it time to redirect
        try:
            wait = WebDriverWait(browser, 5)
            # Should redirect to auth/login or Google OAuth
            wait.until(lambda driver: 'login' in driver.current_url.lower() or
                                     'accounts.google.com' in driver.current_url.lower())

            assert 'admin' not in browser.current_url or 'login' in browser.current_url.lower(), \
                "Admin page should redirect to login for unauthenticated users\n" \
                "Check routes/admin.py has @require_admin decorator"

        except TimeoutException:
            # Check if we're still on admin page (bad - should have redirected)
            if '/admin' in browser.current_url and 'login' not in browser.current_url.lower():
                pytest.fail(
                    "Admin page did not redirect to login\n"
                    "Unauthenticated users should not access /admin\n"
                    "Check routes/admin.py @require_admin decorator"
                )

    def test_admin_dashboard_loads_with_authentication(self, authenticated_browser, installation_config):
        """Verify admin dashboard loads after authentication."""
        url = f"{installation_config['test_url']}/admin"

        # Browser is already authenticated via authenticated_browser fixture
        authenticated_browser.get(url)

        try:
            wait = WebDriverWait(authenticated_browser, 10)

            # Wait for dashboard to load
            wait.until(EC.presence_of_element_located((By.TAG_NAME, 'h1')))

            # Verify we're on admin dashboard (not redirected to login)
            assert 'admin' in authenticated_browser.current_url.lower(), \
                f"Not on admin page. Current URL: {authenticated_browser.current_url}\n" \
                "Admin authentication may have failed"

            assert 'login' not in authenticated_browser.current_url.lower(), \
                "Redirected to login despite authentication\n" \
                "Check OAuth flow and admin permissions"

            # Verify dashboard content
            page_text = authenticated_browser.page_source
            org_name = installation_config['org_vars']['organization_name']

            assert org_name in page_text or 'Admin Dashboard' in page_text, \
                "Admin dashboard content not found\n" \
                "Page may have loaded but content is missing"

        except TimeoutException:
            pytest.fail(
                f"Admin dashboard did not load: {url}\n"
                f"Current URL: {authenticated_browser.current_url}\n"
                "Check routes/admin.py and templates/admin/dashboard.html"
            )


class TestCSVExport:
    """Validate CSV export functionality."""

    def test_csv_export_button_exists_and_downloads(self, authenticated_browser, installation_config):
        """Verify CSV export button exists in admin UI and triggers valid CSV download."""
        import os
        import time
        import glob

        # Get download directory (configured in tests/conftest.py for authenticated_browser)
        # The authenticated_browser fixture uses browser options from parent conftest
        test_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        download_dir = os.path.join(test_dir, 'tmp', 'downloads')
        os.makedirs(download_dir, exist_ok=True)

        # Clean up any existing CSV files
        existing_csvs = glob.glob(os.path.join(download_dir, '*.csv'))
        for csv_file in existing_csvs:
            try:
                os.remove(csv_file)
            except Exception:
                pass

        # Navigate to admin page
        admin_url = f"{installation_config['test_url']}/admin"
        authenticated_browser.get(admin_url)

        try:
            wait = WebDriverWait(authenticated_browser, 10)

            # Find CSV export link using LINK_TEXT (most reliable)
            try:
                export_link = wait.until(
                    EC.presence_of_element_located((By.LINK_TEXT, 'Export CSV'))
                )
            except TimeoutException:
                # Try partial link text as fallback
                try:
                    export_link = wait.until(
                        EC.presence_of_element_located((By.PARTIAL_LINK_TEXT, 'Export'))
                    )
                except TimeoutException:
                    pytest.fail(
                        "CSV export button/link not found in admin interface\n"
                        "Expected link text: 'Export CSV'\n"
                        "Check templates/admin/dashboard.html or templates/admin/participants.html"
                    )

            # Get the export URL
            csv_url = export_link.get_attribute('href')

            assert csv_url and 'export_csv' in csv_url, \
                f"Export link doesn't point to CSV export endpoint\n" \
                f"Link href: {csv_url}\n" \
                "Check that export button links to /admin/export_csv"

            # Record existing files BEFORE triggering download
            existing_files = set(glob.glob(os.path.join(download_dir, '*.csv')))

            # Set short page load timeout for file download (will timeout but download starts)
            authenticated_browser.set_page_load_timeout(3)

            # Navigate to CSV URL - this triggers download and will timeout
            try:
                authenticated_browser.get(csv_url)
            except Exception:
                # Timeout expected - download is triggered
                pass

            # Reset timeout
            authenticated_browser.set_page_load_timeout(15)

            # Wait for download to complete
            time.sleep(3)
            current_files = set(glob.glob(os.path.join(download_dir, '*.csv')))
            new_files = current_files - existing_files

            assert new_files, \
                f"CSV file not downloaded to {download_dir}\n" \
                f"Existing files: {existing_files}\n" \
                f"Current files: {current_files}\n" \
                "Download may have failed or saved to different location"

            # Get the downloaded file
            csv_file = list(new_files)[0]

            # Verify file exists and has content
            assert os.path.exists(csv_file), f"CSV file not found: {csv_file}"

            file_size = os.path.getsize(csv_file)
            assert file_size > 0, "Downloaded CSV file is empty"

            # Read and validate CSV content
            with open(csv_file, 'r', encoding='utf-8') as f:
                csv_content = f.read()

            csv_lines = csv_content.strip().split('\n')
            assert len(csv_lines) > 0, "CSV has no lines"

            # Verify CSV header (uses snake_case field names)
            header = csv_lines[0]
            required_headers = ['first_name', 'last_name', 'email', 'preferred_area']

            for required_header in required_headers:
                assert required_header in header, \
                    f"CSV missing required header: '{required_header}'\n" \
                    f"Got headers: {header}\n" \
                    "Check CSV export implementation in routes/admin.py"

            # Verify CSV is parseable
            reader = csv.DictReader(io.StringIO(csv_content))
            rows = list(reader)

            assert reader.fieldnames is not None, \
                "CSV could not be parsed\n" \
                "Verify CSV format is valid"

        except TimeoutException:
            pytest.fail(
                f"Admin page did not load in time: {admin_url}\n"
                "Check deployment and admin route"
            )
        finally:
            # Cleanup: remove downloaded file
            for csv_file in glob.glob(os.path.join(download_dir, '*.csv')):
                try:
                    os.remove(csv_file)
                except Exception:
                    pass


class TestMapConfiguration:
    """Validate map configuration and rendering."""

    def test_map_config_api_returns_valid_data(self, browser, installation_config):
        """Verify /api/areas returns map configuration used by frontend."""
        url = f"{installation_config['test_url']}/api/areas"

        # Use requests instead of Selenium for JSON API
        import requests

        try:
            response = requests.get(url, timeout=10)

            assert response.status_code == 200, \
                f"API returned status {response.status_code}\n" \
                f"URL: {url}\n" \
                "Check routes/api.py get_areas() route exists"

            # Parse JSON response
            data = response.json()

            assert 'areas' in data, \
                "API response missing 'areas' key\n" \
                "Check routes/api.py get_areas() implementation"

            assert 'map_config' in data, \
                "API response missing 'map_config' key\n" \
                "Map cannot render without configuration\n" \
                "Check routes/api.py includes map_config from area_boundaries.json"

            # Verify map_config structure
            map_config = data['map_config']
            required_fields = ['center', 'bounds', 'zoom']
            missing_fields = [f for f in required_fields if f not in map_config]

            assert not missing_fields, \
                f"Map config missing required fields: {missing_fields}\n" \
                f"Required: {required_fields}\n" \
                f"Got: {list(map_config.keys())}\n" \
                f"Check static/data/area_boundaries.json structure"

        except requests.exceptions.RequestException as e:
            pytest.fail(
                f"Failed to retrieve API response: {e}\n"
                f"URL: {url}\n"
                "Check routes/api.py get_areas() route exists"
            )
        except json.JSONDecodeError as e:
            pytest.fail(
                f"Failed to parse API response as JSON: {e}\n"
                f"URL: {url}\n"
                "API may be returning error or invalid format"
            )
