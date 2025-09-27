# Updated by Claude AI on 2025-09-26
"""
Test for Leader Area Assignment Bug Fix

This test verifies that when a participant is promoted to leader of a different area,
their participant area assignment is updated to match their leadership area.

Bug: Participant in Area A promoted to leader of Area C still shows as participant in Area A
Fix: assign_area_leadership now updates area_preference to match assigned_area_leader
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


class TestLeaderAreaAssignmentBug:
    """Test the leader area assignment bug fix."""

    def test_leader_promotion_updates_participant_area(self, participant_model):
        """
        Test that promoting a participant to leader of a different area
        updates their participant area assignment.
        """
        # Create test participant in Area A with leadership interest
        test_participant = {
            'first_name': 'TestLeader',
            'last_name': 'AreaChanger',
            'email': 'test.leader.area@test.com',
            'preferred_area': 'A',  # Originally in Area A
            'participation_type': 'regular',
            'leadership_interest': True,
            'cell_phone': '250-555-0123'
        }

        participant_id = participant_model.add_participant(test_participant)

        # Verify initial state
        participant = participant_model.get_participant(participant_id)
        assert participant['preferred_area'] == 'A'
        assert participant.get('is_leader', False) == False
        assert participant.get('assigned_area_leader') is None

        # Promote participant to leader of Area C (different from their current area)
        success = participant_model.assign_area_leadership(participant_id, 'C', 'test-admin@test.com')
        assert success == True

        # Verify the fix: both leadership area AND participant area should be updated
        updated_participant = participant_model.get_participant(participant_id)

        # Leadership fields should be set
        assert updated_participant['is_leader'] == True
        assert updated_participant['assigned_area_leader'] == 'C'

        # BUG FIX: Participant area should now match leadership area
        assert updated_participant['preferred_area'] == 'C', \
            "Bug: Participant area should be updated to match leadership area"

        # Verify they show up in Area C participant list, not Area A
        area_c_participants = participant_model.get_participants_by_area('C')
        area_a_participants = participant_model.get_participants_by_area('A')

        participant_in_c = any(p['id'] == participant_id for p in area_c_participants)
        participant_in_a = any(p['id'] == participant_id for p in area_a_participants)

        assert participant_in_c == True, "Leader should appear as participant in their leadership area"
        assert participant_in_a == False, "Leader should NOT appear as participant in their original area"

    def test_leader_demotion_preserves_area(self, participant_model):
        """
        Test that demoting a leader preserves their area assignment
        (they remain as a participant in the area they were leading).
        """
        # Create test participant and promote to leader
        test_participant = {
            'first_name': 'TestDemotion',
            'last_name': 'Leader',
            'email': 'test.demotion@test.com',
            'preferred_area': 'B',
            'participation_type': 'regular',
            'leadership_interest': True
        }

        participant_id = participant_model.add_participant(test_participant)

        # Promote to leader of Area D
        participant_model.assign_area_leadership(participant_id, 'D', 'test-admin@test.com')

        # Verify promotion worked and area was updated
        promoted = participant_model.get_participant(participant_id)
        assert promoted['is_leader'] == True
        assert promoted['assigned_area_leader'] == 'D'
        assert promoted['preferred_area'] == 'D'

        # Demote from leadership
        success = participant_model.remove_area_leadership(participant_id, 'test-admin@test.com')
        assert success == True

        # Verify demotion: should remain as participant in Area D
        demoted = participant_model.get_participant(participant_id)
        assert demoted['is_leader'] == False
        assert demoted.get('assigned_area_leader') is None
        assert demoted['preferred_area'] == 'D', \
            "After demotion, should remain as participant in the area they were leading"

    def test_multiple_promotions_scenario(self, participant_model):
        """
        Test the specific scenario described in the bug report:
        Two participants in Area A, both promoted to different leadership areas.
        """
        # Create two participants in Area A with leadership interest
        participant1_data = {
            'first_name': 'Leader1',
            'last_name': 'FromAreaA',
            'email': 'leader1.area.a@test.com',
            'preferred_area': 'A',
            'participation_type': 'regular',
            'leadership_interest': True
        }

        participant2_data = {
            'first_name': 'Leader2',
            'last_name': 'FromAreaA',
            'email': 'leader2.area.a@test.com',
            'preferred_area': 'A',
            'participation_type': 'regular',
            'leadership_interest': True
        }

        p1_id = participant_model.add_participant(participant1_data)
        p2_id = participant_model.add_participant(participant2_data)

        # Both should initially be in Area A
        area_a_initial = participant_model.get_participants_by_area('A')
        assert len([p for p in area_a_initial if p['id'] in [p1_id, p2_id]]) == 2

        # Promote first participant to leader of Area A
        participant_model.assign_area_leadership(p1_id, 'A', 'test-admin@test.com')

        # Promote second participant to leader of Area C
        participant_model.assign_area_leadership(p2_id, 'C', 'test-admin@test.com')

        # Verify final state
        p1_final = participant_model.get_participant(p1_id)
        p2_final = participant_model.get_participant(p2_id)

        # P1 should be leader and participant in Area A
        assert p1_final['is_leader'] == True
        assert p1_final['assigned_area_leader'] == 'A'
        assert p1_final['preferred_area'] == 'A'

        # P2 should be leader and participant in Area C (NOT Area A)
        assert p2_final['is_leader'] == True
        assert p2_final['assigned_area_leader'] == 'C'
        assert p2_final['preferred_area'] == 'C'

        # Check area participant lists
        area_a_final = participant_model.get_participants_by_area('A')
        area_c_final = participant_model.get_participants_by_area('C')

        p1_in_a = any(p['id'] == p1_id for p in area_a_final)
        p2_in_a = any(p['id'] == p2_id for p in area_a_final)
        p2_in_c = any(p['id'] == p2_id for p in area_c_final)

        assert p1_in_a == True, "P1 should be participant in Area A (their leadership area)"
        assert p2_in_a == False, "P2 should NOT be participant in Area A after promotion to Area C"
        assert p2_in_c == True, "P2 should be participant in Area C (their leadership area)"