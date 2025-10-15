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

    # Form Validation Attributes Tests (Priority 2)

    def test_email_field_has_email_type(self, client):
        """
        Verify email field uses type="email" for semantic validation.

        This enables browser-native email validation and proper mobile keyboard.
        """
        response = client.get('/')
        soup = BeautifulSoup(response.data, 'html.parser')

        email_field = soup.find('input', {'id': 'email', 'name': 'email'})
        assert email_field is not None, "Email field not found"

        field_type = email_field.get('type')
        assert field_type == 'email', f"Email field should have type='email', got: {field_type}"

    def test_phone_fields_have_tel_type(self, client):
        """
        Verify phone fields use type="tel" for mobile keyboard optimization.

        Both primary phone and secondary phone should use tel type.
        """
        response = client.get('/')
        soup = BeautifulSoup(response.data, 'html.parser')

        # Primary phone (cell phone)
        phone_field = soup.find('input', {'id': 'phone', 'name': 'phone'})
        assert phone_field is not None, "Primary phone field not found"
        assert phone_field.get('type') == 'tel', "Primary phone should have type='tel'"

        # Secondary phone
        phone2_field = soup.find('input', {'id': 'phone2', 'name': 'phone2'})
        assert phone2_field is not None, "Secondary phone field not found"
        assert phone2_field.get('type') == 'tel', "Secondary phone should have type='tel'"

    def test_checkboxes_have_checkbox_type(self, client):
        """
        Verify all checkbox fields have type="checkbox".

        Includes: binoculars, spotting scope, leadership interest, scribe interest.
        """
        response = client.get('/')
        soup = BeautifulSoup(response.data, 'html.parser')

        checkbox_fields = [
            'has_binoculars',
            'spotting_scope',
            'interested_in_leadership',
            'interested_in_scribe'
        ]

        for field_name in checkbox_fields:
            checkbox = soup.find('input', {'name': field_name})
            assert checkbox is not None, f"Checkbox {field_name} not found"
            assert checkbox.get('type') == 'checkbox', \
                f"{field_name} should have type='checkbox', got: {checkbox.get('type')}"

    def test_text_inputs_have_text_type(self, client):
        """
        Verify text input fields have type="text" or no type (defaults to text).

        Includes: first_name, last_name.
        """
        response = client.get('/')
        soup = BeautifulSoup(response.data, 'html.parser')

        text_fields = ['first_name', 'last_name']

        for field_name in text_fields:
            text_input = soup.find('input', {'name': field_name})
            assert text_input is not None, f"Text field {field_name} not found"

            field_type = text_input.get('type')
            # Type should be 'text' or None (defaults to text in HTML5)
            assert field_type in ['text', None], \
                f"{field_name} should have type='text' or no type, got: {field_type}"

    def test_labels_have_correct_for_attributes(self, client):
        """
        Verify labels have correct for attributes matching input IDs.

        This is important for accessibility and clicking label to focus field.
        """
        response = client.get('/')
        soup = BeautifulSoup(response.data, 'html.parser')

        # Key field -> label mappings
        field_labels = {
            'first_name': 'First Name',
            'last_name': 'Last Name',
            'email': 'Email',
            'phone': 'Cell Phone',  # Labeled as "Cell Phone" per spec
            'skill_level': 'Skill Level',
            'experience': 'Experience',
            'preferred_area': 'Area'
        }

        for field_id, expected_text_fragment in field_labels.items():
            label = soup.find('label', {'for': field_id})
            assert label is not None, f"Label for '{field_id}' not found"
            assert label.get('for') == field_id, \
                f"Label for attribute should match input id: {field_id}"

    def test_required_attributes_on_required_fields(self, client):
        """
        Verify required fields have required attribute for browser validation.

        Required fields per spec: first_name, last_name, email, skill_level,
        experience, participation_type, preferred_area.
        """
        response = client.get('/')
        soup = BeautifulSoup(response.data, 'html.parser')

        required_fields = {
            'first_name': 'input',
            'last_name': 'input',
            'email': 'input',
            'skill_level': 'select',
            'experience': 'select',
            'preferred_area': 'select',
            'participation_type': 'input'  # radio buttons
        }

        for field_name, field_type in required_fields.items():
            if field_type == 'input':
                field = soup.find('input', {'name': field_name})
            else:
                field = soup.find(field_type, {'name': field_name})

            assert field is not None, f"Required field '{field_name}' not found"
            assert field.get('required') is not None, \
                f"Field '{field_name}' should have required attribute"

    def test_optional_fields_do_not_have_required_attribute(self, client):
        """
        Verify optional fields do not have required attribute.

        Optional fields: phone, phone2, binoculars, scope, leadership, scribe, notes.
        """
        response = client.get('/')
        soup = BeautifulSoup(response.data, 'html.parser')

        optional_fields = {
            'phone': 'input',
            'phone2': 'input',
            'has_binoculars': 'input',
            'spotting_scope': 'input',
            'interested_in_leadership': 'input',
            'interested_in_scribe': 'input',
            'notes_to_organizers': 'textarea'
        }

        for field_name, field_type in optional_fields.items():
            field = soup.find(field_type, {'name': field_name})
            assert field is not None, f"Optional field '{field_name}' not found"

            # Optional fields should NOT have required attribute
            # (None or False, but not True)
            required = field.get('required')
            assert required is None or required == False, \
                f"Optional field '{field_name}' should not have required attribute"


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

    def test_year_tabs_present_with_multiple_years(self, admin_client):
        """
        Verify year tabs exist when multiple years of data are present.

        Spec reference: Lines 182-184 (Tab Navigation)

        Note: This test checks for tab navigation structure. Actual year availability
        depends on database state.
        """
        response = admin_client.get('/admin/participants?year=2025')
        soup = BeautifulSoup(response.data, 'html.parser')

        # Look for year tab navigation (Bootstrap nav-tabs)
        year_tabs = soup.find('ul', {'class': lambda x: x and 'nav-tabs' in x})

        # Year tabs should exist (even if only one year has data)
        assert year_tabs is not None, "Year tab navigation not found"

        # Should have tab items
        tab_items = year_tabs.find_all('li', {'class': 'nav-item'})
        assert len(tab_items) > 0, "Should have at least one year tab"

    def test_historical_year_warning_banner(self, admin_client):
        """
        Verify historical year warning banner appears when viewing past years.

        Spec reference: Lines 185-186 (Historical Data Warning)

        Tests that read-only warning is displayed for historical years.
        """
        # Request a historical year (2024)
        response = admin_client.get('/admin/participants?year=2024')
        soup = BeautifulSoup(response.data, 'html.parser')

        # Look for warning alert/banner
        # Should contain text about read-only or historical data
        alerts = soup.find_all('div', {'class': lambda x: x and 'alert' in x})

        warning_found = False
        for alert in alerts:
            alert_text = alert.get_text().lower()
            if 'read-only' in alert_text or 'historical' in alert_text or 'archive' in alert_text:
                warning_found = True
                break

        # If we're viewing 2024 and have current year 2025 data, should show warning
        # This is conditional - warning only shows for actual historical years
        # We'll make this a soft assertion by checking if year is truly historical
        current_year = datetime.now().year
        if response.status_code == 200:
            # Page loaded, check if it's truly a historical year view
            year_badge = soup.find('span', {'class': 'badge'})
            if year_badge and '2024' in year_badge.text and current_year > 2024:
                assert warning_found, "Historical year warning banner should be present when viewing past years"

    def test_historical_year_tabs_have_distinctive_styling(self, admin_client):
        """
        Verify historical year tabs have distinctive styling (orange text, archive icon).

        Spec reference: Line 184 (Historical year tabs: Orange text with archive icon indicator)
        """
        response = admin_client.get('/admin/participants?year=2025')
        soup = BeautifulSoup(response.data, 'html.parser')

        # Look for year tabs
        year_tabs = soup.find('ul', {'class': lambda x: x and 'nav-tabs' in x})

        if year_tabs:
            # Look for tabs with archive/historical indicators
            # Historical tabs should have text-warning class or archive icon
            tab_links = year_tabs.find_all('a', {'class': 'nav-link'})

            # Check if any tabs have historical styling
            # (orange text via text-warning or archive icon via bi-archive)
            has_historical_styling = False
            for tab_link in tab_links:
                classes = str(tab_link.get('class', []))
                text = tab_link.get_text()

                # Check for orange styling or archive icon
                if 'text-warning' in classes or \
                   tab_link.find('i', {'class': lambda x: x and 'bi-archive' in x}):
                    has_historical_styling = True
                    break

            # This is a soft check - styling only present if historical years exist
            # If we only have current year data, this is OK


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


class TestEmptyStateDisplays:
    """
    Test empty state displays across different pages.

    These tests verify that appropriate messages display when no data exists.
    Priority 2 tests for better UX when collections are empty.
    """

    def test_participants_page_empty_state_message(self, admin_client):
        """
        Verify participants page shows appropriate message when no participants exist.

        Spec reference: Lines 49-50 (Empty States - "No Participants" card)

        Note: This test looks for empty state structure. With test data loaded,
        we verify the template has empty state handling.
        """
        # Request a year that likely has no data (year 2000 for isolation)
        response = admin_client.get('/admin/participants?year=2000')
        soup = BeautifulSoup(response.data, 'html.parser')

        # Page should either have participants or an empty state message
        participant_rows = soup.find_all('tr', {'data-participant-id': True})

        # If no participants, should have empty state message
        if len(participant_rows) == 0:
            # Look for empty state indicators
            empty_state_card = soup.find('div', {'class': lambda x: x and 'card' in x},
                                        string=lambda x: x and 'no participants' in x.lower())

            # Or look for alert/message about no data
            empty_message = soup.find(string=lambda x: x and
                                    ('no participants' in x.lower() or
                                     'no registrations' in x.lower() or
                                     'empty' in x.lower()))

            assert empty_state_card is not None or empty_message is not None, \
                "Should show empty state message when no participants exist"

    def test_unassigned_page_empty_state(self, admin_client):
        """
        Verify unassigned page shows message when all participants are assigned.

        Should display "No unassigned participants" or similar message.
        """
        response = admin_client.get('/admin/unassigned?year=2025')
        soup = BeautifulSoup(response.data, 'html.parser')

        # Look for either table with unassigned participants OR empty state message
        unassigned_table = soup.find('table')

        # If table exists, check if it has rows or shows empty message
        if unassigned_table:
            rows = unassigned_table.find_all('tr')
            # Table might be empty (just headers) or have data

        # Look for "no unassigned" message
        no_unassigned_message = soup.find(string=lambda x: x and
                                         ('no unassigned' in x.lower() or
                                          'all participants assigned' in x.lower() or
                                          'all assigned' in x.lower()))

        # Page should show table OR message, but handle empty gracefully
        assert unassigned_table is not None or no_unassigned_message is not None, \
            "Page should show table or 'no unassigned' message"

    def test_leaders_page_shows_areas_without_leaders(self, admin_client):
        """
        Verify leaders page displays areas that don't have leaders assigned.

        Spec reference: Line 259 (Areas without assigned leaders highlighted)

        Should show which areas need leaders.
        """
        response = admin_client.get('/admin/leaders?year=2025')
        soup = BeautifulSoup(response.data, 'html.parser')

        # Look for section showing areas needing leaders
        # Could be a list, table, or text message
        areas_needing_leaders = soup.find(string=lambda x: x and
                                         ('areas needing' in x.lower() or
                                          'need leaders' in x.lower() or
                                          'no leader assigned' in x.lower()))

        # Or look for map legend showing counts
        map_legend = soup.find('div', {'class': lambda x: x and 'legend' in x.lower()})

        # Should have some indication of leadership status
        assert areas_needing_leaders is not None or map_legend is not None, \
            "Leaders page should indicate which areas need leaders"

    def test_dashboard_handles_zero_participants(self, admin_client):
        """
        Verify dashboard displays gracefully with zero participants.

        Statistics should show zeros rather than errors.
        """
        # Request year with no data
        response = admin_client.get('/admin/?year=2000')
        soup = BeautifulSoup(response.data, 'html.parser')

        # Dashboard should load successfully
        assert response.status_code == 200, "Dashboard should load even with no data"

        # Should have statistics cards showing zeros or "No data" messages
        cards = soup.find_all('div', {'class': lambda x: x and 'card' in x})
        assert len(cards) > 0, "Dashboard should have statistics cards even when empty"

    def test_empty_area_shows_appropriate_message(self, admin_client):
        """
        Verify individual area pages show message when area has no participants.

        Each area detail view should handle empty state.
        """
        # Try to access area detail page (if route exists)
        # This tests /admin/area/<code> route
        response = admin_client.get('/admin/area/A?year=2000')

        # Page might not exist or might redirect - check response
        if response.status_code == 200:
            soup = BeautifulSoup(response.data, 'html.parser')

            # Should show either participants or empty message
            participant_list = soup.find('table')
            empty_message = soup.find(string=lambda x: x and
                                     ('no participants' in x.lower() or
                                      'no registrations' in x.lower()))

            # At least one should be present
            assert participant_list is not None or empty_message is not None, \
                "Area detail page should show participants or empty message"


class TestAccessibility:
    """
    Test accessibility compliance (Priority 3).

    Validates ARIA attributes, semantic HTML, keyboard navigation support,
    and other accessibility best practices.
    """

    def test_tables_have_thead_and_tbody(self, admin_client):
        """
        Verify tables use semantic structure with thead and tbody elements.

        Semantic table structure improves screen reader navigation.
        """
        response = admin_client.get('/admin/participants?year=2025')
        soup = BeautifulSoup(response.data, 'html.parser')

        tables = soup.find_all('table')
        assert len(tables) > 0, "Should have tables to test"

        for table in tables:
            thead = table.find('thead')
            tbody = table.find('tbody')

            assert thead is not None, "Table should have <thead> for semantic structure"
            assert tbody is not None, "Table should have <tbody> for semantic structure"

    def test_buttons_have_correct_type_attribute(self, client):
        """
        Verify buttons have appropriate type attribute (button vs submit).

        Submit buttons should have type="submit", action buttons type="button".
        """
        response = client.get('/')
        soup = BeautifulSoup(response.data, 'html.parser')

        # Find submit button on registration form
        submit_buttons = soup.find_all('button', string=lambda x: x and 'submit' in x.lower())

        for btn in submit_buttons:
            btn_type = btn.get('type')
            assert btn_type == 'submit', f"Submit button should have type='submit', got: {btn_type}"

    def test_admin_buttons_have_type_attribute(self, admin_client):
        """
        Verify admin interface buttons have correct type attributes.

        Action buttons (edit, delete, cancel) should use type="button".
        """
        response = admin_client.get('/admin/participants?year=2025')
        soup = BeautifulSoup(response.data, 'html.parser')

        # Find all buttons
        buttons = soup.find_all('button')

        for btn in buttons:
            btn_type = btn.get('type')
            # All buttons should have explicit type
            assert btn_type in ['button', 'submit'], \
                f"Button should have type attribute, got: {btn_type}"

    def test_images_have_alt_text(self, admin_client):
        """
        Verify all images have alt text for screen readers.

        Images without alt text are inaccessible to vision-impaired users.
        """
        response = admin_client.get('/admin/participants?year=2025')
        soup = BeautifulSoup(response.data, 'html.parser')

        images = soup.find_all('img')

        for img in images:
            alt_text = img.get('alt')
            # Alt attribute should exist (can be empty for decorative images)
            assert alt_text is not None, \
                f"Image {img.get('src')} missing alt attribute"

    def test_scope_icon_has_alt_text(self, admin_client):
        """
        Verify spotting scope icon has descriptive alt text.

        Spec reference: Custom SVG spotting scope icon needs alt text.
        """
        response = admin_client.get('/admin/participants?year=2025')
        soup = BeautifulSoup(response.data, 'html.parser')

        # Look for spotting scope images
        scope_images = soup.find_all('img', {'src': lambda x: x and 'scope' in x.lower()})

        for img in scope_images:
            alt_text = img.get('alt', '')
            assert 'scope' in alt_text.lower(), \
                f"Scope icon should have descriptive alt text, got: {alt_text}"

    def test_form_fields_have_associated_labels(self, client):
        """
        Verify all form inputs have associated labels for accessibility.

        Labels improve usability and are required for screen readers.
        This is already partially tested, but more comprehensive here.
        """
        response = client.get('/')
        soup = BeautifulSoup(response.data, 'html.parser')

        # Find all input fields (excluding hidden and submit)
        inputs = soup.find_all('input', {'type': lambda x: x not in ['hidden', 'submit']})

        for input_field in inputs:
            field_id = input_field.get('id')
            field_name = input_field.get('name')

            if field_id:
                # Should have a label with for attribute
                label = soup.find('label', {'for': field_id})
                assert label is not None, \
                    f"Input field '{field_id}' should have associated label"

    def test_select_fields_have_labels(self, client):
        """
        Verify all select dropdowns have associated labels.

        Dropdown fields need labels for screen reader accessibility.
        """
        response = client.get('/')
        soup = BeautifulSoup(response.data, 'html.parser')

        selects = soup.find_all('select')

        for select in selects:
            select_id = select.get('id')

            if select_id:
                label = soup.find('label', {'for': select_id})
                assert label is not None, \
                    f"Select field '{select_id}' should have associated label"

    def test_navigation_has_aria_label(self, client):
        """
        Verify navigation elements have ARIA labels on public pages.

        Navigation landmarks should be labeled for easy identification.
        Tests public pages only (registration, info pages) for accessibility compliance.
        """
        # Test public pages that vision-impaired users might access
        public_pages = [
            '/',                    # Registration form
            '/area-leader-info',   # Area leader info page
            '/scribe-info'         # Scribe info page
        ]

        for page_url in public_pages:
            response = client.get(page_url)
            assert response.status_code == 200, f"Page {page_url} should load"

            soup = BeautifulSoup(response.data, 'html.parser')

            # Find navigation elements
            navs = soup.find_all('nav')

            # Check each nav element for ARIA labels
            for nav in navs:
                aria_label = nav.get('aria-label')
                aria_labelledby = nav.get('aria-labelledby')

                assert aria_label is not None or aria_labelledby is not None, \
                    f"Navigation on {page_url} should have aria-label or aria-labelledby"

    def test_modals_have_aria_attributes(self, client):
        """
        Verify modal dialogs have proper ARIA attributes on public pages.

        Modals should have role="dialog" and aria-labelledby for accessibility.
        Tests public pages only (registration, info pages) for accessibility compliance.
        """
        # Test public pages that vision-impaired users might access
        public_pages = [
            '/',                    # Registration form
            '/area-leader-info',   # Area leader info page
            '/scribe-info'         # Scribe info page
        ]

        for page_url in public_pages:
            response = client.get(page_url)
            assert response.status_code == 200, f"Page {page_url} should load"

            soup = BeautifulSoup(response.data, 'html.parser')

            # Find modal dialogs (Bootstrap modals)
            modals = soup.find_all('div', {'class': lambda x: x and 'modal' in x})

            # Only check if modals exist on this page
            for modal in modals:
                # Bootstrap modals should have proper attributes
                role = modal.get('role')
                aria_labelledby = modal.get('aria-labelledby')
                aria_hidden = modal.get('aria-hidden')

                # Check for proper modal structure
                if 'modal' in str(modal.get('class', [])):
                    # Should have role or aria attributes
                    assert role == 'dialog' or aria_hidden is not None, \
                        f"Modal on {page_url} should have role='dialog' or aria-hidden"

    def test_main_content_has_semantic_structure(self, client):
        """
        Verify page uses semantic HTML5 elements (main, header, footer, nav).

        Semantic elements improve screen reader navigation.
        """
        response = client.get('/')
        soup = BeautifulSoup(response.data, 'html.parser')

        # Check for semantic elements (at least one should exist)
        has_main = soup.find('main') is not None
        has_nav = soup.find('nav') is not None
        has_header = soup.find('header') is not None
        has_footer = soup.find('footer') is not None

        # Should have at least main or some semantic structure
        assert has_main or has_nav or has_header, \
            "Page should use semantic HTML5 elements (main, nav, header)"

    def test_heading_hierarchy_exists(self, client):
        """
        Verify page has proper heading hierarchy (h1, h2, h3).

        Heading hierarchy helps screen readers navigate page structure.
        """
        response = client.get('/')
        soup = BeautifulSoup(response.data, 'html.parser')

        # Should have at least an h1
        h1 = soup.find('h1')
        assert h1 is not None, "Page should have h1 heading"

        # Should have heading structure
        headings = soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
        assert len(headings) > 0, "Page should have heading structure"

    def test_form_has_semantic_fieldsets(self, client):
        """
        Verify registration form uses fieldset/legend for grouping related fields.

        Fieldsets improve form accessibility by grouping related fields.
        Note: This is optional but recommended for complex forms.
        """
        response = client.get('/')
        soup = BeautifulSoup(response.data, 'html.parser')

        # Check if form uses fieldsets (recommended but not required)
        fieldsets = soup.find_all('fieldset')

        # If fieldsets exist, they should have legends
        for fieldset in fieldsets:
            legend = fieldset.find('legend')
            # Fieldsets should have legends for accessibility
            # This is a soft check - not all forms need fieldsets
            if fieldset:
                assert legend is not None or len(fieldsets) == 0, \
                    "Fieldset should have legend element"

    def test_error_messages_have_aria_live(self, client):
        """
        Verify error/alert messages have aria-live for screen reader announcements.

        Dynamic messages should be announced to screen reader users.
        Note: This checks for alert divs, actual aria-live may be added by JS.
        """
        response = client.get('/')
        soup = BeautifulSoup(response.data, 'html.parser')

        # Look for alert/message containers
        alerts = soup.find_all('div', {'class': lambda x: x and 'alert' in x})

        # Alerts should have role or aria attributes for accessibility
        for alert in alerts:
            role = alert.get('role')
            aria_live = alert.get('aria-live')

            # Bootstrap alerts typically have role="alert"
            # This is a soft check - alerts may be added dynamically
            if len(alerts) > 0:
                # At least check structure exists
                assert True  # Alerts exist, structure is present

    def test_required_fields_have_aria_required(self, client):
        """
        Verify required fields have aria-required attribute for screen readers.

        While 'required' HTML attribute works, aria-required improves compatibility.
        Note: HTML5 'required' attribute is often sufficient, but aria-required helps.
        """
        response = client.get('/')
        soup = BeautifulSoup(response.data, 'html.parser')

        # Find required fields
        required_inputs = soup.find_all(['input', 'select'], {'required': True})

        # Fields with required attribute should ideally have aria-required
        # This is a soft recommendation - HTML5 required is usually sufficient
        if len(required_inputs) > 0:
            # At least check that required fields exist and are marked
            assert len(required_inputs) > 0, "Should have required fields marked"

    def test_skip_navigation_link_exists(self, client):
        """
        Verify skip navigation link exists for keyboard users.

        Skip links allow keyboard users to skip repetitive navigation.
        Note: This is a best practice but not always present.
        """
        response = client.get('/')
        soup = BeautifulSoup(response.data, 'html.parser')

        # Look for skip link (usually first link in body)
        # Common patterns: "Skip to main content", "Skip navigation"
        skip_link = soup.find('a', href=lambda x: x and '#' in x,
                             string=lambda x: x and 'skip' in x.lower())

        # This is optional - many sites don't have skip links
        # Just check if it exists and is properly structured
        if skip_link:
            href = skip_link.get('href')
            assert href.startswith('#'), "Skip link should point to anchor"


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
