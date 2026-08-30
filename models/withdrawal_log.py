from datetime import datetime, timezone
from typing import List, Dict
import logging

from models.db import WithdrawalLog, resolve_default_circle_slug


class WithdrawalLogModel:
    """Handle PostgreSQL operations for withdrawal logs, scoped by year/circle."""

    def __init__(self, db_session, year: int = None, circle_slug: str = None):
        self.db = db_session
        self.year = year or datetime.now().year
        self.circle_slug = circle_slug or resolve_default_circle_slug()
        self.logger = logging.getLogger(__name__)

    def _base_query(self):
        return self.db.query(WithdrawalLog).filter_by(year=self.year, circle_slug=self.circle_slug)

    def log_withdrawal(self, participant_id, first_name: str, last_name: str,
                      email: str, area_code: str, withdrawal_reason: str,
                      recorded_by: str) -> bool:
        """Log a participant withdrawal."""
        try:
            entry = WithdrawalLog(
                year=self.year,
                circle_slug=self.circle_slug,
                participant_id=int(participant_id) if participant_id is not None else None,
                first_name=first_name,
                last_name=last_name,
                email=email.lower(),
                area_code=area_code,
                status='withdrawn',
                withdrawal_reason=withdrawal_reason,
                recorded_by=recorded_by,
                recorded_at=datetime.now(timezone.utc),
            )
            self.db.add(entry)
            self.db.commit()
            self.logger.info(f"Logged withdrawal for {first_name} {last_name} <{email}> from area {area_code}")
            return True
        except Exception as e:
            self.db.rollback()
            self.logger.error(f"Failed to log withdrawal: {e}")
            return False

    def log_reactivation(self, participant_id, first_name: str, last_name: str,
                        email: str, area_code: str, recorded_by: str) -> bool:
        """Log a participant reactivation."""
        try:
            entry = WithdrawalLog(
                year=self.year,
                circle_slug=self.circle_slug,
                participant_id=int(participant_id) if participant_id is not None else None,
                first_name=first_name,
                last_name=last_name,
                email=email.lower(),
                area_code=area_code,
                status='reactivated',
                withdrawal_reason=None,
                recorded_by=recorded_by,
                recorded_at=datetime.now(timezone.utc),
            )
            self.db.add(entry)
            self.db.commit()
            self.logger.info(f"Logged reactivation for {first_name} {last_name} <{email}> in area {area_code}")
            return True
        except Exception as e:
            self.db.rollback()
            self.logger.error(f"Failed to log reactivation: {e}")
            return False

    def get_withdrawals_since(self, area_code: str, since_timestamp: datetime) -> List[Dict]:
        """Get all withdrawals for an area since a specific timestamp."""
        try:
            if since_timestamp.tzinfo is None:
                since_timestamp = since_timestamp.replace(tzinfo=timezone.utc)
            rows = self._base_query().filter(
                WithdrawalLog.area_code == area_code,
                WithdrawalLog.status == 'withdrawn',
                WithdrawalLog.recorded_at >= since_timestamp,
            ).all()
            return [r.to_dict() for r in rows]
        except Exception as e:
            self.logger.error(f"Failed to get withdrawals since timestamp: {e}")
            return []

    def get_events_for_area_since(self, area_code: str, since_timestamp: datetime) -> List[Dict]:
        """Get withdrawal AND reactivation events for an area since a timestamp
        (used for net-change calculation in scheduled team-update emails)."""
        try:
            if since_timestamp.tzinfo is None:
                since_timestamp = since_timestamp.replace(tzinfo=timezone.utc)
            rows = self._base_query().filter(
                WithdrawalLog.area_code == area_code,
                WithdrawalLog.status.in_(['withdrawn', 'reactivated']),
                WithdrawalLog.recorded_at >= since_timestamp,
            ).all()
            return [r.to_dict() for r in rows]
        except Exception as e:
            self.logger.error(f"Failed to get withdrawal/reactivation events for area {area_code}: {e}")
            return []

    def get_all_withdrawals_since(self, since_timestamp: datetime) -> List[Dict]:
        """Get all withdrawals since a specific timestamp."""
        try:
            if since_timestamp.tzinfo is None:
                since_timestamp = since_timestamp.replace(tzinfo=timezone.utc)
            rows = self._base_query().filter(
                WithdrawalLog.status == 'withdrawn',
                WithdrawalLog.recorded_at >= since_timestamp,
            ).all()
            return [r.to_dict() for r in rows]
        except Exception as e:
            self.logger.error(f"Failed to get all withdrawals since timestamp: {e}")
            return []
