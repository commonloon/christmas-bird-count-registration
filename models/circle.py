from datetime import datetime, timezone

from models.db import Circle, CircleArea, CircleAdmin
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

    def update(self, slug, circle_data):
        """Update an existing circle's config fields. Returns the updated dict,
        or None if no such circle exists. slug itself is immutable - not settable
        via circle_data (it's the primary key and the Host-header routing key)."""
        row = self.db.query(Circle).filter_by(slug=slug).first()
        if not row:
            return None
        for key, value in circle_data.items():
            if key in ('slug', 'created_at'):
                continue
            setattr(row, key, value)
        row.updated_at = datetime.now(timezone.utc)
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

    def update_area(self, circle_slug, code, name=None, description=None, difficulty=None, terrain=None):
        """Update an existing area's label fields. Returns the updated dict, or
        None if no such area exists for this circle."""
        row = self.db.query(CircleArea).filter_by(circle_slug=circle_slug, code=code.upper()).first()
        if not row:
            return None
        if name is not None:
            row.name = name
        if description is not None:
            row.description = description
        if difficulty is not None:
            row.difficulty = difficulty
        if terrain is not None:
            row.terrain = terrain
        self.db.commit()
        return row.to_dict()


class CircleAdminModel:
    """Manage which emails are circle-scoped admins for a circle."""

    def __init__(self, db_session):
        self.db = db_session

    def is_circle_admin(self, email, circle_slug):
        """Check whether an email is a circle-admin for this specific circle."""
        if not email or not circle_slug:
            return False
        email = email.lower().strip()
        return self.db.query(CircleAdmin).filter_by(email=email, circle_slug=circle_slug).first() is not None

    def get_admins_for_circle(self, circle_slug):
        """Get all circle-admin rows for a circle, ordered by email."""
        rows = self.db.query(CircleAdmin).filter_by(circle_slug=circle_slug).order_by(CircleAdmin.email).all()
        return [row.to_dict() for row in rows]

    def get_circles_for_email(self, email):
        """Get every circle_slug this email is a circle-admin for (reverse of
        get_admins_for_circle) - used to send a per-circle login link to a
        multi-circle admin who requests a magic link from the landing host,
        where there's no single circle to check against."""
        if not email:
            return []
        email = email.lower().strip()
        rows = self.db.query(CircleAdmin).filter_by(email=email).order_by(CircleAdmin.circle_slug).all()
        return [row.circle_slug for row in rows]

    def add_admin(self, email, circle_slug):
        """Grant an email circle-admin access to a circle. Returns the row dict."""
        email = email.lower().strip()
        existing = self.db.query(CircleAdmin).filter_by(email=email, circle_slug=circle_slug).first()
        if existing:
            return existing.to_dict()
        row = CircleAdmin(email=email, circle_slug=circle_slug, created_at=datetime.now(timezone.utc))
        self.db.add(row)
        self.db.commit()
        return row.to_dict()

    def remove_admin(self, email, circle_slug):
        """Revoke an email's circle-admin access to a circle."""
        email = email.lower().strip()
        self.db.query(CircleAdmin).filter_by(email=email, circle_slug=circle_slug).delete()
        self.db.commit()
