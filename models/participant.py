# Updated by Claude AI on 2025-09-16
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

        # Ensure leadership fields default to appropriate values
        participant_data.setdefault('is_leader', False)
        participant_data.setdefault('assigned_area_leader', None)
        participant_data.setdefault('leadership_assigned_by', None)
        participant_data.setdefault('leadership_assigned_at', None)
        participant_data.setdefault('leadership_removed_by', None)
        participant_data.setdefault('leadership_removed_at', None)
        
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

    def get_participant_by_email_and_names(self, email: str, first_name: str, last_name: str) -> Optional[Dict]:
        """Get participant by exact email + first_name + last_name match."""
        query = (self.db.collection(self.collection)
                .where('email', '==', email.lower())
                .where('first_name', '==', first_name)
                .where('last_name', '==', last_name))

        docs = list(query.stream())
        if docs:
            data = docs[0].to_dict()
            data['id'] = docs[0].id
            return data
        return None

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
        """Delete a participant (single table - no synchronization needed)."""
        try:
            participant = self.get_participant(participant_id)
            if not participant:
                self.logger.error(f"Participant {participant_id} not found for deletion")
                return False

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

    def email_name_exists(self, email: str, first_name: str, last_name: str) -> bool:
        """Check if email+name combination exists for current year."""
        query = (self.db.collection(self.collection)
                .where('email', '==', email.lower())
                .where('first_name', '==', first_name)
                .where('last_name', '==', last_name))
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

    def get_leaders(self) -> List[Dict]:
        """Get all active leaders for the current year."""
        leaders = []
        query = (self.db.collection(self.collection)
                 .where('is_leader', '==', True))

        for doc in query.stream():
            data = doc.to_dict()
            data['id'] = doc.id
            leaders.append(data)

        return leaders

    def get_leaders_by_area(self, area_code: str) -> List[Dict]:
        """Get all active leaders for a specific area."""
        leaders = []
        query = (self.db.collection(self.collection)
                 .where('is_leader', '==', True)
                 .where('assigned_area_leader', '==', area_code))

        for doc in query.stream():
            data = doc.to_dict()
            data['id'] = doc.id
            leaders.append(data)

        return leaders

    def is_area_leader(self, email: str, area_code: str = None) -> bool:
        """Check if an email is an area leader (optionally for a specific area)."""
        query = (self.db.collection(self.collection)
                 .where('email', '==', email.lower())
                 .where('is_leader', '==', True))

        if area_code:
            query = query.where('assigned_area_leader', '==', area_code)

        docs = list(query.stream())
        return len(docs) > 0

    def get_leaders_by_identity(self, first_name: str, last_name: str, email: str) -> List[Dict]:
        """Get all leaders matching exact identity (first_name, last_name, email)."""
        leaders = []
        query = (self.db.collection(self.collection)
                 .where('is_leader', '==', True))

        search_first = first_name.strip().lower()
        search_last = last_name.strip().lower()
        search_email = email.lower().strip()

        for doc in query.stream():
            data = doc.to_dict()
            data['id'] = doc.id

            stored_first = data.get('first_name', '').strip().lower()
            stored_last = data.get('last_name', '').strip().lower()
            stored_email = data.get('email', '').strip().lower()

            if (stored_first == search_first and
                stored_last == search_last and
                stored_email == search_email):
                leaders.append(data)

        return leaders

    def get_areas_without_leaders(self) -> List[str]:
        """Get list of area codes that don't have assigned leaders."""
        from config.areas import get_all_areas

        all_areas = set(get_all_areas())
        assigned_areas = set()

        leaders = self.get_leaders()
        for leader in leaders:
            area_code = leader.get('assigned_area_leader')
            if area_code:
                assigned_areas.add(area_code)

        return sorted(all_areas - assigned_areas)

    def assign_area_leadership(self, participant_id: str, area_code: str, assigned_by: str) -> bool:
        """Assign area leadership to a participant."""
        try:
            updates = {
                'is_leader': True,
                'assigned_area_leader': area_code,
                'preferred_area': area_code,  # Update participant area to match leadership area
                'leadership_assigned_by': assigned_by,
                'leadership_assigned_at': datetime.now(),
                'updated_at': datetime.now()
            }
            self.db.collection(self.collection).document(participant_id).update(updates)
            self.logger.info(f"Assigned area leadership of {area_code} to participant {participant_id} and updated their area preference")
            return True
        except Exception as e:
            self.logger.error(f"Failed to assign area leadership: {e}")
            return False

    def remove_area_leadership(self, participant_id: str, removed_by: str) -> bool:
        """Remove area leadership from a participant."""
        try:
            updates = {
                'is_leader': False,
                'assigned_area_leader': None,
                'leadership_removed_by': removed_by,
                'leadership_removed_at': datetime.now(),
                'updated_at': datetime.now()
            }
            self.db.collection(self.collection).document(participant_id).update(updates)
            self.logger.info(f"Removed area leadership from participant {participant_id}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to remove area leadership: {e}")
            return False

    def deactivate_leaders_by_identity(self, first_name: str, last_name: str, email: str, removed_by: str) -> bool:
        """Deactivate all leaders matching exact identity (first_name, last_name, email)."""
        try:
            matching_leaders = self.get_leaders_by_identity(first_name, last_name, email)

            if not matching_leaders:
                self.logger.info(f"No active leaders found for identity: {first_name} {last_name} <{email}>")
                return True

            deactivated_count = 0
            for leader in matching_leaders:
                if self.remove_area_leadership(leader['id'], removed_by):
                    deactivated_count += 1
                    area_code = leader.get('assigned_area_leader', 'unknown')
                    self.logger.info(f"Deactivated leader {leader['id']} for {first_name} {last_name} in area {area_code}")
                else:
                    self.logger.error(f"Failed to deactivate leader {leader['id']} for {first_name} {last_name}")

            success = deactivated_count == len(matching_leaders)
            if success:
                self.logger.info(f"Successfully deactivated {deactivated_count} leader(s) for {first_name} {last_name} <{email}>")
            else:
                self.logger.error(f"Only deactivated {deactivated_count}/{len(matching_leaders)} leader(s) for {first_name} {last_name} <{email}>")

            return success

        except Exception as e:
            self.logger.error(f"Failed to deactivate leaders by identity {first_name} {last_name} <{email}>: {e}")
            return False

    def add_leader(self, leader_data: Dict) -> str:
        """Add a new participant with leadership role. Returns participant ID or raises exception if identity exists."""
        first_name = leader_data.get('first_name', '')
        last_name = leader_data.get('last_name', '')
        email = leader_data.get('email', '')

        # Check if participant with this identity already exists
        existing = self.get_participant_by_email_and_names(email, first_name, last_name)
        if existing:
            raise ValueError(f"Participant with identity ({first_name}, {last_name}, {email}) already exists. Use participant editing to update existing records.")

        # Create new participant with leadership
        participant_data = {
            'first_name': first_name,
            'last_name': last_name,
            'email': email.lower(),
            'phone': leader_data.get('phone', ''),
            'is_leader': True,
            'assigned_area_leader': leader_data.get('area_code'),
            'leadership_assigned_by': leader_data.get('assigned_by'),
            'leadership_assigned_at': datetime.now(),
            'preferred_area': leader_data.get('area_code'),  # Leader's preferred area matches their leadership area
            'experience_level': 'Expert',  # Assume leaders are experienced
            'participation_type': 'regular'
        }

        return self.add_participant(participant_data)

    def assign_leader(self, area_code: str, leader_email: str, first_name: str,
                      last_name: str, phone: str, assigned_by: str) -> str:
        """Assign a leader to an area (wrapper for add_leader with compatible interface)."""
        leader_data = {
            'area_code': area_code,
            'leader_email': leader_email,
            'first_name': first_name,
            'last_name': last_name,
            'phone': phone,
            'assigned_by': assigned_by
        }
        return self.add_leader(leader_data)

    def remove_leader(self, participant_id: str, removed_by: str) -> bool:
        """Remove leadership from a participant (wrapper for remove_area_leadership)."""
        return self.remove_area_leadership(participant_id, removed_by)

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