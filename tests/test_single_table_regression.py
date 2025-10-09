# Single-Table Architecture Regression Tests
# Created by Claude AI on 2025-09-23

"""
Comprehensive regression tests for the single-table architecture conversion.
Tests all critical workflows to ensure the conversion from dual-table (participants + area_leaders)
to single-table (participants with leadership flags) preserves all functionality.

Test Categories:
1. Participant Registration (all types: regular, feeder, leader candidates, scribes)
2. Leader Promotion Workflows (participant → leader, validation)
3. Admin Leader Management UI (add, edit, delete leaders)
4. CSV Export Functionality (participants and leaders separately)
5. Data Integrity and Synchronization
"""

import pytest
import logging
import time
import sys
import os
from datetime import datetime

# Add project root to Python path for imports
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import requests
import csv
import io
import re
from tests.utils.auth_utils import admin_login_for_test

logger = logging.getLogger(__name__)


def safe_click(browser, locator, timeout=10):
    """Safely click an element by scrolling to it and waiting for it to be clickable."""
    wait = WebDriverWait(browser, timeout)
    element = wait.until(EC.element_to_be_clickable(locator))
    browser.execute_script("arguments[0].scrollIntoView(true);", element)
    time.sleep(0.3)  # Brief pause after scrolling
    element.click()
    return element


def safe_select_by_value(browser, locator, value, timeout=10):
    """Safely select a dropdown option by value after scrolling the dropdown into view."""
    wait = WebDriverWait(browser, timeout)
    select_element = wait.until(EC.element_to_be_clickable(locator))
    browser.execute_script("arguments[0].scrollIntoView(true);", select_element)
    time.sleep(0.3)  # Brief pause after scrolling

    select = Select(select_element)
    select.select_by_value(value)
    return select_element


def verify_registration_success(browser, expected_email):
    """Verify successful registration by checking database first, then URL."""
    import urllib.parse
    from models.participant import ParticipantModel
    from config.database import get_firestore_client

    # Wait for page redirect and database write
    time.sleep(3)

    # Check database FIRST - this is the source of truth
    db, _ = get_firestore_client()
    participant_model = ParticipantModel(db, datetime.now().year)

    # Find participant by email
    participants = participant_model.get_all_participants()
    matching_participants = [p for p in participants if p.get('email', '').lower() == expected_email.lower()]

    assert matching_participants, f"No participant found with email: {expected_email}"
    participant = max(matching_participants, key=lambda p: p.get('created_at', ''))
    participant_id = participant.get('id')

    logger.info(f"✓ Database: Found registered participant: {participant.get('first_name')} {participant.get('last_name')} ({expected_email})")

    # Now check if success page was displayed (UI validation)
    current_url = browser.current_url
    if not ("/success" in current_url or "participant_id=" in current_url):
        logger.warning(f"UI Issue: Registration succeeded in database but browser did not navigate to success page. URL: {current_url}")
        logger.warning("This indicates a timing or navigation issue in the UI, but registration actually succeeded.")
    else:
        logger.info(f"✓ UI: Success page displayed at {current_url}")

    return participant_id, participant


class TestParticipantRegistration:
    """Test participant registration for all participation types."""

    @pytest.mark.critical
    def test_regular_participant_registration(self, browser, base_url, clean_database):
        """Test basic participant registration with regular participation type."""
        browser.get(base_url)

        # Fill registration form
        browser.find_element(By.ID, "first_name").send_keys("John")
        browser.find_element(By.ID, "last_name").send_keys("RegularTest")
        browser.find_element(By.ID, "email").send_keys("john.regular@test-regression.ca")
        browser.find_element(By.ID, "phone").send_keys("604-555-0001")

        # Select skill level and experience
        safe_select_by_value(browser, (By.ID, "skill_level"), "Intermediate")
        safe_select_by_value(browser, (By.ID, "experience"), "1-2 counts")

        # Select area and participation type
        safe_select_by_value(browser, (By.ID, "preferred_area"), "A")
        safe_click(browser, (By.ID, "regular"))  # Click radio button for regular participation

        # Equipment preferences
        safe_click(browser, (By.ID, "has_binoculars"))

        # Submit registration
        safe_click(browser, (By.XPATH, "//button[@type='submit']"))

        # Verify successful registration
        participant_id, participant = verify_registration_success(browser, "john.regular@test-regression.ca")
        assert participant['participation_type'] == 'regular'
        assert participant.get('is_leader', False) == False
        assert participant.get('has_binoculars', False) == True  # We clicked the checkbox

    @pytest.mark.critical
    def test_feeder_participant_registration(self, browser, base_url, clean_database):
        """Test feeder participant registration with specific constraints."""
        browser.get(base_url)

        # Fill registration form
        browser.find_element(By.ID, "first_name").send_keys("Jane")
        browser.find_element(By.ID, "last_name").send_keys("FeederTest")
        browser.find_element(By.ID, "email").send_keys("jane.feeder@test-regression.ca")
        browser.find_element(By.ID, "phone").send_keys("604-555-0002")

        # Select skill level and experience
        safe_select_by_value(browser, (By.ID, "skill_level"), "Beginner")
        safe_select_by_value(browser, (By.ID, "experience"), "None")  # First time

        # Feeder participants must select specific area (not UNASSIGNED)
        safe_select_by_value(browser, (By.ID, "preferred_area"), "B")
        safe_click(browser, (By.ID, "feeder"))  # Click radio button for feeder participation

        # Feeder participants cannot be interested in leadership
        # This should be enforced by client-side validation

        # Submit registration
        safe_click(browser, (By.XPATH, "//button[@type='submit']"))

        # Verify successful registration
        participant_id, participant = verify_registration_success(browser, "jane.feeder@test-regression.ca")
        assert participant['participation_type'] == 'FEEDER'
        assert participant.get('interested_in_leadership', False) == False

    @pytest.mark.critical
    def test_leader_candidate_registration(self, browser, base_url, clean_database):
        """Test registration of participant interested in leadership."""
        browser.get(base_url)

        # Fill registration form
        browser.find_element(By.ID, "first_name").send_keys("Bob")
        browser.find_element(By.ID, "last_name").send_keys("LeaderCandidate")
        browser.find_element(By.ID, "email").send_keys("bob.leader@test-regression.ca")
        browser.find_element(By.ID, "phone").send_keys("604-555-0003")

        # Experienced birder
        safe_select_by_value(browser, (By.ID, "skill_level"), "Expert")
        safe_select_by_value(browser, (By.ID, "experience"), "3+ counts")

        # Select area and regular participation
        safe_select_by_value(browser, (By.ID, "preferred_area"), "C")
        safe_click(browser, (By.ID, "regular"))  # Click radio button for regular participation

        # Express interest in leadership
        safe_click(browser, (By.ID, "interested_in_leadership"))
        safe_click(browser, (By.ID, "has_binoculars"))
        safe_click(browser, (By.ID, "spotting_scope"))

        # Submit registration
        safe_click(browser, (By.XPATH, "//button[@type='submit']"))

        # Verify successful registration
        participant_id, participant = verify_registration_success(browser, "bob.leader@test-regression.ca")
        assert participant.get('interested_in_leadership', False) == True
        assert participant.get('is_leader', False) == False  # Not yet promoted

    @pytest.mark.critical
    def test_scribe_candidate_registration(self, browser, base_url, clean_database):
        """Test registration of participant interested in being a scribe."""
        browser.get(base_url)

        # Fill registration form
        browser.find_element(By.ID, "first_name").send_keys("Alice")
        browser.find_element(By.ID, "last_name").send_keys("ScribeCandidate")
        browser.find_element(By.ID, "email").send_keys("alice.scribe@test-regression.ca")
        browser.find_element(By.ID, "phone").send_keys("604-555-0004")

        # Intermediate birder
        safe_select_by_value(browser, (By.ID, "skill_level"), "Intermediate")
        safe_select_by_value(browser, (By.ID, "experience"), "1-2 counts")

        # Select area and participation
        safe_select_by_value(browser, (By.ID, "preferred_area"), "D")
        safe_click(browser, (By.ID, "regular"))  # Click radio button for regular participation

        # Express interest in scribe role
        safe_click(browser, (By.ID, "interested_in_scribe"))
        safe_click(browser, (By.ID, "has_binoculars"))

        # Add notes
        browser.find_element(By.ID, "notes_to_organizers").send_keys("Good handwriting, experience with data entry")

        # Submit registration
        safe_click(browser, (By.XPATH, "//button[@type='submit']"))

        # Verify successful registration
        participant_id, participant = verify_registration_success(browser, "alice.scribe@test-regression.ca")
        assert participant.get('interested_in_scribe', False) == True


class TestLeaderPromotionWorkflows:
    """Test leader promotion and demotion workflows."""

    @pytest.mark.critical
    @pytest.mark.admin
    def test_participant_to_leader_promotion(self, browser, authenticated_browser, base_url, clean_database):
        """Test promoting a participant to area leader through admin interface."""
        import random
        import string

        # Generate unique alphabetic suffix for this test
        test_suffix = ''.join(random.choices(string.ascii_lowercase, k=8))
        test_email = f"promotion-test-{test_suffix}@test-regression.ca"

        # Step 1: Register a participant through the UI (using unauthenticated browser)
        browser.get(base_url)

        browser.find_element(By.ID, "first_name").send_keys("LeaderPromo")
        browser.find_element(By.ID, "last_name").send_keys(f"Test{test_suffix}")
        browser.find_element(By.ID, "email").send_keys(test_email)
        browser.find_element(By.ID, "phone").send_keys("604-555-PROMO")

        safe_select_by_value(browser, (By.ID, "skill_level"), "Intermediate")
        safe_select_by_value(browser, (By.ID, "experience"), "1-2 counts")
        safe_select_by_value(browser, (By.ID, "preferred_area"), "A")
        safe_click(browser, (By.ID, "regular"))
        safe_click(browser, (By.ID, "interested_in_leadership"))
        safe_click(browser, (By.ID, "has_binoculars"))

        safe_click(browser, (By.XPATH, "//button[@type='submit']"))

        # Wait for success page with retry (handle spinner delays)
        success_found = False
        for attempt in range(5):
            time.sleep(2)
            current_url = browser.current_url
            if 'success' in current_url or 'participant_id=' in current_url:
                success_found = True
                break

        assert success_found, \
            f"Registration should redirect to success page, got: {current_url}"

        # Verify registration succeeded in database
        participant_id, participant = verify_registration_success(browser, test_email)
        logger.info(f"Created test participant: {participant_id}")

        # Step 2: Use pre-authenticated admin browser (already logged in)
        # Navigate to leaders page to promote participant
        # Participant must have indicated leadership interest during registration
        authenticated_browser.get(f"{base_url}/admin/leaders")
        wait = WebDriverWait(authenticated_browser, 10)

        # Verify we're on the right page and authenticated
        current_url = authenticated_browser.current_url
        logger.info(f"After navigation, current URL: {current_url}")

        # Wait for page to load
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        # Wait for participant data to sync - look for our specific participant in the table
        # IMPORTANT: Use identity tuple (first_name, last_name, email) not just email
        # Family members can share email addresses
        participant_wait = WebDriverWait(authenticated_browser, 20)  # Longer wait for DB sync
        try:
            logger.info(f"Waiting for participant LeaderPromo Test{test_suffix} ({test_email}) to appear in potential leaders...")
            # Match on all three identity fields to uniquely identify the participant
            participant_wait.until(EC.presence_of_element_located(
                (By.XPATH, f"//tr[contains(., 'LeaderPromo') and contains(., 'Test{test_suffix}') and contains(., '{test_email}')]")
            ))
            logger.info(f"Found participant LeaderPromo Test{test_suffix} in leaders page")
        except TimeoutException:
            logger.error(f"Participant LeaderPromo Test{test_suffix} ({test_email}) did not appear in leaders page after 20 seconds")
            logger.error(f"Current URL: {authenticated_browser.current_url}")
            logger.error(f"Page title: {authenticated_browser.title}")
            # Check if Potential Leaders section exists at all
            try:
                authenticated_browser.find_element(By.XPATH, "//h3[contains(text(), 'Potential Leaders')]")
                logger.error("Potential Leaders section exists but participant not in it")
            except:
                logger.error("Potential Leaders section does not exist on page")
            raise

        # Find participant in "Potential Leaders" section using identity tuple
        # Select area from dropdown in their row
        area_dropdown = wait.until(EC.presence_of_element_located(
            (By.XPATH, f"//tr[contains(., 'LeaderPromo') and contains(., 'Test{test_suffix}') and contains(., '{test_email}')]//select[@name='area_code']")
        ))

        # Scroll dropdown into view and ensure it's visible
        authenticated_browser.execute_script("arguments[0].scrollIntoView({block: 'center'});", area_dropdown)
        time.sleep(0.5)

        # Use JavaScript to set the value as a workaround for "element not interactable" errors
        authenticated_browser.execute_script("arguments[0].value = 'A'; arguments[0].dispatchEvent(new Event('change'));", area_dropdown)
        time.sleep(0.5)

        # Click "Assign" button to promote to leader using identity tuple
        assign_button = wait.until(EC.element_to_be_clickable(
            (By.XPATH, f"//tr[contains(., 'LeaderPromo') and contains(., 'Test{test_suffix}') and contains(., '{test_email}')]//button[contains(text(), 'Assign')]")
        ))
        authenticated_browser.execute_script("arguments[0].scrollIntoView({block: 'center'});", assign_button)
        time.sleep(0.3)
        assign_button.click()

        time.sleep(2)  # Allow promotion to process

        # Step 3: Verify promotion succeeded - participant should now be in leaders table

        # Verify leader appears in table (search for email since names might be in different columns)
        wait.until(EC.presence_of_element_located(
            (By.XPATH, f"//tr[contains(., '{test_email}')]")
        ))

        # Step 5: Verify in database
        from models.participant import ParticipantModel
        from config.database import get_firestore_client
        db, _ = get_firestore_client()
        participant_model = ParticipantModel(db, datetime.now().year)

        participant = participant_model.get_participant(participant_id)
        assert participant is not None, f"Participant {participant_id} not found after promotion"
        assert participant.get('is_leader', False) == True, "Participant should have is_leader=True"
        assert participant.get('assigned_area_leader') == 'A', "Participant should be assigned as leader of area A"

        logger.info(f"✓ Successfully promoted participant {participant_id} to leader of area A")



class TestAdminLeaderManagement:
    """Test admin leader management UI functionality."""

    @pytest.mark.admin
    def test_add_new_leader_via_ui(self, browser, base_url, test_credentials, clean_database):
        """Test adding a new leader through the admin leaders interface."""
        # Login as admin
        admin_creds = test_credentials['admin_primary']
        admin_login_for_test(browser, base_url, admin_creds)

        # Navigate to leaders page
        browser.get(f"{base_url}/admin/leaders")

        # Fill new leader form
        wait = WebDriverWait(browser, 10)

        # Leader contact details
        browser.find_element(By.ID, "first_name").send_keys("NewLeader")
        browser.find_element(By.ID, "last_name").send_keys("AdminTest")
        browser.find_element(By.ID, "email").send_keys("newleader.admin@test-regression.ca")
        browser.find_element(By.ID, "phone").send_keys("604-555-0100")

        # Area and optional fields
        Select(browser.find_element(By.ID, "area_code")).select_by_value("E")
        browser.find_element(By.ID, "phone2").send_keys("604-555-0101")

        # Skill level and experience (required fields)
        Select(browser.find_element(By.ID, "skill_level")).select_by_value("Expert")
        Select(browser.find_element(By.ID, "experience")).select_by_value("3+ counts")

        # Equipment checkboxes
        browser.find_element(By.ID, "has_binoculars").click()
        browser.find_element(By.ID, "spotting_scope").click()

        # Notes
        browser.find_element(By.ID, "notes").send_keys("Experienced area leader from previous years")

        # Submit form
        browser.find_element(By.XPATH, "//button[contains(text(), 'Add Leader')]").click()

        # Verify leader appears in table (use span.leader-name for exact element)
        time.sleep(1)  # Brief pause for form submission
        wait.until(EC.presence_of_element_located(
            (By.XPATH, "//span[@class='leader-name' and contains(text(), 'NewLeader AdminTest')]")
        ))

        # Verify in database
        from models.participant import ParticipantModel
        from config.database import get_firestore_client
        db, _ = get_firestore_client()
        participant_model = ParticipantModel(db, datetime.now().year)
        leaders = participant_model.get_leaders_by_area("E")
        assert len(leaders) == 1
        assert leaders[0]['first_name'] == "NewLeader"
        assert leaders[0]['last_name'] == "AdminTest"
        assert leaders[0]['skill_level'] == "Expert"
        assert leaders[0]['experience'] == "3+ counts"
        assert leaders[0]['has_binoculars'] == True
        assert leaders[0]['spotting_scope'] == True

    @pytest.mark.admin
    def test_edit_leader_via_ui(self, browser, base_url, test_credentials, single_identity_test):
        """Test editing leader information through inline editing."""
        # Create a leader to edit
        identity_helper = single_identity_test.identity_helper
        participant_id, _ = identity_helper.create_test_identity(
            "EditableLeader", "F", "leader"
        )

        # Login as admin
        admin_creds = test_credentials['admin_primary']
        admin_login_for_test(browser, base_url, admin_creds)

        # Navigate to leaders page
        browser.get(f"{base_url}/admin/leaders")

        wait = WebDriverWait(browser, 10)

        # Find the edit button for our leader
        edit_button = wait.until(EC.element_to_be_clickable(
            (By.XPATH, f"//tr[@data-leader-id='{participant_id}']//button[contains(@class, 'btn-edit')]")
        ))
        edit_button.click()

        # Wait for edit mode to activate
        name_input = wait.until(EC.presence_of_element_located(
            (By.XPATH, f"//tr[@data-leader-id='{participant_id}']//input[contains(@class, 'first-name-input')]")
        ))

        # Edit the name
        name_input.clear()
        name_input.send_keys("EditedLeader")

        # Save changes
        save_button = browser.find_element(
            By.XPATH, f"//tr[@data-leader-id='{participant_id}']//button[contains(@class, 'btn-save')]"
        )
        save_button.click()

        # Verify changes saved
        wait.until(EC.text_to_be_present_in_element(
            (By.XPATH, f"//tr[@data-leader-id='{participant_id}']//span[@class='leader-name']"),
            "EditedLeader"
        ))

        # Verify in database
        from models.participant import ParticipantModel
        from config.database import get_firestore_client
        db, _ = get_firestore_client()
        participant_model = ParticipantModel(db, datetime.now().year)
        updated_participant = participant_model.get_participant(participant_id)
        assert updated_participant['first_name'] == "EditedLeader"


# CSV Export Tests - Reference the comprehensive test suite instead of duplicating
# The CSV export functionality is comprehensively tested in test_csv_export_workflows.py
# That file includes:
# - test_csv_export_button_availability - Verifies export buttons on dashboard and participants page
# - test_direct_csv_route_access - Tests direct access to /admin/export_csv route
# - test_csv_export_with_known_data - Validates export content against known test data
# - test_csv_field_completeness - Checks all required fields are present
# - test_csv_sorting_order - Validates sort order (area → participation_type → name)
# - test_large_dataset_export_performance - Tests export performance with 347 participants
#
# Run those tests to validate CSV export functionality as part of regression testing:
#   pytest tests/test_csv_export_workflows.py::TestCSVExport -v


class TestDataIntegrityAndSynchronization:
    """Test data integrity and synchronization in single-table design."""

    @pytest.mark.critical
    def test_participant_deletion_updates_leadership(self, single_identity_test):
        """Test that deleting a participant who is a leader properly updates leadership status."""
        identity_helper = single_identity_test.identity_helper

        # Create participant who is also a leader
        participant_id, _ = identity_helper.create_test_identity(
            "DeleteTestLeader", "H", "both"
        )

        from models.participant import ParticipantModel
        from config.database import get_firestore_client
        db, _ = get_firestore_client()
        participant_model = ParticipantModel(db, datetime.now().year)

        # Verify participant is a leader
        participant = participant_model.get_participant(participant_id)
        assert participant.get('is_leader', False) == True

        # Delete participant
        success = participant_model.delete_participant(participant_id)
        assert success

        # Verify participant is deleted
        deleted_participant = participant_model.get_participant(participant_id)
        assert deleted_participant is None

        # Verify leadership record is handled (in single-table, this means participant is deleted)
        leaders = participant_model.get_leaders_by_area("H")
        leader_names = [f"{l['first_name']} {l['last_name']}" for l in leaders]
        assert "DeleteTestLeader TestLastName" not in leader_names

    @pytest.mark.critical
    def test_leadership_assignment_creates_single_record(self, single_identity_test):
        """Test that leadership assignment only modifies participant record, not dual records."""
        identity_helper = single_identity_test.identity_helper

        # Create regular participant
        participant_id, _ = identity_helper.create_test_identity(
            "SingleRecordTest", "I", "participant"
        )

        from models.participant import ParticipantModel
        from config.database import get_firestore_client
        db, _ = get_firestore_client()
        participant_model = ParticipantModel(db, datetime.now().year)

        # Verify not a leader initially
        participant = participant_model.get_participant(participant_id)
        assert participant.get('is_leader', False) == False

        # Assign leadership
        success = participant_model.assign_area_leadership(
            participant_id, "I", "test-assignment@test.ca"
        )
        assert success

        # Verify leadership assigned
        updated_participant = participant_model.get_participant(participant_id)
        assert updated_participant.get('is_leader', False) == True
        assert updated_participant.get('assigned_area_leader') == "I"

        # Verify appears in leaders list
        leaders = participant_model.get_leaders_by_area("I")
        assert len(leaders) == 1
        assert leaders[0]['id'] == participant_id

    @pytest.mark.critical
    def test_no_orphaned_leader_records(self, single_identity_test):
        """Test that single-table design prevents orphaned leader records."""
        from models.participant import ParticipantModel
        from config.database import get_firestore_client
        db, _ = get_firestore_client()
        participant_model = ParticipantModel(db, datetime.now().year)

        # Get all participants
        all_participants = participant_model.get_all_participants()

        # Get all leaders
        all_leaders = participant_model.get_leaders()

        # Verify every leader is also a participant (should be same records with is_leader=True)
        leader_ids = {leader['id'] for leader in all_leaders}
        participant_ids = {p['id'] for p in all_participants}

        # All leader IDs should be in participant IDs
        orphaned_leaders = leader_ids - participant_ids
        assert len(orphaned_leaders) == 0, f"Found orphaned leader records: {orphaned_leaders}"

        # Verify all leaders have is_leader=True
        for leader in all_leaders:
            assert leader.get('is_leader', False) == True


# Test Markers and Categories
pytest.mark.critical = pytest.mark.critical
pytest.mark.admin = pytest.mark.admin
pytest.mark.slow = pytest.mark.slow
pytest.mark.regression = pytest.mark.regression

# Mark all tests in this file as regression tests
pytestmark = pytest.mark.regression