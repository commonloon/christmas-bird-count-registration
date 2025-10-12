# Unit tests for ParticipantModel
# Updated by Claude AI on 2025-10-11
"""
Fast unit tests for ParticipantModel that test core database operations.
These tests run against the test Firestore database and use year 2000 for isolation.
"""

import pytest
from datetime import datetime
from models.participant import ParticipantModel
from tests.test_config import get_database_name
from google.cloud import firestore


@pytest.fixture(scope="module")
def firestore_client():
    """Module-scoped Firestore client for fast test execution."""
    database_name = get_database_name()
    client = firestore.Client(database=database_name)
    yield client


@pytest.fixture(scope="module")
def test_year():
    """Use year 2000 for test isolation."""
    return 2000


@pytest.fixture(scope="module")
def participant_model(firestore_client, test_year):
    """Module-scoped participant model."""
    return ParticipantModel(firestore_client, test_year)


@pytest.fixture(scope="module", autouse=True)
def clear_test_data(firestore_client, test_year):
    """Clear test data before running tests."""
    collection_name = f'participants_{test_year}'
    docs = firestore_client.collection(collection_name).stream()
    for doc in docs:
        doc.reference.delete()
    yield
    # Leave data for inspection after tests


class TestParticipantCreation:
    """Test participant creation and retrieval."""

    def test_add_participant_basic(self, participant_model):
        """Test adding a basic participant."""
        participant_data = {
            'first_name': 'Alice',
            'last_name': 'Test',
            'email': 'alice@test.com',
            'phone': '555-1234',
            'preferred_area': 'A',
            'skill_level': 'Intermediate',
            'experience': '1-2 counts',
            'participation_type': 'regular'
        }

        participant_id = participant_model.add_participant(participant_data)

        assert participant_id is not None
        assert isinstance(participant_id, str)
        assert len(participant_id) > 0

    def test_add_participant_sets_defaults(self, participant_model):
        """Test that add_participant sets default values."""
        participant_data = {
            'first_name': 'Bob',
            'last_name': 'Default',
            'email': 'bob@test.com',
            'phone': '555-5678',
            'preferred_area': 'B'
        }

        participant_id = participant_model.add_participant(participant_data)
        participant = participant_model.get_participant(participant_id)

        assert participant['is_leader'] is False
        assert participant['assigned_area_leader'] is None
        assert participant['has_binoculars'] is False
        assert participant['spotting_scope'] is False
        assert participant['participation_type'] == 'regular'
        assert participant['year'] == 2000

    def test_add_participant_sets_timestamps(self, participant_model):
        """Test that timestamps are set automatically."""
        participant_data = {
            'first_name': 'Charlie',
            'last_name': 'Timestamp',
            'email': 'charlie@test.com',
            'phone': '555-9999',
            'preferred_area': 'C'
        }

        participant_id = participant_model.add_participant(participant_data)
        participant = participant_model.get_participant(participant_id)

        assert 'created_at' in participant
        assert 'updated_at' in participant
        assert participant['created_at'] is not None
        assert participant['updated_at'] is not None

    def test_get_participant_nonexistent(self, participant_model):
        """Test getting a nonexistent participant returns None."""
        result = participant_model.get_participant('nonexistent-id-12345')
        assert result is None


class TestParticipantQueries:
    """Test querying participants."""

    def test_get_participants_by_area(self, participant_model):
        """Test retrieving participants by area."""
        # Add test participants
        for i in range(3):
            participant_model.add_participant({
                'first_name': f'AreaD{i}',
                'last_name': 'Participant',
                'email': f'aread{i}@test.com',
                'phone': f'555-000{i}',
                'preferred_area': 'D'
            })

        participants = participant_model.get_participants_by_area('D')
        assert len(participants) >= 3
        assert all(p['preferred_area'] == 'D' for p in participants)

    def test_get_unassigned_participants(self, participant_model):
        """Test retrieving unassigned participants."""
        participant_model.add_participant({
            'first_name': 'Unassigned',
            'last_name': 'Person',
            'email': 'unassigned@test.com',
            'phone': '555-0000',
            'preferred_area': 'UNASSIGNED'
        })

        unassigned = participant_model.get_unassigned_participants()
        assert len(unassigned) >= 1
        assert all(p['preferred_area'] == 'UNASSIGNED' for p in unassigned)

    def test_get_participants_by_email(self, participant_model):
        """Test retrieving participants by email."""
        test_email = 'emailtest@test.com'
        participant_model.add_participant({
            'first_name': 'Email',
            'last_name': 'Test',
            'email': test_email,
            'phone': '555-1111',
            'preferred_area': 'E'
        })

        participants = participant_model.get_participants_by_email(test_email)
        assert len(participants) >= 1
        assert all(p['email'] == test_email.lower() for p in participants)

    def test_get_participant_by_email_and_names(self, participant_model):
        """Test identity-based participant lookup."""
        participant_data = {
            'first_name': 'Identity',
            'last_name': 'Match',
            'email': 'identity@test.com',
            'phone': '555-2222',
            'preferred_area': 'F'
        }
        participant_model.add_participant(participant_data)

        result = participant_model.get_participant_by_email_and_names(
            'identity@test.com', 'Identity', 'Match'
        )

        assert result is not None
        assert result['first_name'] == 'Identity'
        assert result['last_name'] == 'Match'
        assert result['email'] == 'identity@test.com'

    def test_get_all_participants(self, participant_model):
        """Test retrieving all participants."""
        all_participants = participant_model.get_all_participants()
        assert isinstance(all_participants, list)
        assert len(all_participants) > 0


class TestParticipantUpdates:
    """Test updating participants."""

    def test_update_participant(self, participant_model):
        """Test updating participant data."""
        participant_id = participant_model.add_participant({
            'first_name': 'Update',
            'last_name': 'Test',
            'email': 'update@test.com',
            'phone': '555-3333',
            'preferred_area': 'G'
        })

        success = participant_model.update_participant(participant_id, {
            'phone': '555-4444',
            'skill_level': 'Expert'
        })

        assert success is True

        updated = participant_model.get_participant(participant_id)
        assert updated['phone'] == '555-4444'
        assert updated['skill_level'] == 'Expert'

    def test_assign_participant_to_area(self, participant_model):
        """Test assigning a participant to an area."""
        participant_id = participant_model.add_participant({
            'first_name': 'Assign',
            'last_name': 'Test',
            'email': 'assign@test.com',
            'phone': '555-5555',
            'preferred_area': 'UNASSIGNED'
        })

        success = participant_model.assign_participant_to_area(
            participant_id, 'H', 'admin@test.com'
        )

        assert success is True

        assigned = participant_model.get_participant(participant_id)
        assert assigned['preferred_area'] == 'H'
        assert assigned['assigned_by'] == 'admin@test.com'
        assert 'assigned_at' in assigned

    def test_update_participant_nonexistent(self, participant_model):
        """Test updating a nonexistent participant returns False."""
        success = participant_model.update_participant('nonexistent-99999', {
            'phone': '555-0000'
        })
        assert success is False


class TestParticipantDeletion:
    """Test deleting participants."""

    def test_delete_participant(self, participant_model):
        """Test deleting a participant."""
        participant_id = participant_model.add_participant({
            'first_name': 'Delete',
            'last_name': 'Me',
            'email': 'delete@test.com',
            'phone': '555-6666',
            'preferred_area': 'I'
        })

        success = participant_model.delete_participant(participant_id)
        assert success is True

        deleted = participant_model.get_participant(participant_id)
        assert deleted is None

    def test_delete_nonexistent_participant(self, participant_model):
        """Test deleting a nonexistent participant returns False."""
        success = participant_model.delete_participant('nonexistent-12345')
        assert success is False


class TestEmailChecks:
    """Test email existence checking."""

    def test_email_exists(self, participant_model):
        """Test checking if an email exists."""
        test_email = 'exists@test.com'
        participant_model.add_participant({
            'first_name': 'Exists',
            'last_name': 'Check',
            'email': test_email,
            'phone': '555-7777',
            'preferred_area': 'J'
        })

        assert participant_model.email_exists(test_email) is True
        assert participant_model.email_exists('doesnotexist@test.com') is False

    def test_email_name_exists(self, participant_model):
        """Test identity-based existence check."""
        participant_model.add_participant({
            'first_name': 'Identity',
            'last_name': 'Exists',
            'email': 'identityexists@test.com',
            'phone': '555-8888',
            'preferred_area': 'K'
        })

        assert participant_model.email_name_exists(
            'identityexists@test.com', 'Identity', 'Exists'
        ) is True

        assert participant_model.email_name_exists(
            'identityexists@test.com', 'Wrong', 'Name'
        ) is False


class TestLeadershipOperations:
    """Test leadership-related operations."""

    def test_get_leaders(self, participant_model):
        """Test retrieving all leaders."""
        participant_id = participant_model.add_participant({
            'first_name': 'Leader',
            'last_name': 'Test',
            'email': 'leader@test.com',
            'phone': '555-9999',
            'preferred_area': 'L',
            'is_leader': True,
            'assigned_area_leader': 'L'
        })

        leaders = participant_model.get_leaders()
        assert any(leader['id'] == participant_id for leader in leaders)

    def test_get_leaders_by_area(self, participant_model):
        """Test retrieving leaders for a specific area."""
        participant_model.add_participant({
            'first_name': 'AreaLeader',
            'last_name': 'M',
            'email': 'leaderm@test.com',
            'phone': '555-1000',
            'preferred_area': 'M',
            'is_leader': True,
            'assigned_area_leader': 'M'
        })

        leaders = participant_model.get_leaders_by_area('M')
        assert len(leaders) >= 1
        assert all(leader['assigned_area_leader'] == 'M' for leader in leaders)

    def test_assign_area_leadership(self, participant_model):
        """Test assigning leadership to a participant."""
        participant_id = participant_model.add_participant({
            'first_name': 'New',
            'last_name': 'Leader',
            'email': 'newleader@test.com',
            'phone': '555-2000',
            'preferred_area': 'N'
        })

        success = participant_model.assign_area_leadership(
            participant_id, 'N', 'admin@test.com'
        )

        assert success is True

        leader = participant_model.get_participant(participant_id)
        assert leader['is_leader'] is True
        assert leader['assigned_area_leader'] == 'N'
        assert leader['preferred_area'] == 'N'  # Should match leadership area
        assert leader['leadership_assigned_by'] == 'admin@test.com'

    def test_remove_area_leadership(self, participant_model):
        """Test removing leadership from a participant."""
        participant_id = participant_model.add_participant({
            'first_name': 'Remove',
            'last_name': 'Leadership',
            'email': 'removeleader@test.com',
            'phone': '555-3000',
            'preferred_area': 'O',
            'is_leader': True,
            'assigned_area_leader': 'O'
        })

        success = participant_model.remove_area_leadership(
            participant_id, 'admin@test.com'
        )

        assert success is True

        former_leader = participant_model.get_participant(participant_id)
        assert former_leader['is_leader'] is False
        assert former_leader['assigned_area_leader'] is None
        assert former_leader['leadership_removed_by'] == 'admin@test.com'

    def test_add_leader(self, participant_model):
        """Test adding a new leader directly."""
        leader_data = {
            'first_name': 'Direct',
            'last_name': 'Leader',
            'email': 'directleader@test.com',
            'phone': '555-4000',
            'area_code': 'P',
            'assigned_by': 'admin@test.com'
        }

        leader_id = participant_model.add_leader(leader_data)

        assert leader_id is not None

        leader = participant_model.get_participant(leader_id)
        assert leader['is_leader'] is True
        assert leader['assigned_area_leader'] == 'P'
        assert leader['preferred_area'] == 'P'

    def test_add_leader_duplicate_identity_raises_error(self, participant_model):
        """Test that adding a leader with existing identity raises error."""
        leader_data = {
            'first_name': 'Duplicate',
            'last_name': 'Leader',
            'email': 'duplicate@test.com',
            'phone': '555-5000',
            'area_code': 'Q',
            'assigned_by': 'admin@test.com'
        }

        # Add first leader
        participant_model.add_leader(leader_data)

        # Attempt to add duplicate should raise ValueError
        with pytest.raises(ValueError, match="already exists"):
            participant_model.add_leader(leader_data)

    def test_get_leaders_by_identity(self, participant_model):
        """Test identity-based leader lookup."""
        participant_model.add_participant({
            'first_name': 'Identity',
            'last_name': 'Leader',
            'email': 'identityleader@test.com',
            'phone': '555-6000',
            'preferred_area': 'R',
            'is_leader': True,
            'assigned_area_leader': 'R'
        })

        leaders = participant_model.get_leaders_by_identity(
            'Identity', 'Leader', 'identityleader@test.com'
        )

        assert len(leaders) >= 1
        assert leaders[0]['first_name'] == 'Identity'
        assert leaders[0]['last_name'] == 'Leader'

    def test_deactivate_leaders_by_identity(self, participant_model):
        """Test deactivating leaders by identity."""
        participant_id = participant_model.add_participant({
            'first_name': 'Deactivate',
            'last_name': 'Me',
            'email': 'deactivate@test.com',
            'phone': '555-7000',
            'preferred_area': 'S',
            'is_leader': True,
            'assigned_area_leader': 'S'
        })

        success = participant_model.deactivate_leaders_by_identity(
            'Deactivate', 'Me', 'deactivate@test.com', 'admin@test.com'
        )

        assert success is True

        participant = participant_model.get_participant(participant_id)
        assert participant['is_leader'] is False

    def test_is_area_leader(self, participant_model):
        """Test checking if someone is an area leader."""
        participant_model.add_participant({
            'first_name': 'Check',
            'last_name': 'Leader',
            'email': 'checkleader@test.com',
            'phone': '555-8000',
            'preferred_area': 'T',
            'is_leader': True,
            'assigned_area_leader': 'T'
        })

        assert participant_model.is_area_leader('checkleader@test.com') is True
        assert participant_model.is_area_leader('checkleader@test.com', 'T') is True
        assert participant_model.is_area_leader('checkleader@test.com', 'Z') is False
        assert participant_model.is_area_leader('notleader@test.com') is False

    def test_get_participants_interested_in_leadership(self, participant_model):
        """Test getting participants interested in leadership."""
        participant_model.add_participant({
            'first_name': 'Interested',
            'last_name': 'Leader',
            'email': 'interested@test.com',
            'phone': '555-9000',
            'preferred_area': 'U',
            'interested_in_leadership': True,
            'is_leader': False
        })

        interested = participant_model.get_participants_interested_in_leadership()
        assert any(
            p['email'] == 'interested@test.com'
            for p in interested
        )

    def test_get_areas_without_leaders(self, participant_model):
        """Test getting areas without assigned leaders."""
        areas = participant_model.get_areas_without_leaders()
        assert isinstance(areas, list)
        # Should include some areas from config (A-X minus assigned ones)
        assert len(areas) > 0

    def test_assign_area_leadership_nonexistent(self, participant_model):
        """Test assigning leadership to nonexistent participant returns False."""
        success = participant_model.assign_area_leadership(
            'nonexistent-88888', 'Z', 'admin@test.com'
        )
        assert success is False

    def test_remove_area_leadership_from_non_leader(self, participant_model):
        """Test removing leadership from participant who is not a leader."""
        participant_id = participant_model.add_participant({
            'first_name': 'NotLeader',
            'last_name': 'Test',
            'email': 'notleader@test.com',
            'phone': '555-1111',
            'preferred_area': 'V',
            'is_leader': False
        })

        success = participant_model.remove_area_leadership(
            participant_id, 'admin@test.com'
        )
        # Should return True (operation is idempotent)
        assert success is True

        # Verify still not a leader
        participant = participant_model.get_participant(participant_id)
        assert participant['is_leader'] is False

    def test_deactivate_leaders_by_identity_no_match(self, participant_model):
        """Test deactivating leaders when no matching identity exists."""
        success = participant_model.deactivate_leaders_by_identity(
            'NonExistent', 'Person', 'noone@test.com', 'admin@test.com'
        )
        # Should return True (no leaders to deactivate, operation is idempotent)
        assert success is True

    def test_remove_leader_wrapper(self, participant_model):
        """Test remove_leader() wrapper method."""
        participant_id = participant_model.add_participant({
            'first_name': 'WrapperTest',
            'last_name': 'Leader',
            'email': 'wrappertest@test.com',
            'phone': '555-2222',
            'preferred_area': 'W',
            'is_leader': True,
            'assigned_area_leader': 'W'
        })

        success = participant_model.remove_leader(participant_id, 'admin@test.com')
        assert success is True

        former_leader = participant_model.get_participant(participant_id)
        assert former_leader['is_leader'] is False
        assert former_leader['assigned_area_leader'] is None


class TestAreaCounts:
    """Test area count calculations."""

    def test_get_area_counts(self, participant_model):
        """Test getting participant counts by area."""
        counts = participant_model.get_area_counts()
        assert isinstance(counts, dict)
        # Counts should not include UNASSIGNED
        assert 'UNASSIGNED' not in counts


class TestStaticMethods:
    """Test static/class methods."""

    def test_get_available_years(self, firestore_client):
        """Test getting available years."""
        years = ParticipantModel.get_available_years(firestore_client)
        assert isinstance(years, list)
        assert 2000 in years  # Our test year
        assert all(isinstance(year, int) for year in years)
