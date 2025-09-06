from google.cloud import firestore
from datetime import datetime
from typing import List, Dict


class RemovalLogModel:
    """Handle Firestore operations for participant removal tracking."""

    def __init__(self, db_client):
        self.db = db_client
        self.collection = 'removal_log'

    def log_removal(self, participant_name: str, area_code: str, removed_by: str, reason: str = '') -> str:
        """Log a participant removal."""
        removal_data = {
            'participant_name': participant_name,
            'area_code': area_code,
            'removed_by': removed_by,
            'reason': reason,
            'removed_at': datetime.now(),
            'year': datetime.now().year,
            'emailed': False
        }

        doc_ref = self.db.collection(self.collection).add(removal_data)
        return doc_ref[1].id