# Identity-Based Testing Utilities for CBC Registration Test Suite
# Updated by Claude AI on 2025-09-22

"""
Utilities for testing identity-based operations and family email scenarios
in the Christmas Bird Count registration system.
"""

import logging
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any
from google.cloud import firestore

# Add project root to Python path for imports
import sys
import os
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from models.participant import ParticipantModel
from models.area_leader import AreaLeaderModel

logger = logging.getLogger(__name__)


class IdentityTestHelper:
    """Helper class for identity-based testing operations."""

    def __init__(self, db_client: firestore.Client, test_year: int = None):
        """Initialize with database client and test year."""
        self.db = db_client
        self.test_year = test_year or datetime.now().year
        self.participant_model = ParticipantModel(db_client, self.test_year)
        self.area_leader_model = AreaLeaderModel(db_client, self.test_year)

    def create_family_scenario(self, family_email: str, members: List[Dict[str, Any]]) -> Dict[str, List[str]]:
        """
        Create a family scenario with multiple members sharing an email.

        Args:
            family_email: Shared email address for family
            members: List of member data with first_name, last_name, area, role, etc.

        Returns:
            Dict with participant_ids and leader_ids lists
        """
        participant_ids = []
        leader_ids = []

        logger.info(f"Creating family scenario: {len(members)} members sharing {family_email}")

        for i, member in enumerate(members):
            # Create participant record
            participant_data = {
                'first_name': member['first_name'],
                'last_name': member['last_name'],
                'email': family_email,
                'phone': f"555-FAM-{i+1:03d}",
                'phone2': '',
                'skill_level': member.get('skill_level', 'Intermediate'),
                'experience': member.get('experience', '1-2 counts'),
                'preferred_area': member.get('area', 'A'),
                'participation_type': member.get('participation_type', 'regular'),
                'has_binoculars': member.get('has_binoculars', True),
                'spotting_scope': member.get('spotting_scope', False),
                'notes_to_organizers': f'Test family member {i+1}',
                'interested_in_leadership': member.get('interested_in_leadership', False),
                'interested_in_scribe': member.get('interested_in_scribe', False),
                'is_leader': False,  # Will be updated if promoted
                'assigned_area_leader': None,
                'auto_assigned': False,
                'assigned_by': '',
                'assigned_at': None
            }

            participant_id = self.participant_model.add_participant(participant_data)
            participant_ids.append(participant_id)
            logger.info(f"Created participant: {member['first_name']} {member['last_name']} (ID: {participant_id})")

            # Create leader record if specified
            if member.get('role') == 'leader':
                leader_data = {
                    'area_code': member.get('area', 'A'),
                    'leader_email': family_email,
                    'first_name': member['first_name'],
                    'last_name': member['last_name'],
                    'cell_phone': f"555-FAM-{i+1:03d}",
                    'assigned_by': 'test-family-setup@test.ca',
                    'active': True,
                    'created_from_participant': True,
                    'notes': f'Test family leader {i+1}'
                }

                leader_id = self.area_leader_model.add_leader(leader_data)
                leader_ids.append(leader_id)

                # Update participant to mark as leader
                self.participant_model.update_participant(participant_id, {
                    'is_leader': True,
                    'assigned_area_leader': member.get('area', 'A')
                })

                logger.info(f"Created leader: {member['first_name']} {member['last_name']} (ID: {leader_id})")

        return {
            'participant_ids': participant_ids,
            'leader_ids': leader_ids,
            'family_email': family_email,
            'member_count': len(members)
        }

    def verify_identity_synchronization(self, first_name: str, last_name: str, email: str) -> Dict[str, Any]:
        """
        Verify that participant and leader records are properly synchronized for an identity.

        Args:
            first_name: First name of person
            last_name: Last name of person
            email: Email address of person

        Returns:
            Dict with synchronization status and details
        """
        logger.info(f"Verifying synchronization for: {first_name} {last_name} <{email}>")

        # Get participant records
        all_participants = self.participant_model.get_all_participants()
        matching_participants = [
            p for p in all_participants
            if (p.get('first_name', '').strip().lower() == first_name.strip().lower() and
                p.get('last_name', '').strip().lower() == last_name.strip().lower() and
                p.get('email', '').strip().lower() == email.strip().lower())
        ]

        # Get leader records using identity-based lookup
        matching_leaders = self.area_leader_model.get_leaders_by_identity(first_name, last_name, email)

        # Check synchronization status
        sync_status = {
            'participant_count': len(matching_participants),
            'leader_count': len(matching_leaders),
            'is_synchronized': True,
            'issues': []
        }

        # Check for issues
        if len(matching_participants) > 1:
            sync_status['issues'].append(f"Multiple participant records found: {len(matching_participants)}")
            sync_status['is_synchronized'] = False

        if len(matching_leaders) > 1:
            sync_status['issues'].append(f"Multiple leader records found: {len(matching_leaders)}")
            sync_status['is_synchronized'] = False

        # Check participant/leader flag consistency
        for participant in matching_participants:
            is_leader_flag = participant.get('is_leader', False)
            has_leader_record = len(matching_leaders) > 0

            if is_leader_flag and not has_leader_record:
                sync_status['issues'].append("Participant marked as leader but no leader record found")
                sync_status['is_synchronized'] = False
            elif not is_leader_flag and has_leader_record:
                sync_status['issues'].append("Leader record exists but participant not marked as leader")
                sync_status['is_synchronized'] = False

        logger.info(f"Synchronization check: {'✓' if sync_status['is_synchronized'] else '✗'}")
        if sync_status['issues']:
            for issue in sync_status['issues']:
                logger.warning(f"Sync issue: {issue}")

        return sync_status

    def test_identity_operations_isolation(self, families: List[Dict]) -> Dict[str, Any]:
        """
        Test that operations on one family member don't affect others sharing the same email.

        Args:
            families: List of family scenario dictionaries

        Returns:
            Dict with isolation test results
        """
        logger.info(f"Testing identity isolation across {len(families)} families")

        results = {
            'families_tested': len(families),
            'isolation_maintained': True,
            'cross_contamination_issues': []
        }

        for family in families:
            family_email = family['family_email']

            # Get all family members before operations
            before_state = {}
            all_participants = self.participant_model.get_all_participants()
            family_participants = [
                p for p in all_participants
                if p.get('email', '').strip().lower() == family_email.lower()
            ]

            for participant in family_participants:
                identity = (
                    participant.get('first_name', '').strip(),
                    participant.get('last_name', '').strip(),
                    participant.get('email', '').strip()
                )
                before_state[identity] = {
                    'is_leader': participant.get('is_leader', False),
                    'area': participant.get('preferred_area', ''),
                    'participant_exists': True
                }

                # Check leader records
                leaders = self.area_leader_model.get_leaders_by_identity(
                    identity[0], identity[1], identity[2]
                )
                before_state[identity]['leader_count'] = len(leaders)

            # Perform operation on first family member (if exists)
            if family_participants:
                first_member = family_participants[0]
                first_identity = (
                    first_member.get('first_name', '').strip(),
                    first_member.get('last_name', '').strip(),
                    first_member.get('email', '').strip()
                )

                # Test deletion and verify isolation
                if self.participant_model.delete_participant(first_member['id']):
                    logger.info(f"Deleted first family member: {first_identity[0]} {first_identity[1]}")

                    # Check other family members are unaffected
                    after_participants = self.participant_model.get_all_participants()
                    remaining_family = [
                        p for p in after_participants
                        if p.get('email', '').strip().lower() == family_email.lower()
                    ]

                    for participant in remaining_family:
                        identity = (
                            participant.get('first_name', '').strip(),
                            participant.get('last_name', '').strip(),
                            participant.get('email', '').strip()
                        )

                        if identity in before_state and identity != first_identity:
                            # This family member should be unaffected
                            before = before_state[identity]
                            current_leaders = self.area_leader_model.get_leaders_by_identity(
                                identity[0], identity[1], identity[2]
                            )

                            if before['leader_count'] != len(current_leaders):
                                issue = f"Family member {identity[0]} {identity[1]} leader count changed: {before['leader_count']} → {len(current_leaders)}"
                                results['cross_contamination_issues'].append(issue)
                                results['isolation_maintained'] = False
                                logger.error(f"Isolation violation: {issue}")

        logger.info(f"Identity isolation test: {'✓' if results['isolation_maintained'] else '✗'}")
        return results

    def create_test_identity(self, base_name: str, area: str, role: str = 'participant') -> Tuple[str, str]:
        """
        Create a single test identity for targeted testing.

        Args:
            base_name: Base name for generating unique test identity
            area: Area assignment
            role: 'participant', 'leader', or 'both'

        Returns:
            Tuple of (participant_id, leader_id) - leader_id is None if not created
        """
        timestamp = datetime.now().strftime('%H%M%S')
        first_name = f"Test{base_name}"
        last_name = f"Identity{timestamp}"
        email = f"test-{base_name.lower()}-{timestamp}@test-identity.ca"

        logger.info(f"Creating test identity: {first_name} {last_name} <{email}> as {role}")

        participant_id = None
        leader_id = None

        if role in ['participant', 'both']:
            participant_data = {
                'first_name': first_name,
                'last_name': last_name,
                'email': email,
                'phone': f'555-TEST-{timestamp}',
                'phone2': '',
                'skill_level': 'Intermediate',
                'experience': '1-2 counts',
                'preferred_area': area,
                'participation_type': 'regular',
                'has_binoculars': True,
                'spotting_scope': False,
                'notes_to_organizers': f'Test identity for {role} testing',
                'interested_in_leadership': role == 'both',
                'interested_in_scribe': False,
                'is_leader': role == 'both',
                'assigned_area_leader': area if role == 'both' else None,
                'auto_assigned': False,
                'assigned_by': 'test-identity-helper',
                'assigned_at': datetime.now() if role == 'both' else None
            }

            participant_id = self.participant_model.add_participant(participant_data)
            logger.info(f"Created test participant: {participant_id}")

        if role in ['leader', 'both']:
            leader_data = {
                'area_code': area,
                'leader_email': email,
                'first_name': first_name,
                'last_name': last_name,
                'cell_phone': f'555-TEST-{timestamp}',
                'assigned_by': 'test-identity-helper',
                'active': True,
                'created_from_participant': role == 'both',
                'notes': f'Test leader for {role} testing'
            }

            leader_id = self.area_leader_model.add_leader(leader_data)
            logger.info(f"Created test leader: {leader_id}")

        return participant_id, leader_id

    def cleanup_test_identities(self, test_email_pattern: str = "test-") -> int:
        """
        Clean up test identities created during testing.

        Args:
            test_email_pattern: Pattern to match test email addresses

        Returns:
            Number of records cleaned up
        """
        cleanup_count = 0

        # Clean up participants
        all_participants = self.participant_model.get_all_participants()
        for participant in all_participants:
            email = participant.get('email', '')
            if test_email_pattern in email:
                if self.participant_model.delete_participant(participant['id']):
                    cleanup_count += 1
                    logger.info(f"Cleaned up test participant: {participant.get('first_name')} {participant.get('last_name')}")

        # Clean up leaders
        all_leaders = self.area_leader_model.get_all_leaders()
        for leader in all_leaders:
            email = leader.get('leader_email', '')
            if test_email_pattern in email:
                if self.area_leader_model.remove_leader(leader['id'], 'test-cleanup'):
                    cleanup_count += 1
                    logger.info(f"Cleaned up test leader: {leader.get('first_name')} {leader.get('last_name')}")

        logger.info(f"Cleaned up {cleanup_count} test identity records")
        return cleanup_count


def create_identity_helper(db_client: firestore.Client, test_year: int = None) -> IdentityTestHelper:
    """Factory function to create an IdentityTestHelper instance."""
    return IdentityTestHelper(db_client, test_year)


# Standard family scenarios for consistent testing
STANDARD_FAMILY_SCENARIOS = [
    {
        'email': 'smith-family@test-scenarios.ca',
        'members': [
            {
                'first_name': 'John',
                'last_name': 'Smith',
                'area': 'A',
                'role': 'leader',
                'skill_level': 'Expert',
                'interested_in_leadership': True
            },
            {
                'first_name': 'Jane',
                'last_name': 'Smith',
                'area': 'B',
                'role': 'participant',
                'skill_level': 'Intermediate',
                'interested_in_leadership': False
            }
        ]
    },
    {
        'email': 'johnson-family@test-scenarios.ca',
        'members': [
            {
                'first_name': 'Bob',
                'last_name': 'Johnson',
                'area': 'C',
                'role': 'leader',
                'skill_level': 'Expert',
                'interested_in_leadership': True
            },
            {
                'first_name': 'Alice',
                'last_name': 'Johnson',
                'area': 'D',
                'role': 'leader',
                'skill_level': 'Intermediate',
                'interested_in_leadership': True
            },
            {
                'first_name': 'Charlie',
                'last_name': 'Johnson',
                'area': 'E',
                'role': 'participant',
                'skill_level': 'Beginner',
                'interested_in_leadership': False
            }
        ]
    }
]