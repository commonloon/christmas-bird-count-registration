# Database Utilities for Test Suite
# Updated by Claude AI on 2025-09-22
# Updated by Claude AI on 2026-09-08 (Firestore -> Postgres)

"""
Utilities for managing database state during testing.
Provides functions for cleaning, populating, and validating test data.
"""

import logging
import time
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional

from tests.test_config import TEST_CONFIG, TEST_CIRCLE_SLUG
from models.db import Participant, RemovalLog
from models.participant import ParticipantModel

logger = logging.getLogger(__name__)

class DatabaseManager:
    """Manages database operations for testing."""

    def __init__(self, db_session, circle_slug: Optional[str] = None):
        self.db = db_session
        self.circle_slug = circle_slug or TEST_CIRCLE_SLUG
        self.current_year = TEST_CONFIG['current_year']
        self.isolation_year = TEST_CONFIG['isolation_test_year']

    def clear_test_collections(self, year: Optional[int] = None) -> bool:
        """
        Clear participant/removal_log rows for the given year (or both the
        current and isolation test years if none given), scoped to this
        circle.

        Returns:
            bool: True if successful
        """
        try:
            years_to_clear = [year] if year else [self.current_year, self.isolation_year]

            for test_year in years_to_clear:
                self.db.query(Participant).filter_by(circle_slug=self.circle_slug, year=test_year).delete()
                self.db.query(RemovalLog).filter_by(circle_slug=self.circle_slug, year=test_year).delete()

            self.db.commit()
            logger.info(f"Cleared test data for {self.circle_slug}, years: {years_to_clear}")
            return True

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to clear test collections: {e}")
            return False

    def create_test_participant(self, participant_data: Dict[str, Any], year: Optional[int] = None) -> int:
        """
        Create a test participant record.

        Args:
            participant_data: Participant data dictionary
            year: Year for the record (defaults to current year)

        Returns:
            int: ID of the created participant
        """
        test_year = year or self.current_year
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
            'is_leader': False,
        }
        final_data = {**required_defaults, **participant_data}

        model = ParticipantModel(self.db, year=test_year, circle_slug=self.circle_slug)
        participant_id = model.add_participant(final_data)
        logger.info(f"Created test participant {participant_id} for {self.circle_slug} {test_year}")
        return participant_id

    def create_test_leader(self, leader_data: Dict[str, Any], year: Optional[int] = None) -> int:
        """
        Create a test participant with a leadership role assigned.

        Args:
            leader_data: Leader data dictionary. 'area_code' maps to
                assigned_area_leader; 'leader_email' is also accepted as an
                alias for 'email' for compatibility with older callers.
            year: Year for the record (defaults to current year)

        Returns:
            int: ID of the created participant/leader
        """
        test_year = year or self.current_year
        required_defaults = {
            'first_name': 'Test',
            'last_name': 'Leader',
            'email': leader_data.get('leader_email') or f'test-leader-{int(time.time())}@example.com',
            'phone': '555-0456',
            'preferred_area': leader_data.get('area_code', 'A'),
        }
        final_data = {**required_defaults, **leader_data}
        final_data.setdefault('email', final_data.get('leader_email'))
        final_data['is_leader'] = True
        final_data['assigned_area_leader'] = final_data.get('area_code', final_data.get('preferred_area'))
        final_data['leadership_assigned_by'] = final_data.get('assigned_by', 'test-admin@example.com')
        final_data['leadership_assigned_at'] = datetime.now(timezone.utc)

        model = ParticipantModel(self.db, year=test_year, circle_slug=self.circle_slug)
        participant_id = model.add_participant(final_data)
        logger.info(f"Created test leader {participant_id} for {self.circle_slug} {test_year}")
        return participant_id

    def get_participant_count(self, area_code: Optional[str] = None, year: Optional[int] = None) -> int:
        """Get participant count for an area or total."""
        test_year = year or self.current_year
        query = self.db.query(Participant).filter_by(circle_slug=self.circle_slug, year=test_year)
        if area_code:
            query = query.filter_by(preferred_area=area_code)
        return query.count()

    def get_leader_count(self, area_code: Optional[str] = None, year: Optional[int] = None) -> int:
        """Get leader count for an area or total (leadership is a flag on the
        participant row, not a separate table, since the single-table
        leadership migration)."""
        test_year = year or self.current_year
        query = self.db.query(Participant).filter_by(circle_slug=self.circle_slug, year=test_year, is_leader=True)
        if area_code:
            query = query.filter_by(assigned_area_leader=area_code)
        return query.count()

    def verify_data_consistency(self, year: Optional[int] = None) -> Dict[str, Any]:
        """
        Verify basic data consistency for the given year: no duplicate
        (first_name, last_name, email) identities, and every leader row has
        an assigned area. (There's no separate leader table to cross-check
        against post-single-table-leadership migration.)
        """
        test_year = year or self.current_year
        results = {
            'consistent': True,
            'issues': [],
            'duplicate_identities': [],
        }

        try:
            rows = self.db.query(Participant).filter_by(circle_slug=self.circle_slug, year=test_year).all()

            identity_counts: Dict[tuple, int] = {}
            for row in rows:
                identity = (row.first_name, row.last_name, row.email)
                identity_counts[identity] = identity_counts.get(identity, 0) + 1

                if row.is_leader and not row.assigned_area_leader:
                    results['issues'].append(f"Participant {row.id} is_leader=True but has no assigned_area_leader")
                    results['consistent'] = False

            duplicates = {identity: count for identity, count in identity_counts.items() if count > 1}
            if duplicates:
                results['duplicate_identities'] = duplicates
                results['consistent'] = False

            if results['consistent']:
                logger.info(f"Data consistency check passed for {self.circle_slug} {test_year}")
            else:
                logger.warning(f"Data consistency issues for {self.circle_slug} {test_year}: {len(results['issues'])} issues")

            return results

        except Exception as e:
            logger.error(f"Failed to verify data consistency: {e}")
            return {'consistent': False, 'error': str(e)}

    def get_database_stats(self, year: Optional[int] = None) -> Dict[str, int]:
        """Get row-count statistics for testing."""
        test_year = year or self.current_year
        try:
            participant_count = self.db.query(Participant).filter_by(circle_slug=self.circle_slug, year=test_year).count()
            leader_count = self.db.query(Participant).filter_by(
                circle_slug=self.circle_slug, year=test_year, is_leader=True
            ).count()
            removal_log_count = self.db.query(RemovalLog).filter_by(circle_slug=self.circle_slug, year=test_year).count()

            stats = {
                'participants': participant_count,
                'leaders': leader_count,
                'removal_log': removal_log_count,
            }
            logger.info(f"Database stats for {self.circle_slug} {test_year}: {stats}")
            return stats

        except Exception as e:
            logger.error(f"Failed to get database stats: {e}")
            return {}

def create_database_manager(db_session, circle_slug: Optional[str] = None) -> DatabaseManager:
    """
    Factory function to create a DatabaseManager instance.

    Args:
        db_session: SQLAlchemy session
        circle_slug: Circle to scope operations to (defaults to TEST_CIRCLE_SLUG)

    Returns:
        DatabaseManager: Configured database manager
    """
    return DatabaseManager(db_session, circle_slug)
