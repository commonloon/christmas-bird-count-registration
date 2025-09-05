from google.cloud import firestore
from datetime import datetime
from typing import List, Dict, Optional


class ParticipantModel:
    """Handle Firestore operations for participants."""

    def __init__(self, db_client):
        self.db = db_client
        self.collection = 'participants'

    def add_participant(self, participant_data: Dict) -> str:
        """Add a new participant to Firestore."""
        participant_data['created_at'] = datetime.now()
        participant_data['year'] = datetime.now().year

        doc_ref = self.db.collection(self.collection).add(participant_data)
        return doc_ref[1].id  # Return document ID

    def get_participant(self, participant_id: str) -> Optional[Dict]:
        """Get a participant by ID."""
        doc = self.db.collection(self.collection).document(participant_id).get()
        if doc.exists:
            data = doc.to_dict()
            data['id'] = doc.id
            return data
        return None

    def get_participants_by_area(self, area_code: str, year: int = None) -> List[Dict]:
        """Get all participants for a specific area."""
        if year is None:
            year = datetime.now().year

        participants = []
        query = self.db.collection(self.collection).where('preferred_area', '==', area_code).where('year', '==', year)

        for doc in query.stream():
            data = doc.to_dict()
            data['id'] = doc.id
            participants.append(data)

        return participants

    def get_area_counts(self, year: int = None) -> Dict[str, int]:
        """Get participant count by area."""
        if year is None:
            year = datetime.now().year

        counts = {}
        query = self.db.collection(self.collection).where('year', '==', year)

        for doc in query.stream():
            data = doc.to_dict()
            area = data.get('preferred_area', 'UNKNOWN')
            counts[area] = counts.get(area, 0) + 1

        return counts

    def update_participant(self, participant_id: str, updates: Dict) -> bool:
        """Update a participant's information."""
        try:
            updates['updated_at'] = datetime.now()
            self.db.collection(self.collection).document(participant_id).update(updates)
            return True
        except Exception:
            return False

    def delete_participant(self, participant_id: str) -> bool:
        """Delete a participant."""
        try:
            self.db.collection(self.collection).document(participant_id).delete()
            return True
        except Exception:
            return False

    def get_all_participants(self, year: int = None) -> List[Dict]:
        """Get all participants for a given year."""
        if year is None:
            year = datetime.now().year

        participants = []
        query = self.db.collection(self.collection).where('year', '==', year)

        for doc in query.stream():
            data = doc.to_dict()
            data['id'] = doc.id
            participants.append(data)

        return participants

    def email_exists(self, email: str, year: int = None) -> bool:
        """Check if an email is already registered for the current year."""
        if year is None:
            year = datetime.now().year

        query = self.db.collection(self.collection).where('email', '==', email).where('year', '==', year)
        docs = list(query.stream())
        return len(docs) > 0