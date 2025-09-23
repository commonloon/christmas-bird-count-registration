from google.cloud import firestore
from datetime import datetime
from typing import List, Dict, Optional
import logging


class AreaLeaderModel:
    """Handle Firestore operations for area leaders with year-aware collections."""

    def __init__(self, db_client, year: int = None):
        self.db = db_client
        self.year = year or datetime.now().year
        self.collection = f'area_leaders_{self.year}'
        self.logger = logging.getLogger(__name__)

    def add_area_leader(self, leader_data: Dict) -> str:
        """Add a new area leader to the year-specific collection."""
        leader_data['assigned_date'] = datetime.now()
        leader_data['year'] = self.year
        leader_data.setdefault('active', True)

        doc_ref = self.db.collection(self.collection).add(leader_data)
        self.logger.info(
            f"Added area leader to {self.collection}: {leader_data.get('leader_email')} for area {leader_data.get('area_code')}")
        return doc_ref[1].id

    def add_leader(self, leader_data: Dict) -> str:
        """Add a new area leader (alias for add_area_leader for consistency)."""
        return self.add_area_leader(leader_data)

    def get_area_leader(self, leader_id: str) -> Optional[Dict]:
        """Get an area leader by ID from the year-specific collection."""
        doc = self.db.collection(self.collection).document(leader_id).get()
        if doc.exists:
            data = doc.to_dict()
            data['id'] = doc.id
            return data
        return None

    def get_leaders_by_area(self, area_code: str) -> List[Dict]:
        """Get all active leaders for a specific area in the current year."""
        leaders = []
        query = (self.db.collection(self.collection)
                 .where('area_code', '==', area_code)
                 .where('active', '==', True))

        for doc in query.stream():
            data = doc.to_dict()
            data['id'] = doc.id
            leaders.append(data)

        return leaders

    def get_leaders_for_area(self, area_code: str) -> List[Dict]:
        """Get all active leaders for a specific area (alias for get_leaders_by_area)."""
        return self.get_leaders_by_area(area_code)

    def get_leaders_by_email(self, email: str) -> List[Dict]:
        """Get all areas led by a specific email address in the current year."""
        leaders = []
        query = (self.db.collection(self.collection)
                 .where('leader_email', '==', email.lower())
                 .where('active', '==', True))

        for doc in query.stream():
            data = doc.to_dict()
            data['id'] = doc.id
            leaders.append(data)

        return leaders

    def is_area_leader(self, email: str, area_code: str = None) -> bool:
        """Check if an email is an area leader (optionally for a specific area)."""
        query = (self.db.collection(self.collection)
                 .where('leader_email', '==', email.lower())
                 .where('active', '==', True))

        if area_code:
            query = query.where('area_code', '==', area_code)

        docs = list(query.stream())
        return len(docs) > 0

    def get_all_leaders(self) -> List[Dict]:
        """Get all active area leaders for the current year."""
        leaders = []
        query = (self.db.collection(self.collection)
                 .where('active', '==', True)
                 .order_by('area_code'))

        for doc in query.stream():
            data = doc.to_dict()
            data['id'] = doc.id
            leaders.append(data)

        return leaders

    def get_areas_by_leader_email(self, email: str) -> List[Dict]:
        """Get all areas led by a specific email address."""
        leaders = []
        query = (self.db.collection(self.collection)
                 .where('leader_email', '==', email.lower())
                 .where('active', '==', True))

        for doc in query.stream():
            data = doc.to_dict()
            data['id'] = doc.id
            leaders.append(data)

        return leaders

    def get_areas_without_leaders(self) -> List[str]:
        """Get list of area codes that don't have assigned leaders."""
        from config.areas import get_all_areas

        all_areas = set(get_all_areas())
        assigned_areas = set()

        leaders = self.get_all_leaders()
        for leader in leaders:
            assigned_areas.add(leader.get('area_code'))

        return sorted(all_areas - assigned_areas)

    def assign_leader(self, area_code: str, leader_email: str, first_name: str,
                      last_name: str, cell_phone: str, assigned_by: str) -> str:
        """Assign a leader to an area."""
        leader_data = {
            'area_code': area_code,
            'leader_email': leader_email.lower(),
            'first_name': first_name,
            'last_name': last_name,
            'cell_phone': cell_phone,
            'assigned_by': assigned_by,
            'active': True
        }

        return self.add_area_leader(leader_data)

    def remove_leader(self, leader_id: str, removed_by: str) -> bool:
        """Deactivate an area leader."""
        try:
            updates = {
                'active': False,
                'removed_by': removed_by,
                'removed_date': datetime.now()
            }
            self.db.collection(self.collection).document(leader_id).update(updates)
            self.logger.info(f"Deactivated area leader {leader_id}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to remove area leader {leader_id}: {e}")
            return False

    def update_leader(self, leader_id: str, updates: Dict) -> bool:
        """Update area leader information."""
        try:
            updates['updated_at'] = datetime.now()
            self.db.collection(self.collection).document(leader_id).update(updates)
            return True
        except Exception as e:
            self.logger.error(f"Failed to update area leader {leader_id}: {e}")
            return False

    def get_leader_areas(self, email: str) -> List[str]:
        """Get list of area codes led by a specific email address."""
        leaders = self.get_leaders_by_email(email)
        return [leader.get('area_code') for leader in leaders if leader.get('area_code')]

    def get_area_leader_emails(self, area_code: str) -> List[str]:
        """Get list of leader email addresses for a specific area."""
        leaders = self.get_leaders_by_area(area_code)
        return [leader.get('leader_email') for leader in leaders if leader.get('leader_email')]


    def get_leader_contact_info(self, area_code: str) -> Dict:
        """Get consolidated contact information for area leaders."""
        leaders = self.get_leaders_by_area(area_code)

        if not leaders:
            return {
                'area_code': area_code,
                'has_leaders': False,
                'leader_count': 0,
                'emails': [],
                'names': [],
                'phones': []
            }

        return {
            'area_code': area_code,
            'has_leaders': True,
            'leader_count': len(leaders),
            'emails': [leader.get('leader_email') for leader in leaders],
            'names': [f"{leader.get('first_name', '')} {leader.get('last_name', '')}".strip() for leader in leaders],
            'phones': [leader.get('cell_phone') for leader in leaders if leader.get('cell_phone')]
        }

    @classmethod
    def get_available_years(cls, db_client) -> List[int]:
        """Get list of years that have area leader data."""
        try:
            collections = db_client.collections()
            years = []

            for collection in collections:
                if collection.id.startswith('area_leaders_'):
                    try:
                        year = int(collection.id.split('_')[2])
                        years.append(year)
                    except (ValueError, IndexError):
                        continue

            return sorted(years, reverse=True)

        except Exception as e:
            logging.error(f"Failed to get available years for area leaders: {e}")
            return [datetime.now().year]

    def get_leaders_by_identity(self, first_name: str, last_name: str, email: str) -> List[Dict]:
        """Get all active leaders matching exact identity (first_name, last_name, email)."""
        leaders = []
        query = (self.db.collection(self.collection)
                 .where('first_name', '==', first_name.strip())
                 .where('last_name', '==', last_name.strip())
                 .where('leader_email', '==', email.lower().strip())
                 .where('active', '==', True))

        for doc in query.stream():
            data = doc.to_dict()
            data['id'] = doc.id
            leaders.append(data)

        return leaders

    def get_areas_by_identity(self, first_name: str, last_name: str, email: str) -> List[Dict]:
        """Get all areas led by a specific identity (first_name, last_name, email)."""
        return self.get_leaders_by_identity(first_name, last_name, email)

    def deactivate_leaders_by_identity(self, first_name: str, last_name: str, email: str, removed_by: str) -> bool:
        """Deactivate all active leaders matching exact identity (first_name, last_name, email)."""
        try:
            # Find all matching active leaders
            matching_leaders = self.get_leaders_by_identity(first_name, last_name, email)

            if not matching_leaders:
                self.logger.info(f"No active leaders found for identity: {first_name} {last_name} <{email}>")
                return True  # No leaders to deactivate is success

            # Deactivate each matching leader
            deactivated_count = 0
            for leader in matching_leaders:
                if self.remove_leader(leader['id'], removed_by):
                    deactivated_count += 1
                    self.logger.info(f"Deactivated leader {leader['id']} for {first_name} {last_name} in area {leader.get('area_code')}")
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