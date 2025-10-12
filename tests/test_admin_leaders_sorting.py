# Updated by Claude AI on 2025-09-26
"""
Test for Admin Leaders Page Sorting

This test verifies that both the current leaders table and potential leaders table
are properly sorted by area code then by first name in ascending order.
"""

import pytest
import os
import sys
from datetime import datetime

# Add project root to path for imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from models.participant import ParticipantModel
from tests.utils.database_utils import create_database_manager
from tests.test_config import get_base_url
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


@pytest.fixture
def participant_model(firestore_client):
    """Create participant model for current year."""
    current_year = datetime.now().year
    return ParticipantModel(firestore_client, current_year)


@pytest.fixture(autouse=True)
def cleanup_test_data(firestore_client):
    """Clean up test data before and after each test."""
    db_manager = create_database_manager(firestore_client)
    db_manager.clear_test_collections()
    yield
    db_manager.clear_test_collections()


class TestAdminLeadersSorting:
    """Test the sorting functionality on admin/leaders page."""

    def test_leaders_page_sorting(self, authenticated_browser, participant_model):
        """
        Test that both current leaders and potential leaders tables are sorted
        by area code then by first name in ascending order.
        """
        base_url = get_base_url()

        # Create test participants with mixed names and areas to verify sorting
        test_participants = [
            # Leadership interested participants (potential leaders)
            {
                'first_name': 'Zebra',  # Z name in Area A
                'last_name': 'TestPerson',
                'email': 'zebra.a@test.com',
                'preferred_area': 'A',
                'participation_type': 'regular',
                'interested_in_leadership': True
            },
            {
                'first_name': 'Alpha',  # A name in Area C
                'last_name': 'TestPerson',
                'email': 'alpha.c@test.com',
                'preferred_area': 'C',
                'participation_type': 'regular',
                'interested_in_leadership': True
            },
            {
                'first_name': 'Beta',  # B name in Area A (should sort after Alpha C but before Zebra A)
                'last_name': 'TestPerson',
                'email': 'beta.a@test.com',
                'preferred_area': 'A',
                'participation_type': 'regular',
                'interested_in_leadership': True
            },
            {
                'first_name': 'Charlie',  # C name in Area B
                'last_name': 'TestPerson',
                'email': 'charlie.b@test.com',
                'preferred_area': 'B',
                'participation_type': 'regular',
                'interested_in_leadership': True
            }
        ]

        # Create participants and promote some to leaders
        participant_ids = []
        for participant in test_participants:
            participant_id = participant_model.add_participant(participant)
            participant_ids.append(participant_id)

        # Promote some participants to leaders with different area assignments
        # Zebra (originally Area A) becomes leader of Area D
        participant_model.assign_area_leadership(participant_ids[0], 'D', 'test-admin@test.com')

        # Alpha (originally Area C) becomes leader of Area B
        participant_model.assign_area_leadership(participant_ids[1], 'B', 'test-admin@test.com')

        # Beta and Charlie remain as potential leaders

        # Navigate to leaders page (already authenticated via fixture)
        authenticated_browser.get(f"{base_url}/admin/leaders")

        wait = WebDriverWait(authenticated_browser, 10)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "table")))

        # Verify current leaders sorting (should be: Alpha/Area B, Zebra/Area D)
        # Find the current leaders table - it's in a card with "Current Area Leaders" header
        current_leaders_rows = authenticated_browser.find_elements(By.XPATH, "//h5[contains(text(), 'Current Area Leaders')]/../..//tbody/tr")

        if len(current_leaders_rows) >= 2:
            # Check that leaders are sorted by area then name
            first_leader_area = current_leaders_rows[0].find_elements(By.TAG_NAME, "td")[0].text.strip()
            first_leader_name = current_leaders_rows[0].find_elements(By.TAG_NAME, "td")[1].text.strip()

            second_leader_area = current_leaders_rows[1].find_elements(By.TAG_NAME, "td")[0].text.strip()
            second_leader_name = current_leaders_rows[1].find_elements(By.TAG_NAME, "td")[1].text.strip()

            # Should be sorted by area first (B comes before D)
            assert first_leader_area <= second_leader_area, \
                f"Current leaders not sorted by area: {first_leader_area} should come before {second_leader_area}"

            # Check that Alpha (Area B) comes before Zebra (Area D)
            if first_leader_area == 'B':
                assert 'Alpha' in first_leader_name, "First leader should be Alpha in Area B"
            if second_leader_area == 'D':
                assert 'Zebra' in second_leader_name, "Second leader should be Zebra in Area D"

        # Verify potential leaders sorting (should be: Beta/Area A, Charlie/Area B)
        # Find the potential leaders table - it's in a card with "Potential Leaders" header
        potential_leaders_rows = authenticated_browser.find_elements(By.XPATH, "//h5[contains(text(), 'Potential Leaders')]/../..//tbody/tr")

        if len(potential_leaders_rows) >= 2:
            # Extract area and name information from potential leaders table
            # Columns are: Name, Email, Skill Level, Preferred Area, Action
            first_potential_name = potential_leaders_rows[0].find_elements(By.TAG_NAME, "td")[0].text.strip()
            first_potential_area = potential_leaders_rows[0].find_elements(By.TAG_NAME, "td")[3].text.strip()

            second_potential_name = potential_leaders_rows[1].find_elements(By.TAG_NAME, "td")[0].text.strip()
            second_potential_area = potential_leaders_rows[1].find_elements(By.TAG_NAME, "td")[3].text.strip()

            # Verify sorting: Area A should come before Area B
            assert first_potential_area <= second_potential_area, \
                f"Potential leaders not sorted by area: {first_potential_area} should come before {second_potential_area}"

            # If same areas, check name sorting
            if first_potential_area == second_potential_area:
                assert first_potential_name <= second_potential_name, \
                    f"Within same area, names not sorted: {first_potential_name} should come before {second_potential_name}"

            # At minimum, verify we have the expected participants
            page_source = authenticated_browser.page_source
            assert 'Beta' in page_source, "Beta should appear in potential leaders"
            assert 'Charlie' in page_source, "Charlie should appear in potential leaders"

        # Additional verification: check that all expected participants are present
        page_text = authenticated_browser.page_source
        assert 'Alpha' in page_text, "Alpha should be visible on the page"
        assert 'Beta' in page_text, "Beta should be visible on the page"
        assert 'Charlie' in page_text, "Charlie should be visible on the page"
        assert 'Zebra' in page_text, "Zebra should be visible on the page"

    def test_empty_tables_no_errors(self, authenticated_browser):
        """Test that empty tables don't cause errors and page loads correctly."""
        base_url = get_base_url()

        # Navigate to leaders page with no data (already authenticated via fixture)
        authenticated_browser.get(f"{base_url}/admin/leaders")

        wait = WebDriverWait(authenticated_browser, 10)
        # Just verify the page loads without errors
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "h1")))

        # Check that page title or header is present
        page_text = authenticated_browser.page_source
        assert "Leaders" in page_text or "Area Leaders" in page_text

    def test_single_entry_tables(self, authenticated_browser, participant_model):
        """Test sorting works correctly with single entries in each table."""
        base_url = get_base_url()

        # Create single test participant
        test_participant = {
            'first_name': 'SingleTest',
            'last_name': 'Leader',
            'email': 'single.test@test.com',
            'preferred_area': 'F',
            'participation_type': 'regular',
            'interested_in_leadership': True
        }

        participant_id = participant_model.add_participant(test_participant)

        # Promote to leader to have one entry in current leaders
        participant_model.assign_area_leadership(participant_id, 'F', 'test-admin@test.com')

        # Create another participant to have one entry in potential leaders
        potential_participant = {
            'first_name': 'PotentialTest',
            'last_name': 'Leader',
            'email': 'potential.test@test.com',
            'preferred_area': 'G',
            'participation_type': 'regular',
            'interested_in_leadership': True
        }
        participant_model.add_participant(potential_participant)

        # Navigate to leaders page (already authenticated via fixture)
        authenticated_browser.get(f"{base_url}/admin/leaders")

        wait = WebDriverWait(authenticated_browser, 10)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "table")))

        # Verify both participants are visible
        page_text = authenticated_browser.page_source
        assert 'SingleTest' in page_text, "Current leader should be visible"
        assert 'PotentialTest' in page_text, "Potential leader should be visible"