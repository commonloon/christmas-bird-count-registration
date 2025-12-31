# Updated by Claude AI on 2025-12-31
from datetime import datetime
import re
from config.areas import get_all_areas


def natural_sort_key(area_code):
    """Create a sort key for natural/numeric sorting of area codes.

    Handles codes like: A, B, C (alphabetic) and 1, 2, 10, 4A, 9B (numeric/alphanumeric).
    Sorts alphabetically for letter codes: A, B, C, ... X
    Sorts numerically for numeric codes: 1, 2, 4A, 4B, 9A, 9B, 10, 11, etc.

    Args:
        area_code: Area code string (e.g., 'A', 'B', '1', '4A', '10')

    Returns:
        Tuple for natural sorting
    """
    # Extract numeric and alphabetic parts
    parts = re.findall(r'(\d+|[A-Za-z]+)', str(area_code))
    # Convert numeric parts to integers for proper numeric sorting
    return tuple(int(p) if p.isdigit() else p for p in parts)


class AreaSignupTypeModel:
    """Manage area signup type settings (open vs admin-only) in Firestore."""

    COLLECTION_NAME = 'area_signup_type'

    def __init__(self, db):
        """Initialize with Firestore client."""
        self.db = db
        self.collection = db.collection(self.COLLECTION_NAME)

    def get_area_signup_type(self, area_code):
        """Get signup type for a specific area (admin_assignment_only flag).

        Args:
            area_code: The area code (e.g., 'A', 'B')

        Returns:
            dict with 'admin_assignment_only' boolean, defaults to False if not found
        """
        doc = self.collection.document(area_code.upper()).get()
        if doc.exists:
            return doc.to_dict()
        # Default to open registration
        return {'admin_assignment_only': False, 'area_code': area_code.upper()}

    def get_all_signup_types(self):
        """Get signup types for all areas.

        Returns:
            dict mapping area codes to {admin_assignment_only: bool}
        """
        result = {}
        docs = self.collection.stream()

        for doc in docs:
            area_code = doc.id
            result[area_code] = doc.to_dict()

        # Fill in missing areas with defaults
        for area_code in get_all_areas():
            if area_code not in result:
                result[area_code] = {'admin_assignment_only': False, 'area_code': area_code}

        return result

    def set_admin_assignment_only(self, area_code, admin_assignment_only, updated_by=None):
        """Set the admin assignment only flag for an area.

        Args:
            area_code: The area code
            admin_assignment_only: Boolean flag
            updated_by: Email of admin making the change

        Returns:
            True if successful
        """
        area_code = area_code.upper()

        # Prepare update data
        data = {
            'area_code': area_code,
            'admin_assignment_only': admin_assignment_only,
            'updated_at': datetime.now(),
            'updated_by': updated_by
        }

        try:
            self.collection.document(area_code).set(data, merge=True)
            return True
        except Exception as e:
            print(f"Error updating area signup type: {e}")
            return False

    def is_admin_assignment_only(self, area_code):
        """Check if an area is admin-assignment-only.

        Args:
            area_code: The area code

        Returns:
            Boolean
        """
        signup_type = self.get_area_signup_type(area_code)
        return signup_type.get('admin_assignment_only', False)

    def get_public_areas(self):
        """Get list of area codes available for public registration (excludes admin-only areas).

        Returns:
            Naturally sorted list of public area codes (A, B, C or 1, 2, 4A, 4B, 9A, 10, etc.)
        """
        signup_types = self.get_all_signup_types()
        public_codes = [code for code, settings in signup_types.items()
                        if not settings.get('admin_assignment_only', False)]
        return sorted(public_codes, key=natural_sort_key)

    def initialize_all_areas(self):
        """Initialize all areas to open registration if they don't exist yet.

        This is called during initial setup to ensure all areas have entries.
        """
        all_areas = get_all_areas()
        batch = self.db.batch()

        for area_code in all_areas:
            doc = self.collection.document(area_code).get()
            if not doc.exists:
                data = {
                    'area_code': area_code,
                    'admin_assignment_only': False,
                    'created_at': datetime.now()
                }
                batch.set(self.collection.document(area_code), data)

        batch.commit()
