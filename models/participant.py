# Updated by Claude AI at 2025-01-15 14:35:12
from google.cloud import firestore
from datetime import datetime
from typing import List, Dict, Optional
import logging


class ParticipantModel:
    """Handle Firestore operations for participants with year-aware collections."""

    def __init__(self, db_client, year: int = None):
        self.db = db_client
        self.year = year or datetime.now().year
        self.collection = f'participants_{self.year}'
        self.logger = logging.getLogger(__name__)

    def add_participant(self, participant_data: Dict) -> str:
        """Add a new participant to the year-specific collection."""
        participant_data['created_at'] = datetime.now()
        participant_data['updated_at'] = datetime.now()
        participant_data['year'] = self.year

        # Ensure is_leader defaults to False (admin-assigned only)
        participant_data.setdefault('is_leader', False)
        participant_data.setdefault('assigned_area_leader', None)
        
        # Set defaults for new fields
        participant_data.setdefault('notes_to_organizers', '')
        participant_data.setdefault('has_binoculars', False)
        participant_data.setdefault('spotting_scope', False)
        participant_data.setdefault('participation_type', 'regular')

        doc_ref = self.db.collection(self.collection).add(participant_data)
        self.logger.info(f"Added participant to {self.collection}: {participant_data.get('email')}")
        return doc_ref[1].id

    def get_participant(self, participant_id: str) -> Optional[Dict]:
        """Get a participant by ID from the year-specific collection."""
        doc = self.db.collection(self.collection).document(participant_id).get()
        if doc.exists:
            data = doc.to_dict()
            data['id'] = doc.id
            return data
        return None

    def get_participants_by_area(self, area_code: str) -> List[Dict]:
        """Get all participants for a specific area in the current year."""
        participants = []
        query = self.db.collection(self.collection).where('preferred_area', '==', area_code)

        for doc in query.stream():
            data = doc.to_dict()
            data['id'] = doc.id
            participants.append(data)

        return participants

    def get_unassigned_participants(self) -> List[Dict]:
        """Get all participants with preferred_area = 'UNASSIGNED'."""
        participants = []
        query = self.db.collection(self.collection).where('preferred_area', '==', 'UNASSIGNED')

        for doc in query.stream():
            data = doc.to_dict()
            data['id'] = doc.id
            participants.append(data)

        return participants

    def assign_participant_to_area(self, participant_id: str, area_code: str, assigned_by: str) -> bool:
        """Assign an unassigned participant to a specific area."""
        try:
            updates = {
                'preferred_area': area_code,
                'updated_at': datetime.now(),
                'assigned_by': assigned_by,
                'assigned_at': datetime.now()
            }
            self.db.collection(self.collection).document(participant_id).update(updates)
            self.logger.info(f"Assigned participant {participant_id} to area {area_code}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to assign participant {participant_id}: {e}")
            return False

    def get_area_counts(self) -> Dict[str, int]:
        """Get participant count by area for the current year."""
        counts = {}
        query = self.db.collection(self.collection)

        for doc in query.stream():
            data = doc.to_dict()
            area = data.get('preferred_area', 'UNKNOWN')
            if area != 'UNASSIGNED':  # Don't count unassigned in area totals
                counts[area] = counts.get(area, 0) + 1

        return counts

    def get_participants_by_email(self, email: str) -> List[Dict]:
        """Get all participants with a specific email address."""
        participants = []
        query = self.db.collection(self.collection).where('email', '==', email.lower())
        
        for doc in query.stream():
            data = doc.to_dict()
            data['id'] = doc.id
            participants.append(data)
        
        return participants

    def update_participant(self, participant_id: str, updates: Dict) -> bool:
        """Update a participant's information."""
        try:
            updates['updated_at'] = datetime.now()
            self.db.collection(self.collection).document(participant_id).update(updates)
            return True
        except Exception as e:
            self.logger.error(f"Failed to update participant {participant_id}: {e}")
            return False

    def delete_participant(self, participant_id: str) -> bool:
        """Delete a participant (current year only)."""
        try:
            self.db.collection(self.collection).document(participant_id).delete()
            self.logger.info(f"Deleted participant {participant_id} from {self.collection}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to delete participant {participant_id}: {e}")
            return False

    def get_all_participants(self) -> List[Dict]:
        """Get all participants for the current year."""
        participants = []
        query = self.db.collection(self.collection).order_by('created_at', direction=firestore.Query.DESCENDING)

        for doc in query.stream():
            data = doc.to_dict()
            data['id'] = doc.id
            participants.append(data)

        return participants

    def email_exists(self, email: str) -> bool:
        """Check if an email is already registered for the current year."""
        query = self.db.collection(self.collection).where('email', '==', email.lower())
        docs = list(query.stream())
        return len(docs) > 0

    def get_participants_interested_in_leadership(self) -> List[Dict]:
        """Get participants who expressed interest in leadership but aren't assigned as leaders."""
        participants = []
        query = (self.db.collection(self.collection)
                 .where('interested_in_leadership', '==', True)
                 .where('is_leader', '==', False))

        for doc in query.stream():
            data = doc.to_dict()
            data['id'] = doc.id
            participants.append(data)

        return participants

    def assign_leadership(self, participant_id: str, area_code: str, assigned_by: str) -> bool:
        """Assign leadership role to a participant."""
        try:
            updates = {
                'is_leader': True,
                'assigned_area_leader': area_code,
                'leadership_assigned_by': assigned_by,
                'leadership_assigned_at': datetime.now(),
                'updated_at': datetime.now()
            }
            self.db.collection(self.collection).document(participant_id).update(updates)
            self.logger.info(f"Assigned leadership of area {area_code} to participant {participant_id}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to assign leadership: {e}")
            return False

    def remove_leadership(self, participant_id: str, removed_by: str) -> bool:
        """Remove leadership role from a participant."""
        try:
            updates = {
                'is_leader': False,
                'assigned_area_leader': None,
                'leadership_removed_by': removed_by,
                'leadership_removed_at': datetime.now(),
                'updated_at': datetime.now()
            }
            self.db.collection(self.collection).document(participant_id).update(updates)
            self.logger.info(f"Removed leadership from participant {participant_id}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to remove leadership: {e}")
            return False

    def get_historical_participants(self, area_code: str, years_back: int = 3) -> List[Dict]:
        """Get participants for an area across multiple years, with email deduplication."""
        current_year = datetime.now().year
        participants = {}  # email -> most recent participant data

        for year in range(current_year - years_back, current_year + 1):
            try:
                year_model = ParticipantModel(self.db, year)
                year_participants = year_model.get_participants_by_area(area_code)

                for participant in year_participants:
                    email = participant.get('email', '').lower()
                    if email:
                        # Keep most recent data (later years override earlier ones)
                        participants[email] = participant

            except Exception as e:
                self.logger.warning(f"Could not access participants_{year}: {e}")
                continue

        return list(participants.values())

    @classmethod
    def get_available_years(cls, db_client) -> List[int]:
        """Get list of years that have participant data."""
        try:
            collections = db_client.collections()
            years = []

            for collection in collections:
                if collection.id.startswith('participants_'):
                    try:
                        year = int(collection.id.split('_')[1])
                        years.append(year)
                    except (ValueError, IndexError):
                        continue

            return sorted(years, reverse=True)

        except Exception as e:
            logging.error(f"Failed to get available years: {e}")
            return [datetime.now().year]