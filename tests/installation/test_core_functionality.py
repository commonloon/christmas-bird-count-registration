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


@pytest.mark.installation
class TestRegistrationWorkflow:
    """Validate basic participant registration workflow."""

    @pytest.mark.smoke
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

    @pytest.mark.smoke
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

    @pytest.mark.smoke
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

    @pytest.mark.installation
    def test_area_dropdown_excludes_admin_only(self, browser, installation_config):
        """Verify areas with admin_assignment_only=True are excluded from dropdown."""
        url = installation_config['test_url']
        area_config = installation_config['area_config']

        # Find admin-only areas
        admin_only_areas = {
            code for code, config in area_config.items()
            if config.get('admin_assignment_only', False)
        }

        if not admin_only_areas:
            pytest.skip("No admin-only areas configured")

        browser.get(url)

        try:
            wait = WebDriverWait(browser, 10)
            area_select = wait.until(
                EC.presence_of_element_located((By.NAME, 'preferred_area'))
            )

            select = Select(area_select)
            dropdown_values = {opt.get_attribute('value') for opt in select.options if opt.get_attribute('value')}

            # Check that admin-only areas are NOT in dropdown
            found_admin_only = dropdown_values.intersection(admin_only_areas)

            assert not found_admin_only, \
                f"Admin-only areas should not appear in public dropdown:\n" \
                f"Found: {sorted(found_admin_only)}\n" \
                f"Check templates/index.html filters admin_assignment_only areas"

        except TimeoutException:
            pytest.fail("Area dropdown not found")

    @pytest.mark.installation
    def test_skill_level_dropdown_complete(self, browser, installation_config):
        """Verify skill level dropdown has all 4 required options."""
        url = installation_config['test_url']
        expected_skills = {'Newbie', 'Beginner', 'Intermediate', 'Expert'}

        browser.get(url)

        try:
            wait = WebDriverWait(browser, 10)
            skill_select = wait.until(
                EC.presence_of_element_located((By.NAME, 'skill_level'))
            )

            select = Select(skill_select)
            dropdown_skills = {opt.get_attribute('value') for opt in select.options if opt.get_attribute('value')}

            missing = expected_skills - dropdown_skills

            assert not missing, \
                f"Skill levels missing from dropdown:\n" \
                f"Expected: {sorted(expected_skills)}\n" \
                f"Got: {sorted(dropdown_skills)}\n" \
                f"Missing: {sorted(missing)}\n" \
                f"Check templates/index.html skill_level options"

        except TimeoutException:
            pytest.fail("Skill level dropdown not found")

    @pytest.mark.installation
    def test_experience_dropdown_complete(self, browser, installation_config):
        """Verify experience dropdown has all 3 required options."""
        url = installation_config['test_url']
        expected_experience = {'None', '1-2 counts', '3+ counts'}

        browser.get(url)

        try:
            wait = WebDriverWait(browser, 10)
            exp_select = wait.until(
                EC.presence_of_element_located((By.NAME, 'experience'))
            )

            select = Select(exp_select)
            dropdown_exp = {opt.get_attribute('value') for opt in select.options if opt.get_attribute('value')}

            missing = expected_experience - dropdown_exp

            assert not missing, \
                f"Experience levels missing from dropdown:\n" \
                f"Expected: {sorted(expected_experience)}\n" \
                f"Got: {sorted(dropdown_exp)}\n" \
                f"Missing: {sorted(missing)}\n" \
                f"Check templates/index.html experience options"

        except TimeoutException:
            pytest.fail("Experience dropdown not found")

    @pytest.mark.installation
    def test_participation_type_options_present(self, browser, installation_config):
        """Verify participation type radio buttons include 'regular' and 'FEEDER'."""
        url = installation_config['test_url']

        browser.get(url)

        try:
            wait = WebDriverWait(browser, 10)

            # Wait for form to load
            wait.until(EC.presence_of_element_located((By.NAME, 'participation_type')))

            # Find all participation_type radio buttons
            radio_buttons = browser.find_elements(By.NAME, 'participation_type')
            values = {btn.get_attribute('value') for btn in radio_buttons}

            required = {'regular', 'FEEDER'}
            missing = required - values

            assert not missing, \
                f"Participation type options missing:\n" \
                f"Expected: {sorted(required)}\n" \
                f"Got: {sorted(values)}\n" \
                f"Missing: {sorted(missing)}\n" \
                f"Check templates/index.html participation_type radio buttons"

        except TimeoutException:
            pytest.fail("Participation type radio buttons not found")


@pytest.mark.installation
class TestAdminAccess:
    """Validate admin authentication and dashboard access."""

    @pytest.mark.smoke
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

    @pytest.mark.smoke
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

    @pytest.mark.installation
    def test_participants_page_shows_all_areas(self, authenticated_browser, installation_config):
        """Verify admin participants page displays all configured areas."""
        url = f"{installation_config['test_url']}/admin/participants"
        all_areas = installation_config['all_areas']

        authenticated_browser.get(url)

        try:
            wait = WebDriverWait(authenticated_browser, 10)

            # Wait for page to load
            wait.until(EC.presence_of_element_located((By.TAG_NAME, 'body')))

            page_text = authenticated_browser.page_source

            # Check that all area codes appear somewhere on the page
            # (either in table, dropdowns, or area filters)
            missing_areas = []
            for area_code in all_areas:
                if area_code not in page_text:
                    missing_areas.append(area_code)

            assert not missing_areas, \
                f"Some areas not visible on participants page:\n" \
                f"Missing: {sorted(missing_areas)}\n" \
                f"All {len(all_areas)} configured areas should be accessible\n" \
                f"Check routes/admin.py participants route includes all areas"

        except TimeoutException:
            pytest.fail(f"Participants page did not load: {url}")

    @pytest.mark.installation
    def test_can_view_leader_management_page(self, authenticated_browser, installation_config):
        """Verify admin can access leader management page."""
        url = f"{installation_config['test_url']}/admin/leaders"

        authenticated_browser.get(url)

        try:
            wait = WebDriverWait(authenticated_browser, 10)

            # Wait for leader management page to load
            wait.until(EC.presence_of_element_located((By.TAG_NAME, 'h1')))

            page_text = authenticated_browser.page_source

            # Verify we're on the leaders page
            assert 'leader' in page_text.lower(), \
                "Leader management page did not load correctly\n" \
                "Expected page content about leaders\n" \
                "Check routes/admin.py leaders route"

            # Check that page has leader table or controls
            has_leader_table = len(authenticated_browser.find_elements(By.CSS_SELECTOR, 'table')) > 0
            has_leader_form = len(authenticated_browser.find_elements(By.CSS_SELECTOR, 'form')) > 0

            assert has_leader_table or has_leader_form, \
                "Leader management page missing table or form\n" \
                "Page should have leader list or leader assignment controls\n" \
                "Check templates/admin/leaders.html"

        except TimeoutException:
            pytest.fail(f"Leader management page did not load: {url}")


@pytest.mark.smoke
@pytest.mark.installation
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


@pytest.mark.installation
class TestMapFunctionality:
    """Validate map display and interaction (comprehensive tests)."""

    def test_map_center_within_bounds(self, browser, installation_config, area_boundaries_data):
        """Verify map center point is reasonable for configured areas."""
        if not area_boundaries_data:
            pytest.skip("area_boundaries.json not available")

        url = installation_config['test_url']
        browser.get(url)

        try:
            wait = WebDriverWait(browser, 10)
            wait.until(EC.presence_of_element_located((By.ID, 'count-area-map')))

            # Get map config from area_boundaries.json
            map_config = area_boundaries_data.get('map_config', {})
            center = map_config.get('center')
            bounds = map_config.get('bounds')

            assert center, "Map config missing 'center' point"
            assert bounds, "Map config missing 'bounds'"

            # Verify center is within bounds
            lat, lng = center
            [[south, west], [north, east]] = bounds

            assert south <= lat <= north, \
                f"Map center latitude {lat} outside bounds [{south}, {north}]\n" \
                f"Check static/data/area_boundaries.json map_config.center"

            assert west <= lng <= east, \
                f"Map center longitude {lng} outside bounds [{west}, {east}]\n" \
                f"Check static/data/area_boundaries.json map_config.center"

        except TimeoutException:
            pytest.fail("Map container not found")

    def test_map_shows_all_areas(self, browser, installation_config):
        """Verify map renders polygons for all configured areas."""
        url = installation_config['test_url']
        all_areas = installation_config['all_areas']

        browser.get(url)

        try:
            wait = WebDriverWait(browser, 15)

            # Wait for map to initialize
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '.leaflet-container')))

            # Wait for area polygons to render (they have area codes as classes or data attributes)
            # Give extra time for all polygons to load
            import time
            time.sleep(3)

            # Check that polygons exist (Leaflet creates SVG paths for polygons)
            polygons = browser.find_elements(By.CSS_SELECTOR, '.leaflet-interactive')

            assert len(polygons) > 0, \
                "No interactive map elements (polygons) found\n" \
                "Map may not be rendering area boundaries\n" \
                "Check static/js/map.js loads area_boundaries.json correctly"

            # We expect at least as many polygons as areas (some areas might have multiple polygons)
            assert len(polygons) >= len(all_areas), \
                f"Expected at least {len(all_areas)} polygons for {len(all_areas)} areas\n" \
                f"Found only {len(polygons)} interactive elements\n" \
                f"Some areas may not be rendering on the map"

        except TimeoutException:
            pytest.fail("Map did not render polygons within 15 seconds")

    def test_area_polygons_clickable(self, browser, installation_config):
        """Verify area polygons are interactive and clickable."""
        url = installation_config['test_url']

        browser.get(url)

        try:
            wait = WebDriverWait(browser, 15)

            # Wait for map and polygons to load
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '.leaflet-interactive')))

            import time
            time.sleep(2)

            # Find clickable polygons
            polygons = browser.find_elements(By.CSS_SELECTOR, '.leaflet-interactive')

            assert len(polygons) > 0, "No clickable polygons found on map"

            # Try clicking the first polygon
            first_polygon = polygons[0]

            # Scroll to make polygon visible if needed
            browser.execute_script("arguments[0].scrollIntoView(true);", first_polygon)
            time.sleep(0.5)

            # Try to click the polygon - use JavaScript click if regular click fails
            from selenium.common.exceptions import ElementNotInteractableException
            try:
                first_polygon.click()
            except ElementNotInteractableException:
                # SVG elements don't have .click() method - dispatch click event instead
                browser.execute_script("""
                    var event = new MouseEvent('click', {
                        view: window,
                        bubbles: true,
                        cancelable: true
                    });
                    arguments[0].dispatchEvent(event);
                """, first_polygon)

            time.sleep(1)

            # After clicking, the area dropdown should be updated or highlighted
            # Check that preferred_area dropdown exists and has a selection
            area_select = browser.find_element(By.NAME, 'preferred_area')
            selected_value = Select(area_select).first_selected_option.get_attribute('value')

            # Clicking a polygon should select an area (not empty or UNASSIGNED unless that's what was clicked)
            assert selected_value, \
                "Clicking polygon did not update area dropdown\n" \
                "Check static/js/map.js polygon click handler"

        except TimeoutException:
            pytest.fail("Could not interact with map polygons")
        except Exception as e:
            pytest.fail(f"Error testing polygon interaction: {e}")

    def test_map_zoom_and_bounds_reasonable(self, browser, installation_config, area_boundaries_data):
        """Verify map zoom level and bounds are reasonable for the areas."""
        if not area_boundaries_data:
            pytest.skip("area_boundaries.json not available")

        map_config = area_boundaries_data.get('map_config', {})
        zoom = map_config.get('zoom')
        bounds = map_config.get('bounds')

        assert zoom is not None, "Map config missing 'zoom' level"
        assert isinstance(zoom, (int, float)), f"Zoom should be numeric, got {type(zoom)}"
        assert 1 <= zoom <= 20, \
            f"Zoom level {zoom} outside reasonable range [1, 20]\n" \
            f"Typical city-level zoom is 10-14\n" \
            f"Check static/data/area_boundaries.json map_config.zoom"

        assert bounds, "Map config missing 'bounds'"
        [[south, west], [north, east]] = bounds

        # Verify bounds make sense (north > south, east > west in most cases)
        assert north > south, \
            f"North bound ({north}) should be greater than south bound ({south})\n" \
            f"Check bounds in area_boundaries.json"

        # For most cases east > west, but handle international dateline crossing
        if east < west:
            # Crossing dateline - this is okay but less common
            pass


@pytest.mark.smoke
@pytest.mark.installation
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


@pytest.mark.installation
class TestDataIntegrity:
    """Validate data models and database integrity (comprehensive tests)."""

    def test_database_collections_accessible(self, installation_config):
        """Verify can access participant and leader collections for current year."""
        from google.cloud import firestore
        from config.database import get_firestore_client

        db, database_id = get_firestore_client()
        current_year = installation_config['current_year']

        try:
            # Check participants collection exists and is accessible
            participants_collection = db.collection(f'participants_{current_year}')

            # Try to query (limit to 1 to avoid loading all data)
            try:
                list(participants_collection.limit(1).stream())
            except Exception as e:
                pytest.fail(
                    f"Cannot access participants_{current_year} collection: {e}\n"
                    f"Database: {database_id}\n"
                    "Run: python utils/verify_indexes.py {database_id}"
                )

            # Check area_leaders collection exists and is accessible
            leaders_collection = db.collection(f'area_leaders_{current_year}')

            try:
                list(leaders_collection.limit(1).stream())
            except Exception as e:
                pytest.fail(
                    f"Cannot access area_leaders_{current_year} collection: {e}\n"
                    f"Database: {database_id}\n"
                    "Collection should be created automatically on first use"
                )

        except Exception as e:
            pytest.fail(f"Database connection error: {e}")

    def test_participant_model_methods_available(self, installation_config):
        """Verify ParticipantModel core methods are available and functional."""
        from models.participant import ParticipantModel
        from config.database import get_firestore_client

        db, _ = get_firestore_client()

        try:
            model = ParticipantModel(db)

            # Verify critical methods exist
            assert hasattr(model, 'get_all_participants'), \
                "ParticipantModel missing get_all_participants() method"

            assert hasattr(model, 'get_participants_by_area'), \
                "ParticipantModel missing get_participants_by_area() method"

            assert hasattr(model, 'get_leaders'), \
                "ParticipantModel missing get_leaders() method"

            assert hasattr(model, 'get_area_counts'), \
                "ParticipantModel missing get_area_counts() method"

            assert hasattr(model, 'get_leaders_by_area'), \
                "ParticipantModel missing get_leaders_by_area() method"

            assert hasattr(model, 'get_areas_without_leaders'), \
                "ParticipantModel missing get_areas_without_leaders() method"

            # Try calling get_area_counts (should work even with empty database)
            try:
                counts = model.get_area_counts()
                assert isinstance(counts, dict), \
                    "get_area_counts() should return dict"
            except Exception as e:
                pytest.fail(
                    f"ParticipantModel.get_area_counts() failed: {e}\n"
                    "Check models/participant.py implementation"
                )

        except ImportError as e:
            pytest.fail(f"Cannot import ParticipantModel: {e}")
        except Exception as e:
            pytest.fail(f"ParticipantModel initialization failed: {e}")

    def test_removal_log_model_accessible(self, installation_config):
        """Verify RemovalLogModel is accessible and functional."""
        from models.removal_log import RemovalLogModel
        from config.database import get_firestore_client

        db, _ = get_firestore_client()

        try:
            model = RemovalLogModel(db)

            # Verify critical methods exist
            assert hasattr(model, 'log_removal'), \
                "RemovalLogModel missing log_removal() method"

            assert hasattr(model, 'get_all_removals'), \
                "RemovalLogModel missing get_all_removals() method"

            assert hasattr(model, 'get_pending_removals'), \
                "RemovalLogModel missing get_pending_removals() method"

            assert hasattr(model, 'get_removal_stats'), \
                "RemovalLogModel missing get_removal_stats() method"

            # Try calling get_all_removals (should work even with empty database)
            try:
                logs = model.get_all_removals()
                assert isinstance(logs, list), \
                    "get_all_removals() should return list"
            except Exception as e:
                pytest.fail(
                    f"RemovalLogModel.get_all_removals() failed: {e}\n"
                    "Check models/removal_log.py implementation"
                )

        except ImportError as e:
            pytest.fail(f"Cannot import RemovalLogModel: {e}")
        except Exception as e:
            pytest.fail(f"RemovalLogModel initialization failed: {e}")
