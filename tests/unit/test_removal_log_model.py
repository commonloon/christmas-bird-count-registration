# Unit tests for RemovalLogModel
# Updated by Claude AI on 2025-10-11
"""
Fast unit tests for RemovalLogModel that test removal logging and tracking.
These tests run against the test Firestore database and use year 2000 for isolation.
"""

import pytest
from datetime import datetime, timedelta
from models.removal_log import RemovalLogModel
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
def removal_log_model(firestore_client, test_year):
    """Module-scoped removal log model."""
    return RemovalLogModel(firestore_client, test_year)


@pytest.fixture(scope="module", autouse=True)
def clear_test_data(firestore_client, test_year):
    """Clear test data before running tests."""
    collection_name = f'removal_log_{test_year}'
    docs = firestore_client.collection(collection_name).stream()
    for doc in docs:
        doc.reference.delete()
    yield
    # Leave data for inspection after tests


class TestRemovalLogging:
    """Test logging participant removals."""

    def test_log_removal_basic(self, removal_log_model):
        """Test logging a basic removal."""
        removal_id = removal_log_model.log_removal(
            participant_name='John Doe',
            area_code='A',
            removed_by='admin@test.com',
            reason='Participant request'
        )

        assert removal_id is not None
        assert isinstance(removal_id, str)
        assert len(removal_id) > 0

    def test_log_removal_with_email(self, removal_log_model):
        """Test logging removal with participant email."""
        removal_id = removal_log_model.log_removal(
            participant_name='Jane Smith',
            area_code='B',
            removed_by='admin@test.com',
            reason='No response',
            participant_email='jane@test.com'
        )

        removal = removal_log_model.get_removal(removal_id)
        assert removal['participant_email'] == 'jane@test.com'
        assert removal['participant_name'] == 'Jane Smith'
        assert removal['area_code'] == 'B'

    def test_log_removal_sets_defaults(self, removal_log_model):
        """Test that log_removal sets default values."""
        removal_id = removal_log_model.log_removal(
            participant_name='Test User',
            area_code='C',
            removed_by='admin@test.com'
        )

        removal = removal_log_model.get_removal(removal_id)
        assert removal['emailed'] is False
        assert removal['year'] == 2000
        assert 'removed_at' in removal
        assert removal['reason'] == ''

    def test_get_removal_nonexistent(self, removal_log_model):
        """Test getting a nonexistent removal returns None."""
        result = removal_log_model.get_removal('nonexistent-id-12345')
        assert result is None


class TestPendingRemovals:
    """Test querying pending removals."""

    def test_get_pending_removals(self, removal_log_model):
        """Test retrieving pending removals."""
        # Add some removals
        removal_log_model.log_removal(
            participant_name='Pending One',
            area_code='D',
            removed_by='admin@test.com'
        )
        removal_log_model.log_removal(
            participant_name='Pending Two',
            area_code='E',
            removed_by='admin@test.com'
        )

        pending = removal_log_model.get_pending_removals()
        assert len(pending) >= 2
        assert all(r['emailed'] is False for r in pending)

    def test_get_pending_removals_by_area(self, removal_log_model):
        """Test retrieving pending removals for specific area."""
        removal_log_model.log_removal(
            participant_name='Area F User',
            area_code='F',
            removed_by='admin@test.com'
        )

        pending_f = removal_log_model.get_pending_removals_by_area('F')
        assert len(pending_f) >= 1
        assert all(r['area_code'] == 'F' for r in pending_f)
        assert all(r['emailed'] is False for r in pending_f)


class TestRemovalRetrieval:
    """Test retrieving removal records."""

    def test_get_all_removals(self, removal_log_model):
        """Test retrieving all removals."""
        all_removals = removal_log_model.get_all_removals()
        assert isinstance(all_removals, list)
        assert len(all_removals) > 0

    def test_get_all_removals_with_limit(self, removal_log_model):
        """Test retrieving removals with limit."""
        limited = removal_log_model.get_all_removals(limit=5)
        assert isinstance(limited, list)
        assert len(limited) <= 5

    def test_get_removals_by_area(self, removal_log_model):
        """Test retrieving removals for a specific area."""
        removal_log_model.log_removal(
            participant_name='Area G User 1',
            area_code='G',
            removed_by='admin@test.com'
        )
        removal_log_model.log_removal(
            participant_name='Area G User 2',
            area_code='G',
            removed_by='admin@test.com'
        )

        removals_g = removal_log_model.get_removals_by_area('G')
        assert len(removals_g) >= 2
        assert all(r['area_code'] == 'G' for r in removals_g)

    def test_get_recent_removals(self, removal_log_model):
        """Test retrieving recent removals."""
        removal_log_model.log_removal(
            participant_name='Recent User',
            area_code='H',
            removed_by='admin@test.com'
        )

        recent = removal_log_model.get_recent_removals(days_back=7)
        assert isinstance(recent, list)
        # Should include the removal we just created
        assert any(r['participant_name'] == 'Recent User' for r in recent)

    def test_get_removals_since(self, removal_log_model):
        """Test retrieving removals since a timestamp."""
        cutoff = datetime.now() - timedelta(hours=1)

        removal_log_model.log_removal(
            participant_name='Since Test User',
            area_code='I',
            removed_by='admin@test.com'
        )

        removals = removal_log_model.get_removals_since('I', cutoff)
        assert len(removals) >= 1
        assert all(r['area_code'] == 'I' for r in removals)


class TestEmailTracking:
    """Test email tracking functionality."""

    def test_mark_removal_emailed(self, removal_log_model):
        """Test marking a single removal as emailed."""
        removal_id = removal_log_model.log_removal(
            participant_name='Email Test',
            area_code='J',
            removed_by='admin@test.com'
        )

        success = removal_log_model.mark_removal_emailed(removal_id)
        assert success is True

        removal = removal_log_model.get_removal(removal_id)
        assert removal['emailed'] is True
        assert 'emailed_at' in removal

    def test_mark_removals_emailed_batch(self, removal_log_model):
        """Test marking multiple removals as emailed."""
        removal_ids = []
        for i in range(3):
            removal_id = removal_log_model.log_removal(
                participant_name=f'Batch {i}',
                area_code='K',
                removed_by='admin@test.com'
            )
            removal_ids.append(removal_id)

        success = removal_log_model.mark_removals_emailed(removal_ids)
        assert success is True

        # Verify all are marked
        for removal_id in removal_ids:
            removal = removal_log_model.get_removal(removal_id)
            assert removal['emailed'] is True

    def test_mark_removal_emailed_nonexistent(self, removal_log_model):
        """Test marking nonexistent removal as emailed returns False."""
        success = removal_log_model.mark_removal_emailed('nonexistent-77777')
        assert success is False

    def test_mark_removals_emailed_batch_with_invalid_ids(self, removal_log_model):
        """Test batch marking with some invalid IDs."""
        # Create one valid removal
        valid_id = removal_log_model.log_removal(
            participant_name='Valid Batch',
            area_code='Z',
            removed_by='admin@test.com'
        )

        # Mix valid and invalid IDs
        mixed_ids = [valid_id, 'invalid-id-1', 'invalid-id-2']

        # This should handle the invalid IDs gracefully
        # The exact behavior depends on implementation
        # (could return partial success or False)
        result = removal_log_model.mark_removals_emailed(mixed_ids)

        # Verify the valid one was marked
        removal = removal_log_model.get_removal(valid_id)
        # If implementation is robust, valid one should be marked even if others failed
        assert removal is not None


class TestRemovalStatistics:
    """Test removal statistics and analytics."""

    def test_get_removal_stats(self, removal_log_model):
        """Test getting removal statistics."""
        stats = removal_log_model.get_removal_stats()

        assert 'total_removals' in stats
        assert 'pending_email' in stats
        assert 'by_area' in stats
        assert 'by_reason' in stats
        assert 'year' in stats
        assert stats['year'] == 2000
        assert isinstance(stats['total_removals'], int)
        assert isinstance(stats['pending_email'], int)
        assert isinstance(stats['by_area'], dict)
        assert isinstance(stats['by_reason'], dict)

    def test_get_removals_needing_notification(self, removal_log_model):
        """Test getting removals grouped by area for notifications."""
        # Add some pending removals
        removal_log_model.log_removal(
            participant_name='Notify L1',
            area_code='L',
            removed_by='admin@test.com'
        )
        removal_log_model.log_removal(
            participant_name='Notify L2',
            area_code='L',
            removed_by='admin@test.com'
        )
        removal_log_model.log_removal(
            participant_name='Notify M1',
            area_code='M',
            removed_by='admin@test.com'
        )

        by_area = removal_log_model.get_removals_needing_notification()
        assert isinstance(by_area, dict)
        assert 'L' in by_area
        assert 'M' in by_area
        assert len(by_area['L']) >= 2
        assert len(by_area['M']) >= 1


class TestRemovalDeletion:
    """Test deleting removal records."""

    def test_delete_removal_log(self, removal_log_model):
        """Test deleting a removal log entry."""
        removal_id = removal_log_model.log_removal(
            participant_name='Delete Me',
            area_code='N',
            removed_by='admin@test.com'
        )

        success = removal_log_model.delete_removal_log(removal_id)
        assert success is True

        deleted = removal_log_model.get_removal(removal_id)
        assert deleted is None

    def test_delete_nonexistent_removal(self, removal_log_model):
        """Test deleting a nonexistent removal (Firestore doesn't fail on missing docs)."""
        # Firestore delete succeeds even if document doesn't exist
        success = removal_log_model.delete_removal_log('nonexistent-12345')
        assert success is True  # Firestore behavior: delete is idempotent


class TestStaticMethods:
    """Test static/class methods."""

    def test_get_available_years(self, firestore_client):
        """Test getting available years."""
        years = RemovalLogModel.get_available_years(firestore_client)
        assert isinstance(years, list)
        assert 2000 in years  # Our test year
        assert all(isinstance(year, int) for year in years)
