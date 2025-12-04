# Updated by Claude AI on 2025-12-02
from google.cloud import firestore
from datetime import datetime
from typing import List, Dict
import logging


class WithdrawalLogModel:
    """Handle Firestore operations for withdrawal logs with year-aware collections."""

    def __init__(self, db_client, year: int = None):
        self.db = db_client
        self.year = year or datetime.now().year
        self.collection = f'withdrawal_log_{self.year}'
        self.logger = logging.getLogger(__name__)

    def log_withdrawal(self, participant_id: str, first_name: str, last_name: str,
                      email: str, area_code: str, withdrawal_reason: str,
                      recorded_by: str) -> bool:
        """Log a participant withdrawal."""
        try:
            entry = {
                'participant_id': participant_id,
                'first_name': first_name,
                'last_name': last_name,
                'email': email.lower(),
                'area_code': area_code,
                'status': 'withdrawn',
                'withdrawal_reason': withdrawal_reason,
                'recorded_by': recorded_by,
                'recorded_at': datetime.now()
            }

            self.db.collection(self.collection).add(entry)
            self.logger.info(f"Logged withdrawal for {first_name} {last_name} <{email}> from area {area_code}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to log withdrawal: {e}")
            return False

    def log_reactivation(self, participant_id: str, first_name: str, last_name: str,
                        email: str, area_code: str, recorded_by: str) -> bool:
        """Log a participant reactivation."""
        try:
            entry = {
                'participant_id': participant_id,
                'first_name': first_name,
                'last_name': last_name,
                'email': email.lower(),
                'area_code': area_code,
                'status': 'reactivated',
                'withdrawal_reason': None,
                'recorded_by': recorded_by,
                'recorded_at': datetime.now()
            }

            self.db.collection(self.collection).add(entry)
            self.logger.info(f"Logged reactivation for {first_name} {last_name} <{email}> in area {area_code}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to log reactivation: {e}")
            return False

    def get_withdrawals_since(self, area_code: str, since_timestamp: datetime) -> List[Dict]:
        """Get all withdrawals for an area since a specific timestamp."""
        from google.cloud.firestore_v1.base_query import FieldFilter
        withdrawals = []

        try:
            query = (self.db.collection(self.collection)
                    .where(filter=FieldFilter('area_code', '==', area_code))
                    .where(filter=FieldFilter('status', '==', 'withdrawn'))
                    .where(filter=FieldFilter('recorded_at', '>=', since_timestamp)))

            for doc in query.stream():
                data = doc.to_dict()
                data['id'] = doc.id
                withdrawals.append(data)

            return withdrawals
        except Exception as e:
            self.logger.error(f"Failed to get withdrawals since timestamp: {e}")
            return []

    def get_all_withdrawals_since(self, since_timestamp: datetime) -> List[Dict]:
        """Get all withdrawals since a specific timestamp."""
        from google.cloud.firestore_v1.base_query import FieldFilter
        withdrawals = []

        try:
            query = (self.db.collection(self.collection)
                    .where(filter=FieldFilter('status', '==', 'withdrawn'))
                    .where(filter=FieldFilter('recorded_at', '>=', since_timestamp)))

            for doc in query.stream():
                data = doc.to_dict()
                data['id'] = doc.id
                withdrawals.append(data)

            return withdrawals
        except Exception as e:
            self.logger.error(f"Failed to get all withdrawals since timestamp: {e}")
            return []
