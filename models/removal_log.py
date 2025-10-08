from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter
from datetime import datetime
from typing import List, Dict, Optional
import logging


class RemovalLogModel:
    """Handle Firestore operations for participant removal tracking with year-aware collections."""

    def __init__(self, db_client, year: int = None):
        self.db = db_client
        self.year = year or datetime.now().year
        self.collection = f'removal_log_{self.year}'
        self.logger = logging.getLogger(__name__)

    def log_removal(self, participant_name: str, area_code: str, removed_by: str,
                    reason: str = '', participant_email: str = '') -> str:
        """Log a participant removal."""
        removal_data = {
            'participant_name': participant_name,
            'participant_email': participant_email,
            'area_code': area_code,
            'removed_by': removed_by,
            'reason': reason,
            'removed_at': datetime.now(),
            'year': self.year,
            'emailed': False
        }

        doc_ref = self.db.collection(self.collection).add(removal_data)
        self.logger.info(f"Logged removal: {participant_name} from area {area_code}")
        return doc_ref[1].id

    def get_removal(self, removal_id: str) -> Optional[Dict]:
        """Get a removal log entry by ID."""
        doc = self.db.collection(self.collection).document(removal_id).get()
        if doc.exists:
            data = doc.to_dict()
            data['id'] = doc.id
            return data
        return None

    def get_pending_removals(self) -> List[Dict]:
        """Get removals that haven't been emailed yet for the current year."""
        removals = []
        query = self.db.collection(self.collection).where(filter=FieldFilter('emailed', '==', False))

        for doc in query.stream():
            data = doc.to_dict()
            data['id'] = doc.id
            removals.append(data)

        return removals

    def get_pending_removals_by_area(self, area_code: str) -> List[Dict]:
        """Get pending removals for a specific area."""
        removals = []
        query = (self.db.collection(self.collection)
                 .where(filter=FieldFilter('emailed', '==', False))
                 .where(filter=FieldFilter('area_code', '==', area_code)))

        for doc in query.stream():
            data = doc.to_dict()
            data['id'] = doc.id
            removals.append(data)

        return removals

    def get_all_removals(self, limit: int = None) -> List[Dict]:
        """Get all removal log entries for the current year."""
        removals = []
        query = self.db.collection(self.collection).order_by('removed_at', direction=firestore.Query.DESCENDING)

        if limit:
            query = query.limit(limit)

        for doc in query.stream():
            data = doc.to_dict()
            data['id'] = doc.id
            removals.append(data)

        return removals

    def get_removals_by_area(self, area_code: str) -> List[Dict]:
        """Get all removals for a specific area in the current year."""
        removals = []
        query = (self.db.collection(self.collection)
                 .where(filter=FieldFilter('area_code', '==', area_code))
                 .order_by('removed_at', direction=firestore.Query.DESCENDING))

        for doc in query.stream():
            data = doc.to_dict()
            data['id'] = doc.id
            removals.append(data)

        return removals

    def mark_removals_emailed(self, removal_ids: List[str]) -> bool:
        """Mark removals as having been emailed."""
        try:
            batch = self.db.batch()
            timestamp = datetime.now()

            for removal_id in removal_ids:
                doc_ref = self.db.collection(self.collection).document(removal_id)
                batch.update(doc_ref, {
                    'emailed': True,
                    'emailed_at': timestamp
                })

            batch.commit()
            self.logger.info(f"Marked {len(removal_ids)} removals as emailed")
            return True

        except Exception as e:
            self.logger.error(f"Failed to mark removals as emailed: {e}")
            return False

    def mark_removal_emailed(self, removal_id: str) -> bool:
        """Mark a single removal as having been emailed."""
        try:
            updates = {
                'emailed': True,
                'emailed_at': datetime.now()
            }
            self.db.collection(self.collection).document(removal_id).update(updates)
            return True
        except Exception as e:
            self.logger.error(f"Failed to mark removal {removal_id} as emailed: {e}")
            return False

    def get_removal_stats(self) -> Dict:
        """Get removal statistics for the current year."""
        all_removals = self.get_all_removals()
        pending_removals = self.get_pending_removals()

        # Count by area
        by_area = {}
        for removal in all_removals:
            area = removal.get('area_code', 'UNKNOWN')
            by_area[area] = by_area.get(area, 0) + 1

        # Count by reason
        by_reason = {}
        for removal in all_removals:
            reason = removal.get('reason', 'No reason provided')
            by_reason[reason] = by_reason.get(reason, 0) + 1

        return {
            'total_removals': len(all_removals),
            'pending_email': len(pending_removals),
            'by_area': by_area,
            'by_reason': by_reason,
            'year': self.year
        }

    def delete_removal_log(self, removal_id: str) -> bool:
        """Delete a removal log entry (admin only, rare use case)."""
        try:
            self.db.collection(self.collection).document(removal_id).delete()
            self.logger.info(f"Deleted removal log entry {removal_id}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to delete removal log {removal_id}: {e}")
            return False

    def get_recent_removals(self, days_back: int = 7) -> List[Dict]:
        """Get removals from the last N days."""
        from datetime import timedelta
        cutoff_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        cutoff_date = cutoff_date - timedelta(days=days_back)

        removals = []
        query = (self.db.collection(self.collection)
                 .where(filter=FieldFilter('removed_at', '>=', cutoff_date))
                 .order_by('removed_at', direction=firestore.Query.DESCENDING))

        for doc in query.stream():
            data = doc.to_dict()
            data['id'] = doc.id
            removals.append(data)

        return removals

    def get_removals_since(self, area_code: str, since_timestamp: datetime) -> List[Dict]:
        """Get removals for a specific area since the given timestamp."""
        removals = []
        query = (self.db.collection(self.collection)
                 .where(filter=FieldFilter('area_code', '==', area_code))
                 .where(filter=FieldFilter('removed_at', '>=', since_timestamp))
                 .order_by('removed_at', direction=firestore.Query.DESCENDING))

        for doc in query.stream():
            data = doc.to_dict()
            data['id'] = doc.id
            removals.append(data)

        return removals

    def get_removals_needing_notification(self) -> Dict[str, List[Dict]]:
        """Get pending removals grouped by area for email notifications."""
        pending = self.get_pending_removals()
        by_area = {}

        for removal in pending:
            area_code = removal.get('area_code', 'UNKNOWN')
            if area_code not in by_area:
                by_area[area_code] = []
            by_area[area_code].append(removal)

        return by_area

    @classmethod
    def get_available_years(cls, db_client) -> List[int]:
        """Get list of years that have removal log data."""
        try:
            collections = db_client.collections()
            years = []

            for collection in collections:
                if collection.id.startswith('removal_log_'):
                    try:
                        year = int(collection.id.split('_')[2])
                        years.append(year)
                    except (ValueError, IndexError):
                        continue

            return sorted(years, reverse=True)

        except Exception as e:
            logging.error(f"Failed to get available years for removal logs: {e}")
            return [datetime.now().year]