from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional
import logging

from models.db import RemovalLog, resolve_default_circle_slug


class RemovalLogModel:
    """Handle PostgreSQL operations for participant removal tracking, scoped by year/circle."""

    def __init__(self, db_session, year: int = None, circle_slug: str = None):
        self.db = db_session
        self.year = year or datetime.now().year
        self.circle_slug = circle_slug or resolve_default_circle_slug()
        self.logger = logging.getLogger(__name__)

    def _base_query(self):
        return self.db.query(RemovalLog).filter_by(year=self.year, circle_slug=self.circle_slug)

    def log_removal(self, participant_name: str, area_code: str, removed_by: str,
                    reason: str = '', participant_email: str = '') -> str:
        """Log a participant removal."""
        removal = RemovalLog(
            year=self.year,
            circle_slug=self.circle_slug,
            participant_name=participant_name,
            participant_email=participant_email,
            area_code=area_code,
            removed_by=removed_by,
            reason=reason,
            removed_at=datetime.now(timezone.utc),
            emailed=False,
        )
        self.db.add(removal)
        self.db.commit()
        self.logger.info(f"Logged removal: {participant_name} from area {area_code}")
        return str(removal.id)

    def get_removal(self, removal_id) -> Optional[Dict]:
        """Get a removal log entry by ID."""
        row = self._base_query().filter_by(id=int(removal_id)).first()
        return row.to_dict() if row else None

    def get_pending_removals(self) -> List[Dict]:
        """Get removals that haven't been emailed yet for the current year."""
        rows = self._base_query().filter_by(emailed=False).all()
        return [r.to_dict() for r in rows]

    def get_pending_removals_by_area(self, area_code: str) -> List[Dict]:
        """Get pending removals for a specific area."""
        rows = self._base_query().filter_by(emailed=False, area_code=area_code).all()
        return [r.to_dict() for r in rows]

    def get_all_removals(self, limit: int = None) -> List[Dict]:
        """Get all removal log entries for the current year."""
        query = self._base_query().order_by(RemovalLog.removed_at.desc())
        if limit:
            query = query.limit(limit)
        return [r.to_dict() for r in query.all()]

    def get_removals_by_area(self, area_code: str) -> List[Dict]:
        """Get all removals for a specific area in the current year."""
        rows = self._base_query().filter_by(area_code=area_code).order_by(RemovalLog.removed_at.desc()).all()
        return [r.to_dict() for r in rows]

    def mark_removals_emailed(self, removal_ids: List) -> bool:
        """Mark removals as having been emailed."""
        try:
            timestamp = datetime.now(timezone.utc)
            ids = [int(rid) for rid in removal_ids]
            self._base_query().filter(RemovalLog.id.in_(ids)).update(
                {RemovalLog.emailed: True, RemovalLog.emailed_at: timestamp},
                synchronize_session=False,
            )
            self.db.commit()
            self.logger.info(f"Marked {len(removal_ids)} removals as emailed")
            return True
        except Exception as e:
            self.db.rollback()
            self.logger.error(f"Failed to mark removals as emailed: {e}")
            return False

    def mark_removal_emailed(self, removal_id) -> bool:
        """Mark a single removal as having been emailed."""
        try:
            removal = self._base_query().filter_by(id=int(removal_id)).first()
            if not removal:
                return False
            removal.emailed = True
            removal.emailed_at = datetime.now(timezone.utc)
            self.db.commit()
            return True
        except Exception as e:
            self.db.rollback()
            self.logger.error(f"Failed to mark removal {removal_id} as emailed: {e}")
            return False

    def get_removal_stats(self) -> Dict:
        """Get removal statistics for the current year."""
        all_removals = self.get_all_removals()
        pending_removals = self.get_pending_removals()

        by_area = {}
        for removal in all_removals:
            area = removal.get('area_code') or 'UNKNOWN'
            by_area[area] = by_area.get(area, 0) + 1

        by_reason = {}
        for removal in all_removals:
            reason = removal.get('reason') or 'No reason provided'
            by_reason[reason] = by_reason.get(reason, 0) + 1

        return {
            'total_removals': len(all_removals),
            'pending_email': len(pending_removals),
            'by_area': by_area,
            'by_reason': by_reason,
            'year': self.year,
        }

    def delete_removal_log(self, removal_id) -> bool:
        """Delete a removal log entry (admin only, rare use case)."""
        try:
            removal = self._base_query().filter_by(id=int(removal_id)).first()
            if not removal:
                return False
            self.db.delete(removal)
            self.db.commit()
            self.logger.info(f"Deleted removal log entry {removal_id}")
            return True
        except Exception as e:
            self.db.rollback()
            self.logger.error(f"Failed to delete removal log {removal_id}: {e}")
            return False

    def get_recent_removals(self, days_back: int = 7) -> List[Dict]:
        """Get removals from the last N days."""
        cutoff_date = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        cutoff_date = cutoff_date - timedelta(days=days_back)
        rows = self._base_query().filter(RemovalLog.removed_at >= cutoff_date).order_by(
            RemovalLog.removed_at.desc()
        ).all()
        return [r.to_dict() for r in rows]

    def get_removals_since(self, area_code: str, since_timestamp: datetime) -> List[Dict]:
        """Get removals for a specific area since the given timestamp."""
        if since_timestamp.tzinfo is None:
            since_timestamp = since_timestamp.replace(tzinfo=timezone.utc)
        rows = self._base_query().filter(
            RemovalLog.area_code == area_code, RemovalLog.removed_at >= since_timestamp
        ).order_by(RemovalLog.removed_at.desc()).all()
        return [r.to_dict() for r in rows]

    def get_removals_needing_notification(self) -> Dict[str, List[Dict]]:
        """Get pending removals grouped by area for email notifications."""
        pending = self.get_pending_removals()
        by_area = {}
        for removal in pending:
            area_code = removal.get('area_code') or 'UNKNOWN'
            by_area.setdefault(area_code, []).append(removal)
        return by_area

    @classmethod
    def get_available_years(cls, db_session) -> List[int]:
        """Get list of years that have removal log data."""
        try:
            years = [row[0] for row in db_session.query(RemovalLog.year).distinct().all()]
            return sorted(years, reverse=True) or [datetime.now().year]
        except Exception as e:
            logging.getLogger(__name__).error(f"Failed to get available years for removal logs: {e}")
            return [datetime.now().year]
