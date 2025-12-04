# Updated by Claude AI on 2025-10-03
"""
Field definitions for participants with ordered display and default values.
This centralizes field management to prevent data loss during schema evolution.
"""

from collections import OrderedDict
from datetime import datetime

# Participant field definitions with display order and defaults
PARTICIPANT_FIELDS = OrderedDict([
    # Core identification
    ('first_name', {'default': '', 'display_name': 'First Name', 'csv_order': 1}),
    ('last_name', {'default': '', 'display_name': 'Last Name', 'csv_order': 2}),
    ('email', {'default': '', 'display_name': 'Email', 'csv_order': 3}),

    # Contact information
    ('phone', {'default': '', 'display_name': 'Cell Phone', 'csv_order': 4}),
    ('phone2', {'default': '', 'display_name': 'Secondary Phone', 'csv_order': 5}),

    # CBC details
    ('skill_level', {'default': '', 'display_name': 'Skill Level', 'csv_order': 6}),
    ('experience', {'default': '', 'display_name': 'CBC Experience', 'csv_order': 7}),
    ('preferred_area', {'default': 'UNASSIGNED', 'display_name': 'Preferred Area', 'csv_order': 8}),
    ('participation_type', {'default': 'regular', 'display_name': 'Participation Type', 'csv_order': 9}),

    # Equipment and interests
    ('has_binoculars', {'default': False, 'display_name': 'Has Binoculars', 'csv_order': 10}),
    ('spotting_scope', {'default': False, 'display_name': 'Can Bring Spotting Scope', 'csv_order': 11}),
    ('interested_in_leadership', {'default': False, 'display_name': 'Leadership Interest', 'csv_order': 12}),
    ('interested_in_scribe', {'default': False, 'display_name': 'Scribe Interest', 'csv_order': 13}),

    # Notes
    ('notes_to_organizers', {'default': '', 'display_name': 'Notes to Organizers', 'csv_order': 14}),

    # System fields (usually set by application)
    ('is_leader', {'default': False, 'display_name': 'Is Leader', 'csv_order': 15}),
    ('assigned_area_leader', {'default': None, 'display_name': 'Assigned Area Leader', 'csv_order': 16}),
    ('auto_assigned', {'default': False, 'display_name': 'Auto Assigned', 'csv_order': 17}),
    ('assigned_by', {'default': None, 'display_name': 'Assigned By', 'csv_order': 18}),
    ('assigned_at', {'default': None, 'display_name': 'Assigned At', 'csv_order': 19}),

    # Leadership tracking fields
    ('leadership_assigned_by', {'default': None, 'display_name': 'Leadership Assigned By', 'csv_order': 20}),
    ('leadership_assigned_at', {'default': None, 'display_name': 'Leadership Assigned At', 'csv_order': 21}),
    ('leadership_removed_by', {'default': None, 'display_name': 'Leadership Removed By', 'csv_order': 22}),
    ('leadership_removed_at', {'default': None, 'display_name': 'Leadership Removed At', 'csv_order': 23}),

    # Metadata
    ('created_at', {'default': None, 'display_name': 'Registration Date', 'csv_order': 24}),
    ('updated_at', {'default': None, 'display_name': 'Last Updated', 'csv_order': 25}),
    ('year', {'default': datetime.now().year, 'display_name': 'Year', 'csv_order': 26}),
    ('id', {'default': None, 'display_name': 'ID', 'csv_order': 27}),

    # Withdrawal feature
    ('status', {'default': 'active', 'display_name': 'Status', 'csv_order': 28}),
])


def get_participant_fields():
    """Get ordered list of participant field names."""
    return list(PARTICIPANT_FIELDS.keys())


def get_participant_csv_fields():
    """Get participant fields in CSV export order."""
    fields_with_order = [(field, config['csv_order']) for field, config in PARTICIPANT_FIELDS.items()]
    return [field for field, _ in sorted(fields_with_order, key=lambda x: x[1])]


def get_participant_field_default(field_name):
    """Get default value for a participant field."""
    return PARTICIPANT_FIELDS.get(field_name, {}).get('default', '')


def get_participant_display_name(field_name):
    """Get display name for a participant field."""
    return PARTICIPANT_FIELDS.get(field_name, {}).get('display_name', field_name.replace('_', ' ').title())


def normalize_participant_record(record):
    """
    Normalize a participant record to include all expected fields with defaults.

    Args:
        record: Participant record dictionary

    Returns:
        Normalized record with all fields present
    """
    normalized = {}
    for field_name in get_participant_fields():
        normalized[field_name] = record.get(field_name, get_participant_field_default(field_name))
    return normalized