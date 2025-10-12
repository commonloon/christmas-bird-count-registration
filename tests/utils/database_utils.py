# Database Utilities for Test Suite
# Updated by Claude AI on 2025-09-22

"""
Utilities for managing database state during testing.
Provides functions for cleaning, populating, and validating test data.
"""

import logging
import time
from datetime import datetime
from typing import Dict, List, Any, Optional

from google.cloud import firestore
from tests.test_config import TEST_CONFIG

logger = logging.getLogger(__name__)

class DatabaseManager:
    """Manages database operations for testing."""

    def __init__(self, firestore_client: firestore.Client):
        self.db = firestore_client
        self.current_year = TEST_CONFIG['current_year']
        self.isolation_year = TEST_CONFIG['isolation_test_year']

    def clear_test_collections(self, year: Optional[int] = None) -> bool:
        """
        Clear test data collections for specified year.

        Args:
            year: Year to clear. If None, clears both current and isolation years.

        Returns:
            bool: True if successful
        """
        try:
            years_to_clear = [year] if year else [self.current_year, self.isolation_year]

            for test_year in years_to_clear:
                collections = [
                    f'participants_{test_year}',
                    f'area_leaders_{test_year}',
                    f'removal_log_{test_year}'
                ]

                for collection_name in collections:
                    self._clear_collection(collection_name)

            logger.info(f"Cleared test collections for years: {years_to_clear}")
            return True

        except Exception as e:
            logger.error(f"Failed to clear test collections: {e}")
            return False

    def _clear_collection(self, collection_name: str, batch_size: int = 500):
        """Clear a single collection in batches."""
        try:
            collection_ref = self.db.collection(collection_name)

            while True:
                docs = list(collection_ref.limit(batch_size).stream())
                if not docs:
                    break

                batch = self.db.batch()
                for doc in docs:
                    batch.delete(doc.reference)
                batch.commit()

                logger.debug(f"Deleted {len(docs)} documents from {collection_name}")

            logger.info(f"Collection {collection_name} cleared")

        except Exception as e:
            logger.error(f"Error clearing collection {collection_name}: {e}")

    def create_test_participant(self, participant_data: Dict[str, Any], year: Optional[int] = None) -> str:
        """
        Create a test participant record.

        Args:
            participant_data: Participant data dictionary
            year: Year for the record (defaults to current year)

        Returns:
            str: Document ID of created participant
        """
        try:
            test_year = year or self.current_year
            collection_name = f'participants_{test_year}'

            # Ensure required fields
            required_defaults = {
                'first_name': 'Test',
                'last_name': 'Participant',
                'email': f'test-{int(time.time())}@example.com',
                'phone': '555-0123',
                'skill_level': 'Beginner',
                'experience': 'None',
                'preferred_area': 'A',
                'participation_type': 'regular',
                'has_binoculars': True,
                'spotting_scope': False,
                'notes_to_organizers': '',
                'interested_in_leadership': False,
                'interested_in_scribe': False,
                'is_leader': False,
                'auto_assigned': False,
                'created_at': firestore.SERVER_TIMESTAMP,
                'updated_at': firestore.SERVER_TIMESTAMP,
                'year': test_year
            }

            # Merge with provided data
            final_data = {**required_defaults, **participant_data}

            # Create document
            doc_ref = self.db.collection(collection_name).add(final_data)
            doc_id = doc_ref[1].id

            logger.info(f"Created test participant {doc_id} in {collection_name}")
            return doc_id

        except Exception as e:
            logger.error(f"Failed to create test participant: {e}")
            raise

    def create_test_leader(self, leader_data: Dict[str, Any], year: Optional[int] = None) -> str:
        """
        Create a test area leader record.

        Args:
            leader_data: Leader data dictionary
            year: Year for the record (defaults to current year)

        Returns:
            str: Document ID of created leader
        """
        try:
            test_year = year or self.current_year
            collection_name = f'area_leaders_{test_year}'

            # Ensure required fields
            required_defaults = {
                'area_code': 'A',
                'first_name': 'Test',
                'last_name': 'Leader',
                'leader_email': f'test-leader-{int(time.time())}@example.com',
                'cell_phone': '555-0456',
                'assigned_by': 'test-admin@example.com',
                'assigned_at': firestore.SERVER_TIMESTAMP,
                'active': True,
                'year': test_year,
                'created_from_participant': False,
                'notes': ''
            }

            # Merge with provided data
            final_data = {**required_defaults, **leader_data}

            # Create document
            doc_ref = self.db.collection(collection_name).add(final_data)
            doc_id = doc_ref[1].id

            logger.info(f"Created test leader {doc_id} in {collection_name}")
            return doc_id

        except Exception as e:
            logger.error(f"Failed to create test leader: {e}")
            raise

    def get_participant_count(self, area_code: Optional[str] = None, year: Optional[int] = None) -> int:
        """
        Get participant count for an area or total.

        Args:
            area_code: Area code to filter by (None for total)
            year: Year to query (defaults to current year)

        Returns:
            int: Number of participants
        """
        try:
            test_year = year or self.current_year
            collection_name = f'participants_{test_year}'

            query = self.db.collection(collection_name)
            if area_code:
                query = query.where('preferred_area', '==', area_code)

            docs = list(query.stream())
            count = len(docs)

            logger.debug(f"Found {count} participants for area {area_code or 'ALL'} in {test_year}")
            return count

        except Exception as e:
            logger.error(f"Failed to get participant count: {e}")
            return 0

    def get_leader_count(self, area_code: Optional[str] = None, year: Optional[int] = None) -> int:
        """
        Get leader count for an area or total.

        Args:
            area_code: Area code to filter by (None for total)
            year: Year to query (defaults to current year)

        Returns:
            int: Number of leaders
        """
        try:
            test_year = year or self.current_year
            collection_name = f'area_leaders_{test_year}'

            query = self.db.collection(collection_name)
            if area_code:
                query = query.where('area_code', '==', area_code)

            docs = list(query.stream())
            count = len(docs)

            logger.debug(f"Found {count} leaders for area {area_code or 'ALL'} in {test_year}")
            return count

        except Exception as e:
            logger.error(f"Failed to get leader count: {e}")
            return 0

    def verify_data_consistency(self, year: Optional[int] = None) -> Dict[str, Any]:
        """
        Verify data consistency between participants and leaders collections.

        Args:
            year: Year to check (defaults to current year)

        Returns:
            dict: Consistency check results
        """
        try:
            test_year = year or self.current_year
            participants_collection = f'participants_{test_year}'
            leaders_collection = f'area_leaders_{test_year}'

            results = {
                'consistent': True,
                'issues': [],
                'participant_leaders': [],
                'leader_participants': [],
                'orphaned_leaders': [],
                'duplicate_emails': []
            }

            # Get all participants marked as leaders
            participant_leaders_query = self.db.collection(participants_collection).where('is_leader', '==', True)
            participant_leaders = list(participant_leaders_query.stream())

            # Get all area leaders
            area_leaders = list(self.db.collection(leaders_collection).stream())

            # Check for participants marked as leaders who don't have leader records
            participant_emails = {doc.to_dict().get('email'): doc.id for doc in participant_leaders}
            leader_emails = {doc.to_dict().get('leader_email'): doc.id for doc in area_leaders}

            for email, participant_id in participant_emails.items():
                if email not in leader_emails:
                    results['issues'].append(f"Participant {participant_id} marked as leader but no leader record")
                    results['consistent'] = False

            # Check for leaders without corresponding participant records
            for email, leader_id in leader_emails.items():
                if email not in participant_emails:
                    leader_doc = next(doc for doc in area_leaders if doc.id == leader_id)
                    if leader_doc.to_dict().get('created_from_participant', False):
                        results['issues'].append(f"Leader {leader_id} claims participant origin but no participant found")
                        results['consistent'] = False

            # Check for duplicate emails in participants
            all_participants = list(self.db.collection(participants_collection).stream())
            email_counts = {}
            for doc in all_participants:
                email = doc.to_dict().get('email')
                if email:
                    email_counts[email] = email_counts.get(email, 0) + 1

            duplicates = {email: count for email, count in email_counts.items() if count > 1}
            if duplicates:
                results['duplicate_emails'] = duplicates
                results['consistent'] = False

            results['participant_leaders'] = [doc.to_dict() for doc in participant_leaders]
            results['leader_participants'] = [doc.to_dict() for doc in area_leaders]

            if results['consistent']:
                logger.info(f"Data consistency check passed for year {test_year}")
            else:
                logger.warning(f"Data consistency issues found for year {test_year}: {len(results['issues'])} issues")

            return results

        except Exception as e:
            logger.error(f"Failed to verify data consistency: {e}")
            return {'consistent': False, 'error': str(e)}

    def wait_for_document_creation(self, collection_name: str, doc_id: str, timeout: int = 30) -> bool:
        """
        Wait for a document to be created (handles eventual consistency).

        Args:
            collection_name: Collection name
            doc_id: Document ID to wait for
            timeout: Maximum time to wait in seconds

        Returns:
            bool: True if document exists
        """
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                doc_ref = self.db.collection(collection_name).document(doc_id)
                doc = doc_ref.get()
                if doc.exists:
                    logger.debug(f"Document {doc_id} found in {collection_name}")
                    return True
            except Exception as e:
                logger.debug(f"Error checking document existence: {e}")

            time.sleep(1)

        logger.warning(f"Document {doc_id} not found in {collection_name} after {timeout}s")
        return False

    def get_database_stats(self, year: Optional[int] = None) -> Dict[str, int]:
        """
        Get database statistics for testing.

        Args:
            year: Year to check (defaults to current year)

        Returns:
            dict: Statistics including counts by collection
        """
        try:
            test_year = year or self.current_year
            collections = [
                f'participants_{test_year}',
                f'area_leaders_{test_year}',
                f'removal_log_{test_year}'
            ]

            stats = {}
            for collection_name in collections:
                try:
                    docs = list(self.db.collection(collection_name).stream())
                    stats[collection_name] = len(docs)
                except Exception as e:
                    logger.warning(f"Could not count {collection_name}: {e}")
                    stats[collection_name] = -1

            logger.info(f"Database stats for {test_year}: {stats}")
            return stats

        except Exception as e:
            logger.error(f"Failed to get database stats: {e}")
            return {}

def create_database_manager(firestore_client: firestore.Client) -> DatabaseManager:
    """
    Factory function to create a DatabaseManager instance.

    Args:
        firestore_client: Firestore client instance

    Returns:
        DatabaseManager: Configured database manager
    """
    return DatabaseManager(firestore_client)