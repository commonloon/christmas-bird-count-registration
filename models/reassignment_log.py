# Updated by Claude AI on 2025-10-24
from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter
from datetime import datetime, timezone
from typing import List, Dict, Optional
import logging


class ReassignmentLogModel:
    """Handle Firestore operations for participant reassignment logging (year-aware)."""

    def __init__(self, db_client, year: int = None):
        self.db = db_client
        self.year = year or datetime.now().year
        self.collection = f'reassignments_{self.year}'
        self.logger = logging.getLogger(__name__)

    def log_reassignment(self, participant_id: str, first_name: str, last_name: str,
                        email: str, old_area: str, new_area: str, changed_by: str) -> str:
        """Log a participant reassignment from one area to another.

        Args:
            participant_id: The ID of the reassigned participant
            first_name: Participant's first name (denormalized for audit trail)
            last_name: Participant's last name (denormalized for audit trail)
            email: Participant's email (denormalized for audit trail)
            old_area: Area code they were reassigned FROM
            new_area: Area code they were reassigned TO
            changed_by: Email of admin who performed the reassignment

        Returns:
            Document ID of the created log entry
        """
        reassignment_data = {
            'participant_id': participant_id,
            'first_name': first_name,
            'last_name': last_name,
            'email': email,
            'old_area': old_area,
            'new_area': new_area,
            'changed_by': changed_by,
            'changed_at': datetime.now(timezone.utc),
            'year': self.year
        }

        _, doc_ref = self.db.collection(self.collection).add(reassignment_data)
        self.logger.info(f"Logged reassignment for {first_name} {last_name} from area {old_area} to {new_area}")
        return doc_ref.id

    def get_reassignments_since(self, since_timestamp: datetime) -> List[Dict]:
        """Get all reassignments since a given timestamp.

        Args:
            since_timestamp: Only return reassignments with changed_at >= this time

        Returns:
            List of reassignment records
        """
        try:
            if since_timestamp.tzinfo is None:
                since_timestamp = since_timestamp.replace(tzinfo=timezone.utc)

            reassignments = []
            query = self.db.collection(self.collection).where(
                filter=FieldFilter('year', '==', self.year)
            )

            for doc in query.stream():
                data = doc.to_dict()
                data['id'] = doc.id

                # Filter by timestamp in memory (no composite index needed)
                changed_at = data.get('changed_at')
                if changed_at:
                    if changed_at.tzinfo is None:
                        changed_at = changed_at.replace(tzinfo=timezone.utc)

                    if changed_at >= since_timestamp:  # Use >= to include changes at exact same timestamp
                        reassignments.append(data)

            return reassignments

        except Exception as e:
            self.logger.error(f"Error getting reassignments since {since_timestamp}: {e}")
            return []

    def get_reassignments_for_area_since(self, area_code: str, since_timestamp: datetime) -> tuple:
        """Get reassignments affecting a specific area since timestamp.

        Args:
            area_code: The area code to filter by
            since_timestamp: Only return reassignments with changed_at >= this time

        Returns:
            Tuple of (arrivals, departures) where:
            - arrivals: List of participants reassigned INTO this area
            - departures: List of participants reassigned OUT OF this area
        """
        all_reassignments = self.get_reassignments_since(since_timestamp)

        arrivals = [r for r in all_reassignments if r.get('new_area') == area_code]
        departures = [r for r in all_reassignments if r.get('old_area') == area_code]

        return arrivals, departures

    def get_all_reassignments(self) -> List[Dict]:
        """Get all reassignments for the year (for auditing/reporting)."""
        try:
            reassignments = []
            query = self.db.collection(self.collection).order_by(
                'changed_at', direction=firestore.Query.DESCENDING
            )

            for doc in query.stream():
                data = doc.to_dict()
                data['id'] = doc.id
                reassignments.append(data)

            return reassignments

        except Exception as e:
            self.logger.error(f"Error getting all reassignments for year {self.year}: {e}")
            return []
