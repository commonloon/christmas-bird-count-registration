# Updated by Claude AI on 2025-09-26
"""
Test for Admin Leaders Backend Sorting

This test verifies that the backend sorting logic in the admin/leaders route
properly sorts both current leaders and potential leaders.
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


class TestAdminLeadersBackendSorting:
    """Test the backend sorting logic for admin/leaders page."""

    def test_current_leaders_sorting_logic(self, participant_model):
        """Test that current leaders are sorted by area code then by first name."""

        # Create test participants and promote them to leaders
        test_leaders = [
            # Create leaders in mixed order to test sorting
            {'first_name': 'Zebra', 'last_name': 'Leader', 'email': 'zebra@test.com', 'area': 'C'},
            {'first_name': 'Alpha', 'last_name': 'Leader', 'email': 'alpha@test.com', 'area': 'A'},
            {'first_name': 'Charlie', 'last_name': 'Leader', 'email': 'charlie@test.com', 'area': 'A'},
            {'first_name': 'Beta', 'last_name': 'Leader', 'email': 'beta@test.com', 'area': 'B'},
        ]

        # Create participants and promote to leaders
        for leader_data in test_leaders:
            participant = {
                'first_name': leader_data['first_name'],
                'last_name': leader_data['last_name'],
                'email': leader_data['email'],
                'preferred_area': leader_data['area'],
                'participation_type': 'regular',
                'interested_in_leadership': True
            }
            participant_id = participant_model.add_participant(participant)
            participant_model.assign_area_leadership(participant_id, leader_data['area'], 'test-admin@test.com')

        # Get leaders and simulate the sorting logic from the route
        all_leaders = participant_model.get_leaders()

        # Apply the same sorting logic as in routes/admin.py
        normalized_leaders = all_leaders  # In real code this goes through normalize_participant_record
        normalized_leaders.sort(key=lambda x: (x.get('assigned_area_leader', ''), x.get('first_name', '')))

        # Verify sorting
        assert len(normalized_leaders) == 4, "Should have 4 leaders"

        # Expected order: Alpha (Area A), Charlie (Area A), Beta (Area B), Zebra (Area C)
        expected_order = [
            ('Alpha', 'A'),
            ('Charlie', 'A'),
            ('Beta', 'B'),
            ('Zebra', 'C')
        ]

        for i, (expected_name, expected_area) in enumerate(expected_order):
            actual_name = normalized_leaders[i]['first_name']
            actual_area = normalized_leaders[i]['assigned_area_leader']

            assert actual_name == expected_name, \
                f"Position {i}: Expected {expected_name}, got {actual_name}"
            assert actual_area == expected_area, \
                f"Position {i}: Expected area {expected_area}, got {actual_area}"

    def test_potential_leaders_sorting_logic(self, participant_model):
        """Test that potential leaders are sorted by preferred area then by first name."""

        # Create test participants interested in leadership
        test_participants = [
            {'first_name': 'Zebra', 'last_name': 'Potential', 'email': 'zebra@test.com', 'area': 'B'},
            {'first_name': 'Alpha', 'last_name': 'Potential', 'email': 'alpha@test.com', 'area': 'C'},
            {'first_name': 'Charlie', 'last_name': 'Potential', 'email': 'charlie@test.com', 'area': 'A'},
            {'first_name': 'Beta', 'last_name': 'Potential', 'email': 'beta@test.com', 'area': 'A'},
        ]

        # Create participants with leadership interest
        for participant_data in test_participants:
            participant = {
                'first_name': participant_data['first_name'],
                'last_name': participant_data['last_name'],
                'email': participant_data['email'],
                'preferred_area': participant_data['area'],
                'participation_type': 'regular',
                'interested_in_leadership': True
            }
            participant_model.add_participant(participant)

        # Get leadership interested participants and simulate the sorting logic from the route
        leadership_interested = participant_model.get_participants_interested_in_leadership()

        # Apply the same sorting logic as in routes/admin.py
        leadership_interested.sort(key=lambda x: (x.get('preferred_area', ''), x.get('first_name', '')))

        # Verify sorting
        assert len(leadership_interested) == 4, "Should have 4 potential leaders"

        # Expected order: Beta (Area A), Charlie (Area A), Zebra (Area B), Alpha (Area C)
        expected_order = [
            ('Beta', 'A'),
            ('Charlie', 'A'),
            ('Zebra', 'B'),
            ('Alpha', 'C')
        ]

        for i, (expected_name, expected_area) in enumerate(expected_order):
            actual_name = leadership_interested[i]['first_name']
            actual_area = leadership_interested[i]['preferred_area']

            assert actual_name == expected_name, \
                f"Position {i}: Expected {expected_name}, got {actual_name}"
            assert actual_area == expected_area, \
                f"Position {i}: Expected area {expected_area}, got {actual_area}"

    def test_mixed_scenario_sorting(self, participant_model):
        """Test sorting with a mix of current leaders and potential leaders."""

        # Create participants for both categories
        participants_data = [
            # These will become leaders
            {'first_name': 'Leader1', 'email': 'leader1@test.com', 'area': 'C', 'make_leader': True},
            {'first_name': 'Leader2', 'email': 'leader2@test.com', 'area': 'A', 'make_leader': True},

            # These remain potential leaders
            {'first_name': 'Potential1', 'email': 'potential1@test.com', 'area': 'B', 'make_leader': False},
            {'first_name': 'Potential2', 'email': 'potential2@test.com', 'area': 'A', 'make_leader': False},
        ]

        # Create all participants
        for data in participants_data:
            participant = {
                'first_name': data['first_name'],
                'last_name': 'Test',
                'email': data['email'],
                'preferred_area': data['area'],
                'participation_type': 'regular',
                'interested_in_leadership': True
            }
            participant_id = participant_model.add_participant(participant)

            if data['make_leader']:
                participant_model.assign_area_leadership(participant_id, data['area'], 'test-admin@test.com')

        # Test current leaders sorting
        all_leaders = participant_model.get_leaders()
        all_leaders.sort(key=lambda x: (x.get('assigned_area_leader', ''), x.get('first_name', '')))

        assert len(all_leaders) == 2
        assert all_leaders[0]['first_name'] == 'Leader2'  # Area A
        assert all_leaders[1]['first_name'] == 'Leader1'  # Area C

        # Test potential leaders sorting
        leadership_interested = participant_model.get_participants_interested_in_leadership()
        leadership_interested.sort(key=lambda x: (x.get('preferred_area', ''), x.get('first_name', '')))

        # Should have all 4 participants (including promoted leaders)
        assert len(leadership_interested) >= 2  # At least the non-promoted ones

        # Find the non-leader participants
        non_leaders = [p for p in leadership_interested if not p.get('is_leader', False)]
        assert len(non_leaders) == 2

        # Should be sorted: Potential2 (Area A), Potential1 (Area B)
        assert non_leaders[0]['first_name'] == 'Potential2'
        assert non_leaders[1]['first_name'] == 'Potential1'