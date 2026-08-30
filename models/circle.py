from datetime import datetime, timezone

from models.db import Circle, CircleArea
from models.area_signup_type import natural_sort_key


class CircleModel:
    """Look up count circle configuration (replaces config/organization.py's old
    single-organization module constants for multi-circle support)."""

    def __init__(self, db_session):
        self.db = db_session

    def get_by_slug(self, slug):
        """Get a circle's config by slug, or None if it doesn't exist."""
        row = self.db.query(Circle).filter_by(slug=slug).first()
        if not row:
            return None
        data = row.to_dict()
        # JSON object keys are always strings in Postgres; convert back to int years
        # to match config/organization.py's YEARLY_COUNT_DATES int-keyed dict shape.
        if data.get('yearly_count_dates'):
            data['yearly_count_dates'] = {
                int(year): date_str for year, date_str in data['yearly_count_dates'].items()
            }
        return data

    def get_all(self):
        """Get all circles, ordered by slug."""
        rows = self.db.query(Circle).order_by(Circle.slug).all()
        results = []
        for row in rows:
            data = row.to_dict()
            if data.get('yearly_count_dates'):
                data['yearly_count_dates'] = {
                    int(year): date_str for year, date_str in data['yearly_count_dates'].items()
                }
            results.append(data)
        return results

    def create(self, circle_data):
        """Create a new circle. circle_data should match the Circle column names."""
        now = datetime.now(timezone.utc)
        row = Circle(
            created_at=now,
            updated_at=now,
            **circle_data,
        )
        self.db.add(row)
        self.db.commit()
        return row.to_dict()


class CircleAreaModel:
    """Manage per-circle area definitions (replaces config/areas.py's static AREA_CONFIG,
    which only ever described Vancouver's areas)."""

    def __init__(self, db_session):
        self.db = db_session

    def get_areas_for_circle(self, circle_slug):
        """Get all area definitions for a circle, naturally sorted by code."""
        rows = self.db.query(CircleArea).filter_by(circle_slug=circle_slug).all()
        return sorted((row.to_dict() for row in rows), key=lambda a: natural_sort_key(a['code']))

    def get_area(self, circle_slug, code):
        """Get a single area's definition, or None if it doesn't exist for this circle."""
        row = self.db.query(CircleArea).filter_by(circle_slug=circle_slug, code=code.upper()).first()
        return row.to_dict() if row else None

    def add_area(self, circle_slug, code, name, description=None, difficulty=None, terrain=None):
        """Add one area definition for a circle."""
        row = CircleArea(
            circle_slug=circle_slug,
            code=code.upper(),
            name=name,
            description=description,
            difficulty=difficulty,
            terrain=terrain,
        )
        self.db.add(row)
        self.db.commit()
        return row.to_dict()
