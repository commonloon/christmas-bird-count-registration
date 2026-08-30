from datetime import datetime, timezone
from typing import List, Dict
import logging

from models.db import ReassignmentLog, DEFAULT_CIRCLE_SLUG


class ReassignmentLogModel:
    """Handle PostgreSQL operations for participant reassignment logging (year/circle-scoped)."""

    def __init__(self, db_session, year: int = None, circle_slug: str = None):
        self.db = db_session
        self.year = year or datetime.now().year
        self.circle_slug = circle_slug or DEFAULT_CIRCLE_SLUG
        self.logger = logging.getLogger(__name__)

    def _base_query(self):
        return self.db.query(ReassignmentLog).filter_by(year=self.year, circle_slug=self.circle_slug)

    def log_reassignment(self, participant_id, first_name: str, last_name: str,
                        email: str, old_area: str, new_area: str, changed_by: str) -> str:
        """Log a participant reassignment from one area to another."""
        reassignment = ReassignmentLog(
            year=self.year,
            circle_slug=self.circle_slug,
            participant_id=int(participant_id) if participant_id is not None else None,
            first_name=first_name,
            last_name=last_name,
            email=email,
            old_area=old_area,
            new_area=new_area,
            changed_by=changed_by,
            changed_at=datetime.now(timezone.utc),
        )
        self.db.add(reassignment)
        self.db.commit()
        self.logger.info(f"Logged reassignment for {first_name} {last_name} from area {old_area} to {new_area}")
        return str(reassignment.id)

    def get_reassignments_since(self, since_timestamp: datetime) -> List[Dict]:
        """Get all reassignments since a given timestamp."""
        try:
            if since_timestamp.tzinfo is None:
                since_timestamp = since_timestamp.replace(tzinfo=timezone.utc)
            rows = self._base_query().filter(ReassignmentLog.changed_at >= since_timestamp).all()
            return [r.to_dict() for r in rows]
        except Exception as e:
            self.logger.error(f"Error getting reassignments since {since_timestamp}: {e}")
            return []

    def get_reassignments_for_area_since(self, area_code: str, since_timestamp: datetime) -> tuple:
        """Get reassignments affecting a specific area since timestamp.

        Returns (arrivals, departures).
        """
        all_reassignments = self.get_reassignments_since(since_timestamp)
        arrivals = [r for r in all_reassignments if r.get('new_area') == area_code]
        departures = [r for r in all_reassignments if r.get('old_area') == area_code]
        return arrivals, departures

    def get_all_reassignments(self) -> List[Dict]:
        """Get all reassignments for the year (for auditing/reporting)."""
        try:
            rows = self._base_query().order_by(ReassignmentLog.changed_at.desc()).all()
            return [r.to_dict() for r in rows]
        except Exception as e:
            self.logger.error(f"Error getting all reassignments for year {self.year}: {e}")
            return []
