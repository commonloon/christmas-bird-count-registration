# utils/import_historical_participants.py
# Updated by Claude AI on 2026-10-27
#
# One-off importer for historical participant/leader data into the Postgres-backed
# multi-circle schema. Leadership fields live directly on the participant row (no
# separate area-leaders table), so this single importer covers both.
#
# Source: --csv-dir DIR imports every *.csv in DIR (see utils/participant-csv-dumps/<slug>/).
# Each row's own `year` column is authoritative, not the filename.
#
# The target circle (and its areas) must already exist in Postgres - create it via
# /bigbird/circles/new and import its area boundaries (KML upload) first. This script
# only writes to the participants table.
#
# Usage:
#   python utils/import_historical_participants.py --circle vancouver --csv-dir utils/participant-csv-dumps/vancouver
#   python utils/import_historical_participants.py --circle ladner --csv-dir utils/participant-csv-dumps/ladner
#   python utils/import_historical_participants.py --circle comox-spring --csv-dir utils/participant-csv-dumps/comox-spring
# Add --dry-run to preview counts/warnings without writing anything.
#
import argparse
import csv
import glob
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from config.database import get_db_session  # noqa: E402
from models.db import Participant  # noqa: E402
from models.circle import CircleModel, CircleAreaModel  # noqa: E402
from services.security import sanitize_name, sanitize_email, sanitize_phone, sanitize_notes  # noqa: E402


def parse_csv_bool(value):
    return (value or '').strip() == 'Yes'


def parse_csv_timestamp(value):
    """CSV timestamps are naive 'YYYY-MM-DD HH:MM[:SS]' strings. Confirmed against a
    the original source data that it is stored in UTC, so naive strings here are
    interpreted as UTC."""
    value = (value or '').strip()
    if not value:
        return None
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M'):
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    raise ValueError(f"Unrecognized timestamp format: {value!r}")


def normalize_csv_row(row):
    return {
        'first_name': sanitize_name(row.get('first_name', '')),
        'last_name': sanitize_name(row.get('last_name', '')),
        'email': sanitize_email(row.get('email', '')),
        'phone': sanitize_phone(row.get('phone', '')),
        'phone2': sanitize_phone(row.get('phone2', '')),
        'skill_level': row.get('skill_level') or None,
        'experience': row.get('experience') or None,
        'preferred_area': row.get('preferred_area') or None,
        'participation_type': row.get('participation_type') or 'regular',
        'has_binoculars': parse_csv_bool(row.get('has_binoculars')),
        'spotting_scope': parse_csv_bool(row.get('spotting_scope')),
        'interested_in_leadership': parse_csv_bool(row.get('interested_in_leadership')),
        'notes_to_organizers': sanitize_notes(row.get('notes_to_organizers', '')),
        'is_leader': parse_csv_bool(row.get('is_leader')),
        'assigned_area_leader': row.get('assigned_area_leader') or None,
        'assigned_by': row.get('assigned_by') or None,
        'assigned_at': parse_csv_timestamp(row.get('assigned_at')),
        'leadership_assigned_by': row.get('leadership_assigned_by') or None,
        'leadership_assigned_at': parse_csv_timestamp(row.get('leadership_assigned_at')),
        'leadership_removed_by': row.get('leadership_removed_by') or None,
        'leadership_removed_at': parse_csv_timestamp(row.get('leadership_removed_at')),
        'created_at': parse_csv_timestamp(row.get('created_at')),
        'updated_at': parse_csv_timestamp(row.get('updated_at')),
        'year': int(row['year']),
        'status': row.get('status') or 'active',
    }


def iter_csv_rows(csv_dir):
    for path in sorted(glob.glob(os.path.join(csv_dir, '*.csv'))):
        with open(path, encoding='utf-8') as f:
            for row in csv.DictReader(f):
                yield path, normalize_csv_row(row)


def import_data(session, circle_slug, source_label, records, dry_run):
    circle = CircleModel(session).get_by_slug(circle_slug)
    if not circle:
        print(f"ERROR: circle '{circle_slug}' does not exist yet - "
              f"create it via /bigbird/circles/new first, then import its areas.")
        return 1

    known_areas = {a['code'] for a in CircleAreaModel(session).get_areas_for_circle(circle_slug)}

    inserted = 0
    renamed = 0
    skipped_invalid = 0
    unknown_areas = set()
    # Tracks identities already staged in this run (not yet committed, so a DB
    # query wouldn't see them). A source export can contain two rows that
    # collide on (first_name, last_name, email, year) - either a literal repeat
    # of the same row, or (confirmed in Ladner's 2023/2024 data) two genuinely
    # different historical records for the same person/year, e.g. a bare-bones
    # stub entry an organizer typed in by hand alongside a fuller record with
    # real skill/leadership data. Rather than guess which one is "right" and
    # drop the other, every colliding row is kept: first_name gets 'A' appended
    # (repeatedly, if needed) until the tuple is unique, then it's inserted
    # under that adjusted name. This is a one-off import script, so re-running
    # it against a circle it already populated will re-insert everything under
    # further-renamed identities rather than skipping - only run it once per
    # circle/source for real (dry-run first, as always).
    staged_identities = set()

    for source, data in records:
        # last_name is allowed to be blank - some historical records only ever
        # captured a first name (see the "Imported from 2024 volunteer CSV" rows),
        # and (first_name, '', email) is still a valid, almost-certainly-unique
        # identity tuple. first_name and email are the fields we can't do without.
        if not data['first_name'] or not data['email']:
            print(f"  SKIP (missing first name or email) in {source}: "
                  f"{data['first_name']!r} {data['last_name']!r} {data['email']!r}")
            skipped_invalid += 1
            continue

        for area_field in ('preferred_area', 'assigned_area_leader'):
            area = data.get(area_field)
            if area and area != 'UNASSIGNED' and area not in known_areas:
                unknown_areas.add(area)

        original_first_name = data['first_name']
        identity = (circle_slug, data['year'], data['first_name'], data['last_name'], data['email'])

        def _identity_taken(identity):
            if identity in staged_identities:
                return True
            return session.query(Participant).filter_by(
                circle_slug=circle_slug, year=identity[1],
                first_name=identity[2], last_name=identity[3], email=identity[4],
            ).first() is not None

        while _identity_taken(identity):
            data['first_name'] += 'A'
            identity = (circle_slug, data['year'], data['first_name'], data['last_name'], data['email'])

        if data['first_name'] != original_first_name:
            print(f"  RENAMED duplicate identity in {source}: "
                  f"{original_first_name!r} {data['last_name']!r} {data['email']!r} ({data['year']}) "
                  f"-> first_name {data['first_name']!r} to satisfy uniqueness constraint")
            renamed += 1

        staged_identities.add(identity)
        now = datetime.now(timezone.utc)
        participant = Participant(
            circle_slug=circle_slug,
            created_at=data['created_at'] or now,
            updated_at=data['updated_at'] or now,
            **{k: v for k, v in data.items() if k not in ('created_at', 'updated_at')},
        )
        session.add(participant)
        inserted += 1

    print(f"\n{source_label}: {inserted} to insert ({renamed} renamed to satisfy the identity "
          f"constraint), {skipped_invalid} skipped (missing name/email).")
    if unknown_areas:
        print(f"  WARNING: area codes not found in circle_areas for '{circle_slug}': "
              f"{sorted(unknown_areas)} (import proceeds - these rows just won't resolve "
              f"an area name/boundary until the area exists).")

    if dry_run:
        print("  --dry-run: rolling back, nothing written.")
        session.rollback()
    else:
        session.commit()
        print(f"  Committed {inserted} participant(s).")

    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--circle', required=True, help='circle_slug to import into (must already exist)')
    parser.add_argument('--dry-run', action='store_true', help='preview without writing')

    parser.add_argument('--csv-dir', required=True, help='directory of *.csv files to import (one per year)')

    args = parser.parse_args()

    session = get_db_session()
    try:
        records = list(iter_csv_rows(args.csv_dir))
        label = f"CSV import from {args.csv_dir}"

        return import_data(session, args.circle, label, records, args.dry_run)
    finally:
        session.close()


if __name__ == '__main__':
    sys.exit(main())
