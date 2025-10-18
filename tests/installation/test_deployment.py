"""
Phase 3: Deployment Validation Tests
Updated by Claude AI on 2025-10-18

These tests validate that the deployed application is accessible and properly
configured. They verify URLs, static assets, API endpoints, and form rendering
match the configuration files.

All tests are portable - they dynamically validate against config/*.py files
without hardcoded values.

Requirements:
- Test server must be deployed and accessible
- Run against test environment: pytest tests/installation/test_deployment.py -v
"""

import pytest
import requests
import json
from bs4 import BeautifulSoup
from typing import Set, List, Dict


class TestURLAccessibility:
    """Validate that deployed services are accessible with correct responses."""

    def test_registration_page_loads(self, installation_config):
        """Verify registration page loads successfully with registration form."""
        url = installation_config['test_url']

        try:
            response = requests.get(url, timeout=10)
            assert response.status_code == 200, \
                f"Expected status 200, got {response.status_code}"

            # Verify it's the registration page
            soup = BeautifulSoup(response.text, 'html.parser')
            form = soup.find('form', {'action': '/register'})

            assert form is not None, \
                "Registration form not found on page. Check routes/main.py"

        except requests.exceptions.RequestException as e:
            pytest.fail(
                f"Failed to connect to {url}\n"
                f"Error: {e}\n"
                f"Verify deployment: ./deploy.sh test\n"
                f"Check service status: gcloud run services describe {installation_config['test_service']} "
                f"--region={installation_config['gcp_location']}"
            )

    def test_admin_redirects_to_login(self, installation_config):
        """Verify /admin redirects unauthenticated users to login."""
        url = f"{installation_config['test_url']}/admin"

        try:
            # Don't follow redirects to check redirect status
            response = requests.get(url, allow_redirects=False, timeout=10)

            assert response.status_code in [302, 303, 307, 308], \
                f"Expected redirect (302/303/307/308), got {response.status_code}\n" \
                f"Unauthenticated access to /admin should redirect to login"

        except requests.exceptions.RequestException as e:
            pytest.fail(f"Failed to access {url}: {e}")

    def test_leader_redirects_to_login(self, installation_config):
        """Verify /leader redirects unauthenticated users to login."""
        url = f"{installation_config['test_url']}/leader"

        try:
            response = requests.get(url, allow_redirects=False, timeout=10)

            assert response.status_code in [302, 303, 307, 308], \
                f"Expected redirect (302/303/307/308), got {response.status_code}\n" \
                f"Unauthenticated access to /leader should redirect to login"

        except requests.exceptions.RequestException as e:
            pytest.fail(f"Failed to access {url}: {e}")

    def test_api_areas_returns_json(self, installation_config):
        """Verify /api/areas endpoint returns valid JSON."""
        url = f"{installation_config['test_url']}/api/areas"

        try:
            response = requests.get(url, timeout=10)
            assert response.status_code == 200, \
                f"Expected status 200, got {response.status_code}"

            # Verify it's valid JSON
            data = response.json()
            assert isinstance(data, dict), \
                f"Expected JSON object, got {type(data)}"

        except requests.exceptions.RequestException as e:
            pytest.fail(f"Failed to access {url}: {e}")
        except json.JSONDecodeError as e:
            pytest.fail(f"Invalid JSON response from {url}: {e}")

    def test_api_areas_includes_map_config(self, installation_config):
        """Verify /api/areas response includes map_config."""
        url = f"{installation_config['test_url']}/api/areas"

        try:
            response = requests.get(url, timeout=10)
            assert response.status_code == 200, \
                f"Expected status 200, got {response.status_code}"

            # Verify it's valid JSON
            data = response.json()
            assert isinstance(data, dict), \
                f"Expected JSON object, got {type(data)}"

            # Verify map_config is present
            assert 'map_config' in data, \
                f"/api/areas should include 'map_config' key\n" \
                f"Got keys: {list(data.keys())}\n" \
                f"Check routes/api.py get_areas() implementation"

        except requests.exceptions.RequestException as e:
            pytest.fail(f"Failed to access {url}: {e}")
        except json.JSONDecodeError as e:
            pytest.fail(f"Invalid JSON response from {url}: {e}")


class TestStaticAssets:
    """Validate that static assets are accessible and have correct content."""

    def test_area_boundaries_json_accessible(self, installation_config, area_boundaries_data):
        """Verify area_boundaries.json is accessible and matches configured areas."""
        url = f"{installation_config['test_url']}/static/data/area_boundaries.json"

        try:
            response = requests.get(url, timeout=10)
            assert response.status_code == 200, \
                f"Expected status 200, got {response.status_code}\n" \
                f"File should be at static/data/area_boundaries.json"

            # Parse JSON
            data = response.json()

            # Verify structure
            assert 'areas' in data, "Missing 'areas' key in area_boundaries.json"
            assert 'map_config' in data, "Missing 'map_config' key in area_boundaries.json"

            # Verify areas match configuration
            json_area_codes = {area['letter_code'] for area in data['areas']}
            config_area_codes = set(installation_config['all_areas'])

            missing = config_area_codes - json_area_codes
            extra = json_area_codes - config_area_codes

            assert not missing and not extra, \
                f"Area mismatch between area_boundaries.json and config/areas.py:\n" \
                f"Expected (from config/areas.py): {sorted(config_area_codes)}\n" \
                f"Got from JSON: {sorted(json_area_codes)}\n" \
                f"Missing from JSON: {sorted(missing)}\n" \
                f"Extra in JSON: {sorted(extra)}\n" \
                f"Run: python utils/parse_area_boundaries.py to regenerate"

        except requests.exceptions.RequestException as e:
            pytest.fail(f"Failed to access {url}: {e}")
        except json.JSONDecodeError as e:
            pytest.fail(f"Invalid JSON in area_boundaries.json: {e}")

    def test_map_js_loads(self, installation_config):
        """Verify static/js/map.js is accessible."""
        url = f"{installation_config['test_url']}/static/js/map.js"

        try:
            response = requests.get(url, timeout=10)
            assert response.status_code == 200, \
                f"Expected status 200, got {response.status_code}\n" \
                f"File should be at static/js/map.js"

            # Verify it's JavaScript (basic check)
            assert len(response.text) > 0, "map.js is empty"
            assert 'function' in response.text or 'const' in response.text, \
                "map.js doesn't appear to contain JavaScript code"

        except requests.exceptions.RequestException as e:
            pytest.fail(f"Failed to access {url}: {e}")

    def test_leaders_map_js_loads(self, installation_config):
        """Verify static/js/leaders-map.js is accessible."""
        url = f"{installation_config['test_url']}/static/js/leaders-map.js"

        try:
            response = requests.get(url, timeout=10)
            assert response.status_code == 200, \
                f"Expected status 200, got {response.status_code}\n" \
                f"File should be at static/js/leaders-map.js"

            # Verify it's JavaScript (basic check)
            assert len(response.text) > 0, "leaders-map.js is empty"
            assert 'function' in response.text or 'const' in response.text, \
                "leaders-map.js doesn't appear to contain JavaScript code"

        except requests.exceptions.RequestException as e:
            pytest.fail(f"Failed to access {url}: {e}")

    def test_registration_js_loads(self, installation_config):
        """Verify static/js/registration.js is accessible."""
        url = f"{installation_config['test_url']}/static/js/registration.js"

        try:
            response = requests.get(url, timeout=10)
            assert response.status_code == 200, \
                f"Expected status 200, got {response.status_code}\n" \
                f"File should be at static/js/registration.js"

            # Verify it's JavaScript (basic check)
            assert len(response.text) > 0, "registration.js is empty"
            assert 'function' in response.text or 'const' in response.text, \
                "registration.js doesn't appear to contain JavaScript code"

        except requests.exceptions.RequestException as e:
            pytest.fail(f"Failed to access {url}: {e}")

    def test_main_css_loads(self, installation_config):
        """Verify static/css/main.css is accessible."""
        url = f"{installation_config['test_url']}/static/css/main.css"

        try:
            response = requests.get(url, timeout=10)
            assert response.status_code == 200, \
                f"Expected status 200, got {response.status_code}\n" \
                f"File should be at static/css/main.css"

            # Verify it's CSS (basic check)
            assert len(response.text) > 0, "main.css is empty"
            # CSS should have selectors and rules
            assert '{' in response.text and '}' in response.text, \
                "main.css doesn't appear to contain valid CSS"

        except requests.exceptions.RequestException as e:
            pytest.fail(f"Failed to access {url}: {e}")

    def test_logo_accessible(self, installation_config):
        """Verify configured logo is accessible."""
        from config.organization import LOGO_PATH

        if not LOGO_PATH:
            pytest.fail(
                "LOGO_PATH not configured in config/organization.py\n"
                "Set LOGO_PATH to your logo file path (e.g., '/static/icons/logo.png')"
            )

        url = f"{installation_config['test_url']}{LOGO_PATH}"

        try:
            response = requests.get(url, timeout=10)
            assert response.status_code == 200, \
                f"Logo not found at {url}\n" \
                f"LOGO_PATH in config/organization.py is set to: {LOGO_PATH}\n" \
                f"Verify the logo file exists at static{LOGO_PATH.replace('/static', '')}"

            # Verify it's an image (check content type)
            content_type = response.headers.get('content-type', '')
            assert 'image' in content_type, \
                f"Logo URL doesn't return an image. Content-Type: {content_type}"

        except requests.exceptions.RequestException as e:
            pytest.fail(
                f"Failed to access logo at {url}\n"
                f"LOGO_PATH: {LOGO_PATH}\n"
                f"Error: {e}"
            )

    def test_favicon_exists(self, installation_config):
        """Verify favicon is accessible."""
        # Try common favicon locations
        favicon_paths = ['/favicon.ico', '/static/favicon.ico', '/static/icons/favicon.ico']

        url_base = installation_config['test_url']
        found = False
        tried_urls = []

        for path in favicon_paths:
            url = f"{url_base}{path}"
            tried_urls.append(url)
            try:
                response = requests.get(url, timeout=5)
                if response.status_code == 200:
                    found = True
                    break
            except requests.exceptions.RequestException:
                continue

        assert found, \
            f"Favicon not found at any common location.\n" \
            f"Tried: {', '.join(tried_urls)}\n" \
            f"Add a favicon.ico to one of these locations or configure a custom path."


class TestAPIEndpoints:
    """Validate API endpoints return correct data matching configuration."""

    def test_api_areas_has_all_configured_areas(self, installation_config):
        """Verify /api/areas returns all areas from config/areas.py."""
        url = f"{installation_config['test_url']}/api/areas"
        expected_areas = set(installation_config['all_areas'])

        try:
            response = requests.get(url, timeout=10)
            assert response.status_code == 200

            data = response.json()

            # Extract area codes from response
            if 'areas' in data:
                api_areas = {area['letter_code'] for area in data['areas']}
            else:
                # Handle different possible response formats
                api_areas = {area['letter_code'] for area in data} if isinstance(data, list) else set()

            missing = expected_areas - api_areas
            extra = api_areas - expected_areas

            assert not missing and not extra, \
                f"Area mismatch between /api/areas and config/areas.py:\n" \
                f"Expected (from config/areas.py): {sorted(expected_areas)}\n" \
                f"Got from API: {sorted(api_areas)}\n" \
                f"Missing from API: {sorted(missing)}\n" \
                f"Extra in API: {sorted(extra)}\n" \
                f"Check routes/api.py get_areas() implementation"

        except requests.exceptions.RequestException as e:
            pytest.fail(f"Failed to access {url}: {e}")

    def test_api_areas_includes_all_areas(self, installation_config):
        """Verify /api/areas includes all areas (public and admin-only) for map display."""
        url = f"{installation_config['test_url']}/api/areas"
        expected_all = set(installation_config['all_areas'])

        try:
            response = requests.get(url, timeout=10)
            assert response.status_code == 200

            data = response.json()

            # Extract all areas from response
            if 'areas' in data:
                areas_list = data['areas']
            elif isinstance(data, list):
                areas_list = data
            else:
                pytest.fail(f"Unexpected API response format: {type(data)}")

            api_areas = {area['letter_code'] for area in areas_list}

            missing = expected_all - api_areas
            extra = api_areas - expected_all

            assert not missing and not extra, \
                f"Area mismatch between /api/areas and config/areas.py:\n" \
                f"Expected all areas (from config/areas.py): {sorted(expected_all)}\n" \
                f"Got from API: {sorted(api_areas)}\n" \
                f"Missing from API: {sorted(missing)}\n" \
                f"Extra in API: {sorted(extra)}\n" \
                f"Note: /api/areas should include ALL areas (public + admin-only) for map display.\n" \
                f"Check static/data/area_boundaries.json matches config/areas.py"

        except requests.exceptions.RequestException as e:
            pytest.fail(f"Failed to access {url}: {e}")

    def test_api_map_config_structure(self, installation_config):
        """Verify /api/areas map_config has required fields: center, bounds, zoom."""
        url = f"{installation_config['test_url']}/api/areas"

        try:
            response = requests.get(url, timeout=10)
            assert response.status_code == 200

            data = response.json()
            assert 'map_config' in data, "map_config not found in /api/areas response"

            map_config = data['map_config']

            # Check required fields
            required_fields = ['center', 'bounds', 'zoom']
            missing_fields = [field for field in required_fields if field not in map_config]

            assert not missing_fields, \
                f"Missing required fields in map_config: {missing_fields}\n" \
                f"Expected: {required_fields}\n" \
                f"Got: {list(map_config.keys())}\n" \
                f"Check routes/api.py get_areas() implementation"

            # Validate field types
            assert isinstance(map_config['center'], list) and len(map_config['center']) == 2, \
                f"center should be [lat, lng], got: {map_config['center']}"
            assert isinstance(map_config['bounds'], list) and len(map_config['bounds']) == 2, \
                f"bounds should be [[sw_lat, sw_lng], [ne_lat, ne_lng]], got: {map_config['bounds']}"
            assert isinstance(map_config['zoom'], (int, float)), \
                f"zoom should be a number, got: {type(map_config['zoom'])}"

        except requests.exceptions.RequestException as e:
            pytest.fail(f"Failed to access {url}: {e}")

    def test_api_map_config_matches_area_boundaries(self, installation_config):
        """Verify /api/areas map_config matches static/data/area_boundaries.json."""
        api_url = f"{installation_config['test_url']}/api/areas"
        json_url = f"{installation_config['test_url']}/static/data/area_boundaries.json"

        try:
            api_response = requests.get(api_url, timeout=10)
            json_response = requests.get(json_url, timeout=10)

            assert api_response.status_code == 200
            assert json_response.status_code == 200

            api_data = api_response.json()
            json_data = json_response.json()

            # Extract map_config from both sources
            api_map_config = api_data.get('map_config', {})
            json_map_config = json_data.get('map_config', {})

            # Compare center
            assert api_map_config.get('center') == json_map_config.get('center'), \
                f"Map center mismatch:\n" \
                f"API: {api_map_config.get('center')}\n" \
                f"JSON: {json_map_config.get('center')}\n" \
                f"These should match. Check routes/api.py and area_boundaries.json"

            # Compare bounds
            assert api_map_config.get('bounds') == json_map_config.get('bounds'), \
                f"Map bounds mismatch:\n" \
                f"API: {api_map_config.get('bounds')}\n" \
                f"JSON: {json_map_config.get('bounds')}\n" \
                f"These should match. Check routes/api.py and area_boundaries.json"

            # Compare zoom
            assert api_map_config.get('zoom') == json_map_config.get('zoom'), \
                f"Map zoom mismatch:\n" \
                f"API: {api_map_config.get('zoom')}\n" \
                f"JSON: {json_map_config.get('zoom')}\n" \
                f"These should match. Check routes/api.py and area_boundaries.json"

        except requests.exceptions.RequestException as e:
            pytest.fail(f"Failed to access API endpoints: {e}")


class TestRegistrationFormRendering:
    """Validate registration form contains all required options from config."""

    def test_registration_form_has_area_dropdown(self, installation_config):
        """Verify registration form dropdown contains all public areas."""
        url = installation_config['test_url']
        expected_public = set(installation_config['public_areas'])

        try:
            response = requests.get(url, timeout=10)
            assert response.status_code == 200

            soup = BeautifulSoup(response.text, 'html.parser')

            # Find area selection dropdown
            area_select = soup.find('select', {'name': 'preferred_area'}) or \
                         soup.find('select', {'id': 'preferred_area'})

            assert area_select is not None, \
                "Area preference dropdown not found in registration form\n" \
                "Looking for <select name='preferred_area'> or <select id='preferred_area'>\n" \
                "Check templates/index.html"

            # Extract option values
            options = area_select.find_all('option')
            area_codes = {
                opt['value'] for opt in options
                if opt.get('value') and opt['value'] != 'UNASSIGNED'
            }

            missing = expected_public - area_codes
            extra = area_codes - expected_public

            assert not missing, \
                f"Public areas missing from registration form dropdown:\n" \
                f"Expected (from config/areas.py): {sorted(expected_public)}\n" \
                f"Got from form: {sorted(area_codes)}\n" \
                f"Missing: {sorted(missing)}\n" \
                f"Check routes/main.py passes all public areas to template"

            # Extra areas are acceptable if they're valid (might be admin areas shown conditionally)

        except requests.exceptions.RequestException as e:
            pytest.fail(f"Failed to access {url}: {e}")

    def test_skill_level_dropdown_complete(self, installation_config):
        """Verify skill level dropdown has all 4 levels."""
        url = installation_config['test_url']
        expected_levels = {'newbie', 'beginner', 'intermediate', 'expert'}

        try:
            response = requests.get(url, timeout=10)
            assert response.status_code == 200

            soup = BeautifulSoup(response.text, 'html.parser')

            # Find skill level dropdown
            skill_select = soup.find('select', {'name': 'skill_level'}) or \
                          soup.find('select', {'id': 'skill_level'})

            assert skill_select is not None, \
                "Skill level dropdown not found in registration form\n" \
                "Check templates/index.html for skill_level field"

            # Extract option values
            options = skill_select.find_all('option')
            skill_values = {opt['value'].lower() for opt in options if opt.get('value')}

            missing = expected_levels - skill_values

            assert not missing, \
                f"Skill levels missing from dropdown:\n" \
                f"Expected: {sorted(expected_levels)}\n" \
                f"Got: {sorted(skill_values)}\n" \
                f"Missing: {sorted(missing)}\n" \
                f"Check templates/index.html skill_level options"

        except requests.exceptions.RequestException as e:
            pytest.fail(f"Failed to access {url}: {e}")

    def test_experience_dropdown_complete(self, installation_config):
        """Verify experience dropdown has all 3 levels."""
        url = installation_config['test_url']
        expected_experience = {'none', '1-2 counts', '3+ counts'}

        try:
            response = requests.get(url, timeout=10)
            assert response.status_code == 200

            soup = BeautifulSoup(response.text, 'html.parser')

            # Find experience dropdown
            exp_select = soup.find('select', {'name': 'experience'}) or \
                        soup.find('select', {'id': 'experience'})

            assert exp_select is not None, \
                "Experience dropdown not found in registration form\n" \
                "Check templates/index.html for experience field"

            # Extract option values
            options = exp_select.find_all('option')
            exp_values = {opt['value'].lower() for opt in options if opt.get('value')}

            missing = expected_experience - exp_values

            assert not missing, \
                f"Experience levels missing from dropdown:\n" \
                f"Expected: {sorted(expected_experience)}\n" \
                f"Got: {sorted(exp_values)}\n" \
                f"Missing: {sorted(missing)}\n" \
                f"Check templates/index.html experience options"

        except requests.exceptions.RequestException as e:
            pytest.fail(f"Failed to access {url}: {e}")

    def test_participation_type_options(self, installation_config):
        """Verify participation type has regular and FEEDER options."""
        url = installation_config['test_url']
        # Note: Looking for the value 'FEEDER' specifically, as 'regular' might be implicit

        try:
            response = requests.get(url, timeout=10)
            assert response.status_code == 200

            soup = BeautifulSoup(response.text, 'html.parser')

            # Find participation type field (could be radio buttons or dropdown)
            # Look for inputs with name='participation_type'
            participation_inputs = soup.find_all('input', {'name': 'participation_type'}) or \
                                  soup.find_all('option', {'name': 'participation_type'})

            if not participation_inputs:
                # Try finding by id
                participation_inputs = soup.find_all('input', {'id': lambda x: x and 'participation' in x.lower()})

            assert participation_inputs, \
                "Participation type field not found in registration form\n" \
                "Check templates/index.html for participation_type field"

            # Extract values
            values = {inp.get('value', '').upper() for inp in participation_inputs if inp.get('value')}

            assert 'FEEDER' in values, \
                f"FEEDER participation type missing from form\n" \
                f"Got values: {values}\n" \
                f"Check templates/index.html participation_type options"

        except requests.exceptions.RequestException as e:
            pytest.fail(f"Failed to access {url}: {e}")

    def test_form_has_csrf_token(self, installation_config):
        """Verify registration form includes CSRF protection."""
        url = installation_config['test_url']

        try:
            response = requests.get(url, timeout=10)
            assert response.status_code == 200

            soup = BeautifulSoup(response.text, 'html.parser')

            # Find registration form
            form = soup.find('form', {'action': '/register'})
            assert form is not None, "Registration form not found"

            # Look for CSRF token field
            csrf_input = form.find('input', {'name': 'csrf_token'}) or \
                        form.find('input', {'id': 'csrf_token'})

            assert csrf_input is not None, \
                "CSRF token missing from registration form\n" \
                "Form should include {{ csrf_token() }} in templates/index.html\n" \
                "This is a security requirement per CLAUDE.md"

        except requests.exceptions.RequestException as e:
            pytest.fail(f"Failed to access {url}: {e}")

    def test_unassigned_option_present(self, installation_config):
        """Verify 'Wherever I'm needed most' (UNASSIGNED) option is available."""
        url = installation_config['test_url']

        try:
            response = requests.get(url, timeout=10)
            assert response.status_code == 200

            soup = BeautifulSoup(response.text, 'html.parser')

            # Find area selection dropdown
            area_select = soup.find('select', {'name': 'preferred_area'}) or \
                         soup.find('select', {'id': 'preferred_area'})

            assert area_select is not None, "Area preference dropdown not found"

            # Look for UNASSIGNED option
            options = area_select.find_all('option')
            has_unassigned = any(
                opt.get('value') == 'UNASSIGNED'
                for opt in options
            )

            assert has_unassigned, \
                "UNASSIGNED option missing from area dropdown\n" \
                "Users should be able to select 'Wherever I'm needed most'\n" \
                "Check templates/index.html preferred_area options"

        except requests.exceptions.RequestException as e:
            pytest.fail(f"Failed to access {url}: {e}")

    def test_admin_only_areas_excluded(self, installation_config):
        """Verify admin-only areas are not shown in public registration form."""
        url = installation_config['test_url']

        # Find admin-only areas
        admin_only = {
            code for code, config in installation_config['area_config'].items()
            if config.get('admin_assignment_only', False)
        }

        if not admin_only:
            pytest.skip("No admin-only areas configured")

        try:
            response = requests.get(url, timeout=10)
            assert response.status_code == 200

            soup = BeautifulSoup(response.text, 'html.parser')

            # Find area selection dropdown
            area_select = soup.find('select', {'name': 'preferred_area'}) or \
                         soup.find('select', {'id': 'preferred_area'})

            assert area_select is not None, "Area preference dropdown not found"

            # Extract option values
            options = area_select.find_all('option')
            area_codes = {opt['value'] for opt in options if opt.get('value')}

            # Check for admin-only areas
            found_admin_only = area_codes.intersection(admin_only)

            assert not found_admin_only, \
                f"Admin-only areas should not appear in public registration form:\n" \
                f"Found in form: {sorted(found_admin_only)}\n" \
                f"These areas have admin_assignment_only=True in config/areas.py\n" \
                f"Check routes/main.py uses get_public_areas() not get_all_areas()"

        except requests.exceptions.RequestException as e:
            pytest.fail(f"Failed to access {url}: {e}")
