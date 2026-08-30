from datetime import datetime, timezone
import re

from config.areas import get_all_areas
from models.db import AreaSignupType, DEFAULT_CIRCLE_SLUG


def natural_sort_key(area_code):
    """Create a sort key for natural/numeric sorting of area codes.

    Handles codes like: A, B, C (alphabetic) and 1, 2, 10, 4A, 9B (numeric/alphanumeric).
    Sorts alphabetically for letter codes: A, B, C, ... X
    Sorts numerically for numeric codes: 1, 2, 4A, 4B, 9A, 9B, 10, 11, etc.
    """
    parts = re.findall(r'(\d+|[A-Za-z]+)', str(area_code))
    return tuple(int(p) if p.isdigit() else p for p in parts)


class AreaSignupTypeModel:
    """Manage area signup type settings (open vs admin-only) in PostgreSQL."""

    def __init__(self, db_session, circle_slug: str = None):
        self.db = db_session
        self.circle_slug = circle_slug or DEFAULT_CIRCLE_SLUG

    def _base_query(self):
        return self.db.query(AreaSignupType).filter_by(circle_slug=self.circle_slug)

    def get_area_signup_type(self, area_code):
        """Get signup type for a specific area (admin_assignment_only flag)."""
        area_code = area_code.upper()
        row = self._base_query().filter_by(area_code=area_code).first()
        if row:
            return row.to_dict()
        return {'admin_assignment_only': False, 'area_code': area_code}

    def get_all_signup_types(self):
        """Get signup types for all areas."""
        result = {}
        for row in self._base_query().all():
            result[row.area_code] = row.to_dict()

        for area_code in get_all_areas():
            if area_code not in result:
                result[area_code] = {'admin_assignment_only': False, 'area_code': area_code}

        return result

    def set_admin_assignment_only(self, area_code, admin_assignment_only, updated_by=None):
        """Set the admin assignment only flag for an area."""
        area_code = area_code.upper()
        try:
            row = self._base_query().filter_by(area_code=area_code).first()
            now = datetime.now(timezone.utc)
            if row:
                row.admin_assignment_only = admin_assignment_only
                row.updated_at = now
                row.updated_by = updated_by
            else:
                row = AreaSignupType(
                    circle_slug=self.circle_slug,
                    area_code=area_code,
                    admin_assignment_only=admin_assignment_only,
                    created_at=now,
                    updated_at=now,
                    updated_by=updated_by,
                )
                self.db.add(row)
            self.db.commit()
            return True
        except Exception as e:
            self.db.rollback()
            print(f"Error updating area signup type: {e}")
            return False

    def is_admin_assignment_only(self, area_code):
        """Check if an area is admin-assignment-only."""
        return self.get_area_signup_type(area_code).get('admin_assignment_only', False)

    def get_public_areas(self):
        """Get list of area codes available for public registration (excludes admin-only areas)."""
        signup_types = self.get_all_signup_types()
        public_codes = [code for code, settings in signup_types.items()
                        if not settings.get('admin_assignment_only', False)]
        return sorted(public_codes, key=natural_sort_key)

    def initialize_all_areas(self):
        """Initialize all areas to open registration if they don't exist yet."""
        now = datetime.now(timezone.utc)
        existing = {row.area_code for row in self._base_query().all()}

        for area_code in get_all_areas():
            if area_code not in existing:
                self.db.add(AreaSignupType(
                    circle_slug=self.circle_slug,
                    area_code=area_code,
                    admin_assignment_only=False,
                    created_at=now,
                    updated_at=now,
                ))
        self.db.commit()
