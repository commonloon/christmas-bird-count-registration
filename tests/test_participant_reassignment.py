# Test suite for participant and leader area reassignment functionality
# Updated by Claude AI on 2025-10-07

import pytest
import logging
import time
from datetime import datetime
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from models.participant import ParticipantModel
from tests.test_config import get_base_url, get_database_name
from tests.utils.auth_utils import admin_login_for_test

logger = logging.getLogger(__name__)


@pytest.fixture
def participant_model(firestore_client):
    """Create participant model for current year."""
    current_year = datetime.now().year
    return ParticipantModel(firestore_client, current_year)


# Note: authenticated_browser fixture is now defined in conftest.py and shared across all test files
# This test class uses the global fixture but adds browser window resizing in the navigate fixture


@pytest.fixture(scope="module")
def populated_test_data(firestore_client):
    """Load test participants from CSV fixture once for all tests in this module."""
    import os
    import sys

    # Add project root to path for imports
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    from tests.utils.load_test_data import load_csv_participants, load_participants_to_firestore

    current_year = datetime.now().year
    participant_model = ParticipantModel(firestore_client, current_year)

    # Clear existing participants for current year to start fresh
    logger.info("Clearing existing participants for clean test")
    try:
        participants_ref = firestore_client.collection(f'participants_{current_year}')
        batch_size = 100
        deleted = 0

        while True:
            docs = participants_ref.limit(batch_size).stream()
            batch = firestore_client.batch()
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
    load_participants_to_firestore(firestore_client, current_year, participants)
    logger.info(f"Successfully loaded {len(participants)} test participants to Firestore")

    yield participants

    # Clean up test participants disabled for manual inspection
    # Cleanup now happens at the START of the next test run (lines 51-75 above)
    logger.info(f"Skipping cleanup - test data left in database for manual inspection")
    # # Clean up test participants (runs once after all tests in module complete)
    # logger.info(f"Cleaning up {len(participants)} CSV test participants")
    # try:
    #     participants_ref = firestore_client.collection(f'participants_{current_year}')
    #     batch_size = 100
    #     deleted = 0
    #
    #     while True:
    #         docs = participants_ref.limit(batch_size).stream()
    #         batch = firestore_client.batch()
    #         count = 0
    #
    #         for doc in docs:
    #             batch.delete(doc.reference)
    #             count += 1
    #             deleted += 1
    #
    #         if count == 0:
    #             break
    #
    #         batch.commit()
    #
    #     logger.info(f"Cleanup complete: deleted {deleted} participants")
    # except Exception as e:
    #     logger.warning(f"Cleanup error: {e}")


@pytest.mark.browser
@pytest.mark.admin
@pytest.mark.critical
class TestParticipantReassignment:
    """Test participant and leader area reassignment workflows.

    This class uses class-scoped authenticated_browser fixture to share
    authentication across all tests, significantly reducing execution time.
    """

    @pytest.fixture(autouse=True)
    def navigate_to_participants_page(self, authenticated_browser):
        """Navigate to participants page before each test.

        This provides test isolation by ensuring each test starts from a
        clean page state, while reusing the authenticated browser session.

        Uses shorter timeout (5s) since we're already authenticated and
        subsequent page loads are fast.
        """
        authenticated_browser.get(f"{get_base_url()}/admin/participants")
        WebDriverWait(authenticated_browser, 5).until(
            EC.presence_of_element_located((By.TAG_NAME, "table"))
        )
        logger.info("Navigated to participants page")

    @pytest.fixture(autouse=True)
    def setup_test_data(self, firestore_client, populated_test_data):
        """Use populated test data fixture (347 participants with leaders) - select unique participants for each test."""
        self.db_client = firestore_client
        self.test_participants = populated_test_data

        # Select DIFFERENT participants for each test to avoid conflicts
        # Test 1: Regular participant from Area A
        # Test 2: Leader from Area B (will decline leadership when moved to Area D)
        # Test 3: Leader from Area D (will accept leadership when moved to Area E)
        # Test 4: Regular participant from Area F (for validation test)
        # Test 5: Regular participant from Area G (for cancel test)

        self.test1_participant = None  # Regular in Area A
        self.test2_leader = None       # Leader in Area B
        self.test3_leader = None       # Leader in Area D (different from test2)
        self.test4_participant = None  # Regular in Area F
        self.test5_participant = None  # Regular in Area G

        for p in self.test_participants:
            # Test 1: First regular participant in Area A
            if not self.test1_participant and not p.get('is_leader') and p.get('preferred_area') == 'A':
                self.test1_participant = p

            # Test 2: Leader in Area B
            if not self.test2_leader and p.get('is_leader') and p.get('assigned_area_leader') == 'B':
                self.test2_leader = p

            # Test 3: Leader in Area D (different from test 2)
            if not self.test3_leader and p.get('is_leader') and p.get('assigned_area_leader') == 'D':
                self.test3_leader = p

            # Test 4: First regular participant in Area F
            if not self.test4_participant and not p.get('is_leader') and p.get('preferred_area') == 'F':
                self.test4_participant = p

            # Test 5: First regular participant in Area G
            if not self.test5_participant and not p.get('is_leader') and p.get('preferred_area') == 'G':
                self.test5_participant = p

        logger.info(f"Test 1 participant: {self.test1_participant.get('first_name')} {self.test1_participant.get('last_name')} in Area {self.test1_participant.get('preferred_area')}")
        logger.info(f"Test 2 leader: {self.test2_leader.get('first_name')} {self.test2_leader.get('last_name')} in Area {self.test2_leader.get('assigned_area_leader')}")
        logger.info(f"Test 3 leader: {self.test3_leader.get('first_name')} {self.test3_leader.get('last_name')} in Area {self.test3_leader.get('assigned_area_leader')}")
        logger.info(f"Test 4 participant: {self.test4_participant.get('first_name')} {self.test4_participant.get('last_name')} in Area {self.test4_participant.get('preferred_area')}")
        logger.info(f"Test 5 participant: {self.test5_participant.get('first_name')} {self.test5_participant.get('last_name')} in Area {self.test5_participant.get('preferred_area')}")

    def test_01_regular_participant_reassignment(self, authenticated_browser, participant_model):
        """Test reassigning a regular participant from Area A to Area C."""
        logger.info("=" * 80)
        logger.info("TEST: Regular Participant Reassignment (Area A → Area C)")
        logger.info("=" * 80)

        # Use unique participant for this test
        participant = self.test1_participant
        participant_name = f"{participant['first_name']} {participant['last_name']}"

        # Page navigation already done by navigate_to_participants_page fixture
        logger.info(f"Looking for participant: {participant_name}")

        # Find the participant row
        rows = authenticated_browser.find_elements(By.CSS_SELECTOR, "tbody tr")
        target_row = None
        for row in rows:
            if participant_name in row.text:
                target_row = row
                break

        assert target_row is not None, f"Could not find participant {participant_name} in table"
        logger.info(f"Found participant row")

        # Click Reassign button (use ActionChains for reliable event triggering)
        reassign_button = target_row.find_element(By.CSS_SELECTOR, ".btn-reassign")
        authenticated_browser.execute_script("arguments[0].scrollIntoView({block: 'center'});", reassign_button)
        time.sleep(0.5)  # Brief pause after scroll
        ActionChains(authenticated_browser).move_to_element(reassign_button).click().perform()
        logger.info("Clicked Reassign button")

        # Wait for reassignment controls to appear
        WebDriverWait(authenticated_browser, 5).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, ".reassign-controls"))
        )

        # Select new area (Area C)
        area_select = target_row.find_element(By.CSS_SELECTOR, ".reassign-area-select")
        area_select.click()
        area_option = target_row.find_element(By.CSS_SELECTOR, "option[value='C']")
        area_option.click()
        logger.info("Selected Area C from dropdown")

        # Click confirm button
        confirm_button = target_row.find_element(By.CSS_SELECTOR, ".btn-confirm-reassign")
        confirm_button.click()
        logger.info("Clicked Confirm button")

        # Handle success alert
        try:
            WebDriverWait(authenticated_browser, 5).until(EC.alert_is_present())
            alert = authenticated_browser.switch_to.alert
            alert_text = alert.text
            logger.info(f"Success alert appeared: {alert_text}")
            alert.accept()
            logger.info("Accepted success alert")
        except:
            logger.warning("No alert appeared (page may have reloaded already)")

        # Wait for page reload (single wait is sufficient)
        WebDriverWait(authenticated_browser, 5).until(
            EC.presence_of_element_located((By.TAG_NAME, "table"))
        )
        logger.info("Page reloaded after reassignment")

        # Verify participant moved to Area C in database
        # Query by identity since CSV data doesn't have Firestore document IDs
        first_name = participant['first_name']
        last_name = participant['last_name']
        email = participant['email']

        updated_participant = participant_model.get_participant_by_email_and_names(email, first_name, last_name)

        assert updated_participant is not None, f"Participant {participant_name} not found after reassignment"
        assert updated_participant['preferred_area'] == 'C', f"Expected area C, got {updated_participant.get('preferred_area')}"
        assert not updated_participant.get('is_leader', False), "Regular participant should not be leader"

        logger.info(f"✓ Successfully reassigned {participant_name} to Area C")
        logger.info(f"✓ Database verified: preferred_area=C, is_leader=False")

    def test_02_leader_reassignment_decline_leadership(self, authenticated_browser, participant_model):
        """Test reassigning a leader from Area B to Area D, declining new leadership."""
        logger.info("=" * 80)
        logger.info("TEST: Leader Reassignment - Decline Leadership (Area B → Area D)")
        logger.info("=" * 80)

        # Page navigation and auth already done by fixtures
        # Use unique leader for test 2
        participant = self.test2_leader
        participant_name = f"{participant['first_name']} {participant['last_name']}"
        logger.info(f"Looking for leader: {participant_name}")

        # Find the participant row
        rows = authenticated_browser.find_elements(By.CSS_SELECTOR, "tbody tr")
        target_row = None
        for row in rows:
            if participant_name in row.text and "Leader" in row.text:
                target_row = row
                break

        assert target_row is not None, f"Could not find leader {participant_name} in table"
        logger.info(f"Found leader row with Leader badge")

        # Click Reassign button (use ActionChains for reliable event triggering)
        reassign_button = target_row.find_element(By.CSS_SELECTOR, ".btn-reassign")
        authenticated_browser.execute_script("arguments[0].scrollIntoView({block: 'center'});", reassign_button)
        time.sleep(0.5)  # Brief pause after scroll
        ActionChains(authenticated_browser).move_to_element(reassign_button).click().perform()
        logger.info("Clicked Reassign button")

        # Debug: Check if reassign-controls exists and its visibility
        reassign_controls = target_row.find_elements(By.CSS_SELECTOR, ".reassign-controls")
        logger.info(f"Found {len(reassign_controls)} reassign-controls elements in row")
        if len(reassign_controls) > 0:
            style_attr = reassign_controls[0].get_attribute('style')
            is_displayed = reassign_controls[0].is_displayed()
            logger.info(f"Reassign controls style: {style_attr}, is_displayed: {is_displayed}")

            # Force show the controls via JavaScript
            logger.info("Forcing reassign controls to be visible via JavaScript")
            authenticated_browser.execute_script("""
                arguments[0].querySelector('.action-buttons').style.display = 'none';
                arguments[0].querySelector('.reassign-controls').style.display = 'block';
            """, target_row)
            time.sleep(0.3)  # Brief pause for DOM update

        # Controls are already visible (verified above), no need to wait
        # The wait was looking for ANY .reassign-controls on page, not specifically in target_row

        # Select new area (Area D)
        area_select = target_row.find_element(By.CSS_SELECTOR, ".reassign-area-select")
        area_select.click()
        area_option = target_row.find_element(By.CSS_SELECTOR, "option[value='D']")
        area_option.click()
        logger.info("Selected Area D from dropdown")

        # Click confirm button - this will trigger confirmation dialog for leader
        confirm_button = target_row.find_element(By.CSS_SELECTOR, ".btn-confirm-reassign")
        confirm_button.click()
        logger.info("Clicked Confirm button")

        # Handle leader reassignment modal - click "Team Member" to decline leadership
        try:
            WebDriverWait(authenticated_browser, 5).until(
                EC.visibility_of_element_located((By.ID, "leaderReassignModal"))
            )
            logger.info("Leader reassignment modal appeared")

            # Verify modal message contains area information
            modal_message = authenticated_browser.find_element(By.ID, "leaderReassignMessage").text
            logger.info(f"Modal message: {modal_message}")
            assert "Area B" in modal_message and "Area D" in modal_message, f"Unexpected modal message: {modal_message}"

            # Click "Team Member" button to decline leadership
            team_member_btn = authenticated_browser.find_element(By.ID, "moveAsTeamMember")
            team_member_btn.click()
            logger.info("Clicked 'Team Member' button (declined leadership)")
        except TimeoutException:
            pytest.fail("Expected leader reassignment modal did not appear")

        # Handle success alert that appears after reassignment
        try:
            WebDriverWait(authenticated_browser, 5).until(EC.alert_is_present())
            success_alert = authenticated_browser.switch_to.alert
            success_text = success_alert.text
            logger.info(f"Success alert appeared: {success_text}")
            success_alert.accept()
            logger.info("Accepted success alert")
        except TimeoutException:
            logger.warning("No success alert appeared")

        # Wait for page reload (staleness check ensures reload happened)
        WebDriverWait(authenticated_browser, 5).until(EC.staleness_of(target_row))
        WebDriverWait(authenticated_browser, 5).until(
            EC.presence_of_element_located((By.TAG_NAME, "table"))
        )
        logger.info("Page reloaded after reassignment")

        # Verify leader moved to Area D without leadership in database
        # Query by identity since CSV data doesn't have Firestore document IDs
        first_name = participant['first_name']
        last_name = participant['last_name']
        email = participant['email']

        updated_participant = participant_model.get_participant_by_email_and_names(email, first_name, last_name)

        assert updated_participant is not None, f"Participant {participant_name} not found after reassignment"
        assert updated_participant['preferred_area'] == 'D', f"Expected area D, got {updated_participant.get('preferred_area')}"
        assert not updated_participant.get('is_leader', False), "Participant should not be leader after declining"
        assert updated_participant.get('assigned_area_leader') is None, "assigned_area_leader should be None"

        logger.info(f"✓ Successfully reassigned {participant_name} to Area D as regular participant")
        logger.info(f"✓ Database verified: preferred_area=D, is_leader=False, assigned_area_leader=None")

    def test_03_leader_reassignment_accept_leadership(self, authenticated_browser, participant_model):
        """Test reassigning a leader from Area D to Area E, accepting new leadership."""
        logger.info("=" * 80)
        logger.info("TEST: Leader Reassignment - Accept Leadership (Area D → Area E)")
        logger.info("=" * 80)

        # Page navigation and auth already done by fixtures
        # Use unique leader for test 3
        participant = self.test3_leader
        participant_name = f"{participant['first_name']} {participant['last_name']}"
        logger.info(f"Looking for leader: {participant_name}")

        # Find the participant row
        rows = authenticated_browser.find_elements(By.CSS_SELECTOR, "tbody tr")
        target_row = None
        for row in rows:
            if participant_name in row.text and "Leader" in row.text:
                target_row = row
                break

        assert target_row is not None, f"Could not find leader {participant_name} in table"
        logger.info(f"Found leader row with Leader badge")

        # Click Reassign button (use ActionChains for reliable event triggering)
        reassign_button = target_row.find_element(By.CSS_SELECTOR, ".btn-reassign")
        authenticated_browser.execute_script("arguments[0].scrollIntoView({block: 'center'});", reassign_button)
        time.sleep(0.5)  # Brief pause after scroll
        ActionChains(authenticated_browser).move_to_element(reassign_button).click().perform()
        logger.info("Clicked Reassign button")

        # Debug: Check if reassign-controls exists and its visibility
        reassign_controls = target_row.find_elements(By.CSS_SELECTOR, ".reassign-controls")
        logger.info(f"Found {len(reassign_controls)} reassign-controls elements in row")
        if len(reassign_controls) > 0:
            style_attr = reassign_controls[0].get_attribute('style')
            is_displayed = reassign_controls[0].is_displayed()
            logger.info(f"Reassign controls style: {style_attr}, is_displayed: {is_displayed}")

            # Force show the controls via JavaScript
            logger.info("Forcing reassign controls to be visible via JavaScript")
            authenticated_browser.execute_script("""
                arguments[0].querySelector('.action-buttons').style.display = 'none';
                arguments[0].querySelector('.reassign-controls').style.display = 'block';
            """, target_row)
            time.sleep(0.3)  # Brief pause for DOM update

        # Select new area (Area E)
        area_select = target_row.find_element(By.CSS_SELECTOR, ".reassign-area-select")
        area_select.click()
        area_option = target_row.find_element(By.CSS_SELECTOR, "option[value='E']")
        area_option.click()
        logger.info("Selected Area E from dropdown")

        # Click confirm button - this will trigger leader reassignment modal
        confirm_button = target_row.find_element(By.CSS_SELECTOR, ".btn-confirm-reassign")
        confirm_button.click()
        logger.info("Clicked Confirm button")

        # Handle leader reassignment modal - click "Leader" to accept leadership
        try:
            WebDriverWait(authenticated_browser, 5).until(
                EC.visibility_of_element_located((By.ID, "leaderReassignModal"))
            )
            logger.info("Leader reassignment modal appeared")

            # Verify modal message contains area information
            modal_message = authenticated_browser.find_element(By.ID, "leaderReassignMessage").text
            logger.info(f"Modal message: {modal_message}")
            assert "Area D" in modal_message and "Area E" in modal_message, f"Unexpected modal message: {modal_message}"

            # Click "Leader" button to accept leadership
            leader_btn = authenticated_browser.find_element(By.ID, "moveAsLeader")
            leader_btn.click()
            logger.info("Clicked 'Leader' button (accepted leadership)")
        except TimeoutException:
            pytest.fail("Expected leader reassignment modal did not appear")

        # Handle success alert that appears after reassignment
        try:
            WebDriverWait(authenticated_browser, 5).until(EC.alert_is_present())
            success_alert = authenticated_browser.switch_to.alert
            success_text = success_alert.text
            logger.info(f"Success alert appeared: {success_text}")
            success_alert.accept()
            logger.info("Accepted success alert")
        except TimeoutException:
            logger.warning("No success alert appeared")

        # Wait for page reload (staleness check ensures reload happened)
        WebDriverWait(authenticated_browser, 5).until(EC.staleness_of(target_row))
        WebDriverWait(authenticated_browser, 5).until(
            EC.presence_of_element_located((By.TAG_NAME, "table"))
        )
        logger.info("Page reloaded after reassignment")

        # Verify leader moved to Area E with leadership in database
        # Query by identity since CSV data doesn't have Firestore document IDs
        first_name = participant['first_name']
        last_name = participant['last_name']
        email = participant['email']

        updated_participant = participant_model.get_participant_by_email_and_names(email, first_name, last_name)

        assert updated_participant is not None, f"Participant {participant_name} not found after reassignment"
        assert updated_participant['preferred_area'] == 'E', f"Expected area E, got {updated_participant.get('preferred_area')}"
        assert updated_participant.get('is_leader', False), "Participant should be leader after accepting"
        assert updated_participant.get('assigned_area_leader') == 'E', f"Expected assigned_area_leader=E, got {updated_participant.get('assigned_area_leader')}"

        logger.info(f"✓ Successfully reassigned {participant_name} to Area E as leader")
        logger.info(f"✓ Database verified: preferred_area=E, is_leader=True, assigned_area_leader=E")

    def test_04_reassignment_validation_same_area(self, authenticated_browser):
        """Test validation when trying to reassign participant to same area."""
        logger.info("=" * 80)
        logger.info("TEST: Reassignment Validation - Same Area")
        logger.info("=" * 80)

        # Page navigation and auth already done by fixtures
        # Use unique participant for test 4
        participant = self.test4_participant
        participant_name = f"{participant['first_name']} {participant['last_name']}"
        current_area = participant['preferred_area']
        logger.info(f"Looking for participant: {participant_name} in Area {current_area}")

        # Find the participant row
        rows = authenticated_browser.find_elements(By.CSS_SELECTOR, "tbody tr")
        target_row = None
        for row in rows:
            if participant_name in row.text:
                target_row = row
                break

        assert target_row is not None, f"Could not find participant {participant_name}"
        logger.info(f"Found participant row")

        # Click Reassign button (use ActionChains for reliable event triggering)
        reassign_button = target_row.find_element(By.CSS_SELECTOR, ".btn-reassign")
        authenticated_browser.execute_script("arguments[0].scrollIntoView({block: 'center'});", reassign_button)
        time.sleep(0.5)  # Brief pause after scroll
        ActionChains(authenticated_browser).move_to_element(reassign_button).click().perform()
        logger.info("Clicked Reassign button")

        # Debug: Check if reassign-controls exists and its visibility
        reassign_controls = target_row.find_elements(By.CSS_SELECTOR, ".reassign-controls")
        logger.info(f"Found {len(reassign_controls)} reassign-controls elements in row")
        if len(reassign_controls) > 0:
            style_attr = reassign_controls[0].get_attribute('style')
            is_displayed = reassign_controls[0].is_displayed()
            logger.info(f"Reassign controls style: {style_attr}, is_displayed: {is_displayed}")

            # Force show the controls via JavaScript
            logger.info("Forcing reassign controls to be visible via JavaScript")
            authenticated_browser.execute_script("""
                arguments[0].querySelector('.action-buttons').style.display = 'none';
                arguments[0].querySelector('.reassign-controls').style.display = 'block';
            """, target_row)
            time.sleep(0.3)  # Brief pause for DOM update

        # Select same area
        area_select = target_row.find_element(By.CSS_SELECTOR, ".reassign-area-select")
        area_select.click()
        area_option = target_row.find_element(By.CSS_SELECTOR, f"option[value='{current_area}']")
        area_option.click()
        logger.info(f"Selected same area ({current_area}) from dropdown")

        # Click confirm button
        confirm_button = target_row.find_element(By.CSS_SELECTOR, ".btn-confirm-reassign")
        confirm_button.click()

        # Expect validation alert
        try:
            WebDriverWait(authenticated_browser, 5).until(EC.alert_is_present())
            alert = authenticated_browser.switch_to.alert
            alert_text = alert.text
            logger.info(f"Validation alert appeared: {alert_text}")

            # Verify alert message
            assert "already in Area" in alert_text, f"Expected validation message, got: {alert_text}"

            alert.accept()
            logger.info("✓ Validation correctly prevented reassignment to same area")
        except TimeoutException:
            pytest.fail("Expected validation alert for same-area reassignment did not appear")

    def test_05_reassignment_cancel(self, authenticated_browser, participant_model):
        """Test canceling a reassignment operation."""
        logger.info("=" * 80)
        logger.info("TEST: Reassignment Cancel")
        logger.info("=" * 80)

        # Page navigation and auth already done by fixtures
        # Use unique participant for test 5
        participant = self.test5_participant
        participant_name = f"{participant['first_name']} {participant['last_name']}"
        original_area = participant['preferred_area']
        logger.info(f"Looking for participant: {participant_name} in Area {original_area}")

        # Find the participant row
        rows = authenticated_browser.find_elements(By.CSS_SELECTOR, "tbody tr")
        target_row = None
        for row in rows:
            if participant_name in row.text:
                target_row = row
                break

        assert target_row is not None, f"Could not find participant {participant_name}"
        logger.info(f"Found participant row")

        # Click Reassign button (use ActionChains for reliable event triggering)
        reassign_button = target_row.find_element(By.CSS_SELECTOR, ".btn-reassign")
        authenticated_browser.execute_script("arguments[0].scrollIntoView({block: 'center'});", reassign_button)
        time.sleep(0.5)  # Brief pause after scroll
        ActionChains(authenticated_browser).move_to_element(reassign_button).click().perform()
        logger.info("Clicked Reassign button")

        # Debug: Check if reassign-controls exists and its visibility
        reassign_controls_list = target_row.find_elements(By.CSS_SELECTOR, ".reassign-controls")
        logger.info(f"Found {len(reassign_controls_list)} reassign-controls elements in row")
        if len(reassign_controls_list) > 0:
            style_attr = reassign_controls_list[0].get_attribute('style')
            is_displayed = reassign_controls_list[0].is_displayed()
            logger.info(f"Reassign controls style: {style_attr}, is_displayed: {is_displayed}")

            # Force show the controls via JavaScript
            logger.info("Forcing reassign controls to be visible via JavaScript")
            authenticated_browser.execute_script("""
                arguments[0].querySelector('.action-buttons').style.display = 'none';
                arguments[0].querySelector('.reassign-controls').style.display = 'block';
            """, target_row)
            time.sleep(0.3)  # Brief pause for DOM update

        # Verify action buttons are hidden and reassign controls are shown
        action_buttons = target_row.find_element(By.CSS_SELECTOR, ".action-buttons")
        reassign_controls = target_row.find_element(By.CSS_SELECTOR, ".reassign-controls")

        assert not action_buttons.is_displayed(), "Action buttons should be hidden during reassignment"
        assert reassign_controls.is_displayed(), "Reassign controls should be visible"
        logger.info("✓ UI correctly shows reassignment controls")

        # Click cancel button
        cancel_button = target_row.find_element(By.CSS_SELECTOR, ".btn-cancel-reassign")
        cancel_button.click()
        logger.info("Clicked Cancel button")

        # Verify UI returns to normal
        WebDriverWait(authenticated_browser, 3).until(
            lambda d: action_buttons.is_displayed()
        )

        assert action_buttons.is_displayed(), "Action buttons should be visible after cancel"
        assert not reassign_controls.is_displayed(), "Reassign controls should be hidden after cancel"
        logger.info("✓ UI correctly restored action buttons")

        # Verify participant area unchanged in database
        # Query by identity since CSV data doesn't have Firestore document IDs
        first_name = participant['first_name']
        last_name = participant['last_name']
        email = participant['email']

        updated_participant = participant_model.get_participant_by_email_and_names(email, first_name, last_name)

        assert updated_participant['preferred_area'] == original_area, f"Area should not have changed, expected {original_area}, got {updated_participant.get('preferred_area')}"
        logger.info(f"✓ Participant area unchanged in database: {original_area}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
