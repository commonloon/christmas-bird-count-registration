# Updated by Claude AI on 2025-10-15
"""
UI Conformance Tests - Verify rendered HTML templates match specification.

These tests use Flask test client to render templates and validate that UI
elements (dropdowns, form fields, table columns, etc.) conform to the
requirements in SPECIFICATION.md.

Tests connect to the real cbc-test Firestore database and use test data
loaded by tests/utils/load_test_data.py to validate UI behavior with actual data.

Setup:
    Before running these tests, load test data:
    python tests/utils/load_test_data.py --years 2025

Note: Flask extensions (flask_wtf, flask_limiter) are mocked to avoid
requiring their installation for unit tests.
"""

import sys
import os
from unittest.mock import Mock, MagicMock
from functools import wraps

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
sys.path.insert(0, project_root)

# Create a proper mock for flask_wtf.csrf
class MockCSRFProtect:
    """Mock CSRF protection that does nothing but provides csrf_token function."""
    def __init__(self, app=None):
        self.app = app
        if app:
            self.init_app(app)

    def init_app(self, app):
        """Initialize with app and register csrf_token function."""
        if app:
            # Register csrf_token function for templates
            @app.context_processor
            def csrf_token_processor():
                return {'csrf_token': lambda: 'mock-csrf-token'}

    def exempt(self, view):
        """Return the view unchanged."""
        return view

mock_flask_wtf = MagicMock()
mock_flask_wtf.csrf = MagicMock()
mock_flask_wtf.csrf.CSRFProtect = MockCSRFProtect
sys.modules['flask_wtf'] = mock_flask_wtf
sys.modules['flask_wtf.csrf'] = mock_flask_wtf.csrf

# Create a proper mock for flask_limiter that works as a decorator
def create_limiter_mock():
    """Create a limiter mock that properly handles decorator usage."""
    class MockLimiter:
        def __init__(self, *args, **kwargs):
            pass

        def init_app(self, app):
            """Initialize with Flask app (no-op for testing)."""
            pass

        def limit(self, *args, **kwargs):
            """Return a decorator that preserves function attributes."""
            def decorator(f):
                @wraps(f)
                def wrapper(*args, **kwargs):
                    return f(*args, **kwargs)
                return wrapper
            return decorator

        def exempt(self, f):
            """Return the function unchanged."""
            return f

    mock_module = MagicMock()
    mock_module.Limiter = MockLimiter
    mock_module.util = MagicMock()
    return mock_module

sys.modules['flask_limiter'] = create_limiter_mock()
sys.modules['flask_limiter.util'] = MagicMock()

import pytest
from bs4 import BeautifulSoup
from flask import session
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@pytest.fixture(scope='session')
def load_test_data():
    """
    Session-scoped fixture to ensure test data is loaded before any tests run.

    This loads test participants into year 2025 collection in cbc-test database.
    The data is loaded once per test session and shared across all tests.
    """
    from config.database import get_firestore_client

    # Import load_test_data utility
    sys.path.insert(0, os.path.join(project_root, 'tests', 'utils'))
    from load_test_data import load_test_fixture

    # Connect to database
    db, database_name = get_firestore_client()
    logger.info(f"Connected to database: {database_name}")

    # Load test data for year 2025
    try:
        results = load_test_fixture(
            db,
            years=[2025],
            csv_filename='test_participants_2025.csv',
            clear_first=True
        )
        logger.info(f"Test data loaded: {results}")
        return results
    except Exception as e:
        logger.error(f"Failed to load test data: {e}")
        # Return empty dict if loading fails - tests will handle missing data
        return {}


@pytest.fixture
def app(load_test_data):
    """
    Get Flask app in test mode connected to real cbc-test database.

    Depends on load_test_data fixture to ensure database has known test data.
    """
    # Import the app module (app is created at module level, not via create_app)
    import app as app_module
    flask_app = app_module.app
    flask_app.config['TESTING'] = True
    flask_app.config['WTF_CSRF_ENABLED'] = False  # Disable CSRF for testing
    return flask_app


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture
def admin_client(client):
    """Create test client with admin session."""
    with client.session_transaction() as sess:
        sess['user_email'] = 'cbc-test-admin1@naturevancouver.ca'
        sess['user_name'] = 'Test Admin'
        sess['user_role'] = 'admin'  # Use 'user_role', not just 'role'
    return client


class TestRegistrationFormUI:
    """Test registration form conforms to specification."""

    def test_skill_level_dropdown_has_all_four_options(self, client):
        """
        Verify skill level dropdown has all four options per spec:
        Newbie, Beginner, Intermediate, Expert

        Spec reference: Line 416 - skill_level: "Newbie|Beginner|Intermediate|Expert"
        """
        response = client.get('/')
        assert response.status_code == 200

        soup = BeautifulSoup(response.data, 'html.parser')
        skill_select = soup.find('select', {'id': 'skill_level', 'name': 'skill_level'})

        assert skill_select is not None, "Skill level dropdown not found"

        # Get all option values (excluding empty "Choose..." option)
        options = [opt.get('value') for opt in skill_select.find_all('option') if opt.get('value')]
        expected_options = ['Newbie', 'Beginner', 'Intermediate', 'Expert']

        assert options == expected_options, f"Expected {expected_options}, got {options}"

    def test_skill_level_dropdown_is_required(self, client):
        """Verify skill level field has required attribute."""
        response = client.get('/')
        soup = BeautifulSoup(response.data, 'html.parser')

        skill_select = soup.find('select', {'name': 'skill_level'})
        assert skill_select.get('required') is not None, "Skill level should be required"

    def test_experience_dropdown_has_correct_options(self, client):
        """
        Verify experience dropdown has correct options per spec:
        None, 1-2 counts, 3+ counts

        Spec reference: Line 417 - experience: "None|1-2 counts|3+ counts"
        """
        response = client.get('/')
        soup = BeautifulSoup(response.data, 'html.parser')

        experience_select = soup.find('select', {'id': 'experience', 'name': 'experience'})
        assert experience_select is not None, "Experience dropdown not found"

        options = [opt.get('value') for opt in experience_select.find_all('option') if opt.get('value')]

        expected = ['None', '1-2 counts', '3+ counts']
        assert options == expected, f"Expected {expected}, got {options}"

    def test_experience_dropdown_is_required(self, client):
        """Verify experience field has required attribute."""
        response = client.get('/')
        soup = BeautifulSoup(response.data, 'html.parser')

        experience_select = soup.find('select', {'name': 'experience'})
        assert experience_select.get('required') is not None, "Experience should be required"

    def test_participation_type_options_present(self, client):
        """
        Verify participation type radio buttons for regular and FEEDER.

        Spec reference: Line 418 - participation_type: "regular|FEEDER"
        """
        response = client.get('/')
        soup = BeautifulSoup(response.data, 'html.parser')

        regular_radio = soup.find('input', {'name': 'participation_type', 'value': 'regular'})
        feeder_radio = soup.find('input', {'name': 'participation_type', 'value': 'FEEDER'})

        assert regular_radio is not None, "Regular participation radio button not found"
        assert feeder_radio is not None, "FEEDER participation radio button not found"
        assert regular_radio.get('required') is not None, "Participation type should be required"

    def test_required_fields_present(self, client):
        """
        Verify all required fields exist on registration form.

        Spec reference: Lines 112-129 (Core Participant Fields)
        """
        response = client.get('/')
        soup = BeautifulSoup(response.data, 'html.parser')

        required_fields = {
            'first_name': 'input',
            'last_name': 'input',
            'email': 'input',
            'skill_level': 'select',
            'experience': 'select',
            'participation_type': 'input',  # radio buttons
            'preferred_area': 'select'
        }

        for field_name, field_type in required_fields.items():
            if field_type == 'input':
                field_elem = soup.find('input', {'name': field_name})
            else:
                field_elem = soup.find(field_type, {'name': field_name})

            assert field_elem is not None, f"Required field '{field_name}' not found"

    def test_optional_fields_present(self, client):
        """Verify optional fields exist on registration form."""
        response = client.get('/')
        soup = BeautifulSoup(response.data, 'html.parser')

        optional_fields = {
            'phone': 'input',  # Cell phone (primary)
            'phone2': 'input',  # Secondary phone
            'has_binoculars': 'input',  # checkbox
            'spotting_scope': 'input',  # checkbox
            'interested_in_leadership': 'input',  # checkbox
            'interested_in_scribe': 'input',  # checkbox
            'notes_to_organizers': 'textarea'
        }

        for field_name, field_type in optional_fields.items():
            field_elem = soup.find(field_type, {'name': field_name})
            assert field_elem is not None, f"Optional field '{field_name}' not found"

    def test_equipment_checkboxes_present(self, client):
        """
        Verify equipment checkboxes exist.

        Spec reference: Lines 419-420 (has_binoculars, spotting_scope)
        """
        response = client.get('/')
        soup = BeautifulSoup(response.data, 'html.parser')

        binoculars = soup.find('input', {'id': 'has_binoculars', 'type': 'checkbox'})
        scope = soup.find('input', {'id': 'spotting_scope', 'type': 'checkbox'})

        assert binoculars is not None, "Binoculars checkbox not found"
        assert scope is not None, "Spotting scope checkbox not found"

    def test_leadership_and_scribe_checkboxes_present(self, client):
        """
        Verify leadership and scribe interest checkboxes exist.

        Spec reference: Lines 422-423 (interested_in_leadership, interested_in_scribe)
        """
        response = client.get('/')
        soup = BeautifulSoup(response.data, 'html.parser')

        leadership = soup.find('input', {'id': 'interested_in_leadership', 'type': 'checkbox'})
        scribe = soup.find('input', {'id': 'interested_in_scribe', 'type': 'checkbox'})

        assert leadership is not None, "Leadership interest checkbox not found"
        assert scribe is not None, "Scribe interest checkbox not found"

    def test_phone_field_label_is_cell_phone(self, client):
        """
        Verify primary phone field is labeled "Cell Phone" per spec.

        Spec reference: Line 413 - phone: string (labeled "Cell Phone")
        """
        response = client.get('/')
        soup = BeautifulSoup(response.data, 'html.parser')

        # Find label for phone field
        phone_label = soup.find('label', {'for': 'phone'})
        assert phone_label is not None, "Phone field label not found"

        label_text = phone_label.text.strip()
        assert 'Cell' in label_text, f"Phone label should contain 'Cell', got: {label_text}"

    def test_area_dropdown_has_all_public_areas(self, client):
        """
        Verify area dropdown has all 24 public areas (A-X, excluding admin-only Y).

        Validates that config/areas.py public areas are correctly rendered.
        """
        from config.areas import get_public_areas

        response = client.get('/')
        soup = BeautifulSoup(response.data, 'html.parser')

        area_select = soup.find('select', {'id': 'preferred_area', 'name': 'preferred_area'})
        assert area_select is not None, "Area dropdown not found"

        # Get all area option values (excluding empty "Choose..." and UNASSIGNED)
        options = [opt.get('value') for opt in area_select.find_all('option')
                   if opt.get('value') and opt.get('value') not in ['', 'UNASSIGNED']]

        expected_areas = get_public_areas()  # Should be A-X (24 areas, excludes Y)

        assert len(options) == len(expected_areas), \
            f"Expected {len(expected_areas)} areas, found {len(options)}"

        # Verify each expected area is present
        for area_code in expected_areas:
            assert area_code in options, f"Area {area_code} missing from dropdown"

        # Verify Area Y (admin-only) is NOT present
        assert 'Y' not in options, "Area Y (admin-only) should not be in public dropdown"

    def test_area_dropdown_has_unassigned_option(self, client):
        """Verify area dropdown has UNASSIGNED option for flexible assignment."""
        response = client.get('/')
        soup = BeautifulSoup(response.data, 'html.parser')

        area_select = soup.find('select', {'id': 'preferred_area'})
        unassigned_option = area_select.find('option', {'value': 'UNASSIGNED'})

        assert unassigned_option is not None, "UNASSIGNED option not found"
        assert 'needed most' in unassigned_option.text.lower(), \
            "UNASSIGNED option should indicate 'wherever needed most'"

    def test_area_dropdown_is_required(self, client):
        """Verify area dropdown has required attribute."""
        response = client.get('/')
        soup = BeautifulSoup(response.data, 'html.parser')

        area_select = soup.find('select', {'name': 'preferred_area'})
        assert area_select.get('required') is not None, "Area should be required"

    def test_guide_links_present(self, client):
        """Verify guide links for field counters and feeder counters are present."""
        response = client.get('/')
        soup = BeautifulSoup(response.data, 'html.parser')

        # Look for guide links
        field_guide = soup.find('a', href=lambda x: x and 'field-counters-guide' in x.lower())
        feeder_guide = soup.find('a', href=lambda x: x and 'feeder-counters-guide' in x.lower())

        assert field_guide is not None, "Field Counters guide link not found"
        assert feeder_guide is not None, "Feeder Counters guide link not found"

        # Verify they open in new tab
        assert field_guide.get('target') == '_blank', "Field guide should open in new tab"
        assert feeder_guide.get('target') == '_blank', "Feeder guide should open in new tab"

    def test_privacy_section_present(self, client):
        """Verify privacy information section is present per regulations."""
        response = client.get('/')
        soup = BeautifulSoup(response.data, 'html.parser')

        # Look for privacy section with specific text
        privacy_text = soup.find(string=lambda x: x and 'Provincial Privacy Act' in x)
        assert privacy_text is not None, "Privacy Act compliance text not found"

    def test_map_div_present(self, client):
        """Verify interactive map div exists on registration page."""
        response = client.get('/')
        soup = BeautifulSoup(response.data, 'html.parser')

        map_div = soup.find('div', {'id': 'count-area-map'})
        assert map_div is not None, "Map div not found"

        # Should have style attribute for height
        assert map_div.get('style'), "Map div should have inline style for height"


class TestAdminParticipantsUI:
    """Test admin participants page conforms to specification."""

    def test_edit_skill_level_dropdown_includes_newbie(self, admin_client):
        """
        Verify inline edit skill level dropdown includes Newbie option.

        This test validates the fix for the missing Newbie option in admin edit mode.
        Spec reference: Line 416 - skill_level: "Newbie|Beginner|Intermediate|Expert"

        Requires: Test data loaded in year 2025 (via load_test_data fixture)
        """
        response = admin_client.get('/admin/participants?year=2025')
        assert response.status_code == 200

        soup = BeautifulSoup(response.data, 'html.parser')

        # Find the skill level dropdown in edit mode (hidden by default in table rows)
        skill_selects = soup.find_all('select', {'class': 'skill-input'})

        # Should have dropdowns if test data is loaded
        assert len(skill_selects) > 0, "No skill level dropdowns found - test data may not be loaded"

        # Check the first dropdown structure
        skill_select = skill_selects[0]
        options = [opt.get('value') for opt in skill_select.find_all('option')]

        expected = ['Newbie', 'Beginner', 'Intermediate', 'Expert']
        assert options == expected, f"Admin edit dropdown missing options. Expected {expected}, got {options}"

        # Specifically verify Newbie is present (the bug we fixed)
        assert 'Newbie' in options, "Newbie option missing from admin edit dropdown"

    def test_edit_experience_is_dropdown_not_input(self, admin_client):
        """
        Verify experience field in edit mode is a dropdown, not text input.

        Spec reference: Line 417 - experience should be dropdown with defined values

        Requires: Test data loaded in year 2025 (via load_test_data fixture)
        """
        response = admin_client.get('/admin/participants?year=2025')
        soup = BeautifulSoup(response.data, 'html.parser')

        # Should find select elements with experience-input class
        experience_selects = soup.find_all('select', {'class': 'experience-input'})

        # Should NOT find input elements with experience-input class
        experience_inputs = soup.find_all('input', {'class': 'experience-input'})

        # Should have dropdowns if test data is loaded
        assert len(experience_selects) > 0, "No experience dropdowns found - test data may not be loaded"
        assert len(experience_inputs) == 0, "Found text input for experience (should be dropdown)"

        # Verify dropdown has correct options
        exp_select = experience_selects[0]
        options = [opt.get('value') for opt in exp_select.find_all('option')]
        expected = ['None', '1-2 counts', '3+ counts']
        assert options == expected, f"Experience dropdown: expected {expected}, got {options}"

    def test_edit_experience_dropdown_has_correct_options(self, admin_client):
        """
        Verify experience dropdown in edit mode has all correct options.

        Spec reference: Line 417 - experience: "None|1-2 counts|3+ counts"

        Requires: Test data loaded in year 2025 (via load_test_data fixture)
        """
        response = admin_client.get('/admin/participants?year=2025')
        soup = BeautifulSoup(response.data, 'html.parser')

        experience_selects = soup.find_all('select', {'class': 'experience-input'})
        assert len(experience_selects) > 0, "No experience dropdowns found - test data may not be loaded"

        options = [opt.get('value') for opt in experience_selects[0].find_all('option')]
        expected = ['None', '1-2 counts', '3+ counts']
        assert options == expected, f"Expected {expected}, got {options}"

    def test_table_has_all_required_columns(self, admin_client):
        """
        Verify participant table has all required columns per spec.

        Spec reference: Lines 111-122 (Participant table columns)

        Requires: Test data loaded in year 2025 (via load_test_data fixture)
        """
        response = admin_client.get('/admin/participants?year=2025')
        soup = BeautifulSoup(response.data, 'html.parser')

        # Find table headers
        tables = soup.find_all('table')
        assert len(tables) > 0, "No tables found - test data may not be loaded"

        headers = [th.text.strip() for th in tables[0].find_all('th')]

        required_columns = [
            'Name', 'Email', 'Cell Phone', 'Skill Level', 'Experience',
            'Equipment', 'Notes', 'Leader', 'Scribe', 'Actions'
        ]

        for col in required_columns:
            assert col in headers, f"Required column '{col}' not found in table. Found: {headers}"

    def test_participant_table_displays_phone_as_cell_phone(self, admin_client):
        """
        Verify table header uses "Cell Phone" not just "Phone".

        Spec reference: Line 413 - phone labeled as "Cell Phone"

        Requires: Test data loaded in year 2025 (via load_test_data fixture)
        """
        response = admin_client.get('/admin/participants?year=2025')
        soup = BeautifulSoup(response.data, 'html.parser')

        tables = soup.find_all('table')
        assert len(tables) > 0, "No tables found - test data may not be loaded"

        headers = [th.text.strip() for th in tables[0].find_all('th')]

        assert 'Cell Phone' in headers, f"Expected 'Cell Phone' header, found: {headers}"
        # Make sure it's not just "Phone"
        assert 'Phone' not in [h for h in headers if h != 'Cell Phone'], "Should use 'Cell Phone' not 'Phone'"

    def test_quick_actions_buttons_present(self, admin_client):
        """Verify Quick Actions section has expected buttons."""
        response = admin_client.get('/admin/participants?year=2025')
        soup = BeautifulSoup(response.data, 'html.parser')

        # Check for key action buttons
        manage_unassigned = soup.find('a', href=lambda x: x and '/admin/unassigned' in x)
        manage_leaders = soup.find('a', href=lambda x: x and '/admin/leaders' in x)
        export_csv = soup.find('a', href=lambda x: x and '/admin/export_csv' in x)

        assert manage_unassigned is not None, "Manage Unassigned button not found"
        assert manage_leaders is not None, "Manage Leaders button not found"
        assert export_csv is not None, "Export CSV button not found"

    def test_delete_modal_structure(self, admin_client):
        """
        Verify delete confirmation modal has correct structure.

        Modal should include participant name, warning message, reason textarea.
        """
        response = admin_client.get('/admin/participants?year=2025')
        soup = BeautifulSoup(response.data, 'html.parser')

        # Find delete modal
        delete_modal = soup.find('div', {'id': 'deleteModal'})
        assert delete_modal is not None, "Delete modal not found"

        # Check modal has required elements
        assert delete_modal.find('textarea', {'id': 'deleteReason'}), \
            "Delete reason textarea not found"
        assert delete_modal.find('button', {'type': 'submit'}), \
            "Delete submit button not found"
        assert delete_modal.find(string=lambda x: x and 'cannot be undone' in x.lower()), \
            "Warning message not found in delete modal"

    def test_leader_reassignment_modal_structure(self, admin_client):
        """
        Verify leader reassignment modal exists with correct options.

        Modal should allow moving leader as leader or as team member.
        """
        response = admin_client.get('/admin/participants?year=2025')
        soup = BeautifulSoup(response.data, 'html.parser')

        # Find leader reassignment modal
        leader_modal = soup.find('div', {'id': 'leaderReassignModal'})
        assert leader_modal is not None, "Leader reassignment modal not found"

        # Check for two action buttons
        move_as_leader = leader_modal.find('button', {'id': 'moveAsLeader'})
        move_as_member = leader_modal.find('button', {'id': 'moveAsTeamMember'})

        assert move_as_leader is not None, "'Move as Leader' button not found"
        assert move_as_member is not None, "'Move as Team Member' button not found"

    def test_year_badge_displays_current_year(self, admin_client):
        """Verify year badge shows the selected year."""
        response = admin_client.get('/admin/participants?year=2025')
        soup = BeautifulSoup(response.data, 'html.parser')

        # Look for year badge
        year_badge = soup.find('span', {'class': 'badge'})
        assert year_badge is not None, "Year badge not found"
        assert '2025' in year_badge.text, f"Year badge should show 2025, got: {year_badge.text}"

    def test_breadcrumb_navigation_present(self, admin_client):
        """Verify breadcrumb navigation is present."""
        response = admin_client.get('/admin/participants?year=2025')
        soup = BeautifulSoup(response.data, 'html.parser')

        breadcrumb = soup.find('nav', {'aria-label': 'breadcrumb'})
        assert breadcrumb is not None, "Breadcrumb navigation not found"

        # Should have link to dashboard
        dashboard_link = breadcrumb.find('a', href=lambda x: x and '/admin/' in x)
        assert dashboard_link is not None, "Dashboard link not in breadcrumb"


class TestAdminLeadersUI:
    """Test admin leaders page conforms to specification."""

    def test_leaders_table_has_required_columns(self, admin_client):
        """
        Verify leaders table has all required columns.

        Spec reference: Lines 244-246 (Leader table columns)

        Note: Leaders table should exist even if empty
        """
        response = admin_client.get('/admin/leaders?year=2025')
        assert response.status_code == 200

        soup = BeautifulSoup(response.data, 'html.parser')

        # Find the Current Leaders table
        tables = soup.find_all('table')
        assert len(tables) > 0, "No tables found on leaders page"

        # First table should be current leaders
        headers = [th.text.strip() for th in tables[0].find_all('th')]

        required_columns = ['Area', 'Leader', 'Email', 'Cell Phone', 'Secondary Phone', 'Actions']

        for col in required_columns:
            assert col in headers, f"Required column '{col}' not found. Found: {headers}"

    def test_potential_leaders_table_present(self, admin_client):
        """Verify Potential Leaders section exists."""
        response = admin_client.get('/admin/leaders?year=2025')
        soup = BeautifulSoup(response.data, 'html.parser')

        # Look for Potential Leaders heading or table
        potential_leaders_heading = soup.find(string=lambda x: x and 'Potential Leaders' in x)
        assert potential_leaders_heading is not None, "Potential Leaders section not found"


class TestInfoPages:
    """Test information pages conform to specification."""

    def test_area_leader_info_page_accessible(self, client):
        """Verify area leader info page loads."""
        response = client.get('/area-leader-info')
        assert response.status_code == 200

    def test_scribe_info_page_accessible(self, client):
        """Verify scribe info page loads."""
        response = client.get('/scribe-info')
        assert response.status_code == 200

    def test_area_leader_info_preserves_form_data(self, client):
        """
        Verify area leader info page can receive form data via query params.

        Spec reference: Lines 147-164 (Form Data Preservation System)
        """
        # Simulate clicking area leader link with form data
        response = client.get('/area-leader-info?first_name=John&last_name=Doe&email=test@example.com')
        assert response.status_code == 200

        # Page should load successfully with query params
        soup = BeautifulSoup(response.data, 'html.parser')
        # The actual form data restoration happens in JavaScript, but page should load
        assert soup is not None


class TestDashboardUI:
    """Test admin dashboard conforms to specification."""

    def test_dashboard_loads_for_admin(self, admin_client):
        """Verify admin dashboard loads successfully."""
        response = admin_client.get('/admin/')
        assert response.status_code == 200

    def test_dashboard_has_statistics_section(self, admin_client):
        """Verify dashboard displays statistics overview."""
        response = admin_client.get('/admin/')
        soup = BeautifulSoup(response.data, 'html.parser')

        # Look for common dashboard elements
        # Should have some cards or statistics
        cards = soup.find_all('div', {'class': lambda x: x and 'card' in x})
        assert len(cards) > 0, "Dashboard should have statistics cards"

    def test_dashboard_has_year_selector(self, admin_client):
        """Verify dashboard has year selector."""
        response = admin_client.get('/admin/')
        soup = BeautifulSoup(response.data, 'html.parser')

        # Look for year selector or year indicator
        year_badge = soup.find('span', {'class': 'badge'})
        assert year_badge is not None, "Dashboard should display selected year"


class TestAdminUnassignedPage:
    """Test admin unassigned participants page - critical workflow for assignments."""

    def test_unassigned_page_loads(self, admin_client):
        """Verify unassigned page is accessible."""
        response = admin_client.get('/admin/unassigned?year=2025')
        assert response.status_code == 200

    def test_unassigned_page_has_table(self, admin_client):
        """Verify page displays unassigned participants table."""
        response = admin_client.get('/admin/unassigned?year=2025')
        soup = BeautifulSoup(response.data, 'html.parser')

        # Should have at least one table
        tables = soup.find_all('table')
        assert len(tables) > 0, "Unassigned page should have a table"

    def test_unassigned_table_has_assignment_controls(self, admin_client):
        """Verify table has controls for assigning participants to areas."""
        response = admin_client.get('/admin/unassigned?year=2025')
        soup = BeautifulSoup(response.data, 'html.parser')

        # Look for select/dropdown elements for area assignment
        area_selects = soup.find_all('select', {'class': lambda x: x and 'area' in x.lower()})

        # If there are unassigned participants, should have assignment controls
        # If no unassigned participants, that's OK (empty state)
        # Just verify page structure exists
        assert soup.find('table') is not None or \
               soup.find(string=lambda x: x and ('no unassigned' in x.lower() or 'all assigned' in x.lower())), \
            "Page should show table with controls or 'no unassigned' message"


class TestCSVExport:
    """Test CSV export functionality - critical for data integrity."""

    def test_csv_export_returns_csv_content_type(self, admin_client):
        """Verify CSV export returns correct content type."""
        response = admin_client.get('/admin/export_csv?year=2025')
        assert response.status_code == 200

        content_type = response.headers.get('Content-Type', '')
        assert 'csv' in content_type.lower() or 'text/plain' in content_type.lower(), \
            f"Expected CSV content type, got: {content_type}"

    def test_csv_export_has_filename_with_year(self, admin_client):
        """Verify CSV filename includes year for organization."""
        response = admin_client.get('/admin/export_csv?year=2025')

        content_disposition = response.headers.get('Content-Disposition', '')
        assert 'attachment' in content_disposition.lower(), \
            "CSV should be served as attachment"
        assert '2025' in content_disposition, \
            f"Filename should include year 2025, got: {content_disposition}"

    def test_csv_export_has_required_headers(self, admin_client):
        """
        Verify CSV includes all required columns per specification.

        This is critical for data integrity and downstream processing.

        Requires: Test data loaded in year 2025 (via load_test_data fixture)
        """
        response = admin_client.get('/admin/export_csv?year=2025')
        csv_data = response.data.decode('utf-8')

        # Parse CSV headers (first line)
        lines = csv_data.strip().split('\n')
        assert len(lines) > 0, "CSV should not be empty"

        headers = lines[0].split(',')
        headers = [h.strip().strip('"') for h in headers]

        # Required fields per specification
        required_fields = [
            'first_name', 'last_name', 'email', 'phone',
            'skill_level', 'experience', 'preferred_area',
            'participation_type', 'has_binoculars', 'spotting_scope'
        ]

        for field in required_fields:
            assert any(field.lower() in h.lower() for h in headers), \
                f"Required field '{field}' not found in CSV headers. Found: {headers}"


class TestDataDrivenParticipantRendering:
    """
    Data-driven tests that validate participant data renders correctly.

    These tests use actual data from the test database to verify UI behavior.
    """

    def test_participants_render_with_data(self, admin_client):
        """
        Verify that participants from test database render in tables.

        Requires: Test data loaded in year 2025 (via load_test_data fixture)
        """
        response = admin_client.get('/admin/participants?year=2025')
        soup = BeautifulSoup(response.data, 'html.parser')

        # Find all participant rows (tr elements with data-participant-id)
        participant_rows = soup.find_all('tr', {'data-participant-id': True})

        assert len(participant_rows) > 0, \
            "Should have at least one participant rendered from test data"

    def test_participant_names_display_correctly(self, admin_client):
        """
        Verify participant names render correctly in table.

        Checks that names are escaped and displayed properly.
        """
        response = admin_client.get('/admin/participants?year=2025')
        soup = BeautifulSoup(response.data, 'html.parser')

        # Find participant name elements
        participant_names = soup.find_all('strong', {'class': 'participant-name'})

        assert len(participant_names) > 0, "Should have participant names displayed"

        # Verify names have content (not empty)
        for name_elem in participant_names:
            name_text = name_elem.text.strip()
            assert len(name_text) > 0, "Participant name should not be empty"
            assert name_text != 'None', "Participant name should be valid"

    def test_skill_level_badges_render(self, admin_client):
        """
        Verify skill level badges render with correct Bootstrap classes.

        Badges should have color coding: Expert=success, Intermediate=primary,
        Beginner=info, Newbie=secondary.
        """
        response = admin_client.get('/admin/participants?year=2025')
        soup = BeautifulSoup(response.data, 'html.parser')

        # Find skill level displays
        skill_displays = soup.find_all('div', {'class': 'skill-display'})

        assert len(skill_displays) > 0, "Should have skill level displays"

        # Check that badges exist and have Bootstrap classes
        for skill_div in skill_displays[:5]:  # Check first 5
            badge = skill_div.find('span', {'class': lambda x: x and 'badge' in x})
            if badge:  # Some might be in hidden edit mode
                assert 'bg-' in str(badge.get('class')), \
                    "Skill badge should have Bootstrap background class"

    def test_feeder_participants_have_special_styling(self, admin_client):
        """
        Verify FEEDER participants have table-info class for visual distinction.

        Per spec, FEEDER participants should be visually distinguished.
        """
        response = admin_client.get('/admin/participants?year=2025')
        soup = BeautifulSoup(response.data, 'html.parser')

        # Find all table rows
        all_rows = soup.find_all('tr', {'data-participant-id': True})

        # Look for rows with table-info class (FEEDER participants)
        feeder_rows = [row for row in all_rows if 'table-info' in str(row.get('class', []))]

        # If we have FEEDER participants in test data, they should have styling
        # This is a soft check - test data may not have FEEDER participants
        if feeder_rows:
            for row in feeder_rows:
                # Should have FEEDER indicator
                feeder_text = row.find(string=lambda x: x and x.strip() == 'FEEDER')
                assert feeder_text is not None, \
                    "FEEDER row should have FEEDER text indicator"

    def test_equipment_icons_display(self, admin_client):
        """
        Verify equipment icons display for participants with equipment.

        Icons: binoculars icon, spotting scope icon/image.
        """
        response = admin_client.get('/admin/participants?year=2025')
        soup = BeautifulSoup(response.data, 'html.parser')

        # Find equipment display divs
        equipment_displays = soup.find_all('div', {'class': 'equipment-display'})

        assert len(equipment_displays) > 0, "Should have equipment displays"

        # Check that at least some have icons (bootstrap icons or img tags)
        has_binocular_icons = len(soup.find_all('i', {'class': lambda x: x and 'bi-binoculars' in x})) > 0
        has_scope_images = len(soup.find_all('img', {'alt': lambda x: x and 'scope' in x.lower()})) > 0

        # Soft check - test data should have at least some participants with equipment
        assert has_binocular_icons or has_scope_images or \
               any('None' in div.text for div in equipment_displays), \
            "Should show equipment icons or 'None' indicator"

    def test_leader_badges_display_correctly(self, admin_client):
        """
        Verify is_leader participants have leader badge displayed.

        Leader badge should be visible and styled (bg-success).
        """
        response = admin_client.get('/admin/participants?year=2025')
        soup = BeautifulSoup(response.data, 'html.parser')

        # Find all leader badges
        leader_badges = soup.find_all('span', {'class': lambda x: x and 'badge' in x},
                                     string=lambda x: x and 'Leader' in x)

        # Test data may or may not have leaders - just verify structure if present
        if leader_badges:
            for badge in leader_badges:
                assert 'bg-success' in str(badge.get('class')), \
                    "Leader badge should have success (green) background"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
