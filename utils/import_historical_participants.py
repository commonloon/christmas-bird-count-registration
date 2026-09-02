# utils/import_historical_participants.py
# Updated by Claude AI on 2026-09-02
#
# One-off importer for historical participant/leader data into the Postgres-backed
# multi-circle schema. Leadership fields live directly on the participant row (no
# separate area-leaders table), so this single importer covers both.
#
# Two sources:
#   --csv-dir DIR   Import every *.csv in DIR (see utils/participant-csv-dumps/<slug>/).
#                   Each row's own `year` column is authoritative, not the filename.
#   --firestore     Read a Firestore collection directly. Used for circles whose CSV
#                   export is missing or wasn't produced - see the named-database
#                   gotcha below.
#
# The target circle (and its areas) must already exist in Postgres - create it via
# /bigbird/circles/new and import its area boundaries (KML upload) first. This script
# only writes to the participants table.
#
# Usage:
#   python utils/import_historical_participants.py --circle vancouver --csv-dir utils/participant-csv-dumps/vancouver
#   python utils/import_historical_participants.py --circle ladner --csv-dir utils/participant-csv-dumps/ladner
#   python utils/import_historical_participants.py --circle comox-spring --csv-dir utils/participant-csv-dumps/comox-spring
#   python utils/import_historical_participants.py --circle nanaimo --firestore \
#       --project nanaimo-cbc --database nanaimo-cbc --collection participants_2025 --year 2025
#
# Add --dry-run to preview counts/warnings without writing anything.
#
# Firestore gotcha: a project created with a *named* database (not "(default)") makes
# google.cloud.firestore.Client() fail with a 404 that reads like "no data" rather than
# "wrong database" unless database=... is passed explicitly. nanaimo-cbc uses a database
# named "nanaimo-cbc" (prod) / "nanaimo-test" (test) - run `gcloud firestore databases
# list --project=<project>` if unsure what a given project's database is named.

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
    live Firestore read that the source data is stored in UTC, so naive strings here
    are interpreted as UTC."""
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
        'interested_in_scribe': parse_csv_bool(row.get('interested_in_scribe')),
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


def normalize_firestore_doc(doc_dict, fallback_year):
    return {
        'first_name': sanitize_name(doc_dict.get('first_name') or ''),
        'last_name': sanitize_name(doc_dict.get('last_name') or ''),
        'email': sanitize_email(doc_dict.get('email') or ''),
        'phone': sanitize_phone(doc_dict.get('phone') or ''),
        'phone2': sanitize_phone(doc_dict.get('phone2') or ''),
        'skill_level': doc_dict.get('skill_level') or None,
        'experience': doc_dict.get('experience') or None,
        'preferred_area': doc_dict.get('preferred_area') or None,
        'participation_type': doc_dict.get('participation_type') or 'regular',
        'has_binoculars': bool(doc_dict.get('has_binoculars')),
        'spotting_scope': bool(doc_dict.get('spotting_scope')),
        'interested_in_leadership': bool(doc_dict.get('interested_in_leadership')),
        'interested_in_scribe': bool(doc_dict.get('interested_in_scribe')),
        'notes_to_organizers': sanitize_notes(doc_dict.get('notes_to_organizers') or ''),
        'is_leader': bool(doc_dict.get('is_leader')),
        'assigned_area_leader': doc_dict.get('assigned_area_leader') or None,
        'assigned_by': doc_dict.get('assigned_by') or None,
        'assigned_at': doc_dict.get('assigned_at'),
        'leadership_assigned_by': doc_dict.get('leadership_assigned_by') or None,
        'leadership_assigned_at': doc_dict.get('leadership_assigned_at'),
        'leadership_removed_by': doc_dict.get('leadership_removed_by') or None,
        'leadership_removed_at': doc_dict.get('leadership_removed_at'),
        'created_at': doc_dict.get('created_at'),
        'updated_at': doc_dict.get('updated_at'),
        'year': int(doc_dict.get('year') or fallback_year),
        'status': doc_dict.get('status') or 'active',
    }


def iter_csv_rows(csv_dir):
    for path in sorted(glob.glob(os.path.join(csv_dir, '*.csv'))):
        with open(path, encoding='utf-8') as f:
            for row in csv.DictReader(f):
                yield path, normalize_csv_row(row)


def iter_firestore_docs(project, database, collection, year):
    from google.cloud import firestore

    client = firestore.Client(project=project, database=database)
    for doc in client.collection(collection).stream():
        yield f"{project}/{database}/{collection}/{doc.id}", normalize_firestore_doc(doc.to_dict(), year)


def import_data(session, circle_slug, source_label, records, dry_run):
    circle = CircleModel(session).get_by_slug(circle_slug)
    if not circle:
        print(f"ERROR: circle '{circle_slug}' does not exist yet - "
              f"create it via /bigbird/circles/new first, then import its areas.")
        return 1

    known_areas = {a['code'] for a in CircleAreaModel(session).get_areas_for_circle(circle_slug)}

    inserted = 0
    skipped_duplicate = 0
    skipped_invalid = 0
    unknown_areas = set()

    for source, data in records:
        if not data['first_name'] or not data['last_name'] or not data['email']:
            print(f"  SKIP (missing identity field) in {source}: "
                  f"{data['first_name']!r} {data['last_name']!r} {data['email']!r}")
            skipped_invalid += 1
            continue

        for area_field in ('preferred_area', 'assigned_area_leader'):
            area = data.get(area_field)
            if area and area != 'UNASSIGNED' and area not in known_areas:
                unknown_areas.add(area)

        existing = session.query(Participant).filter_by(
            circle_slug=circle_slug, year=data['year'],
            first_name=data['first_name'], last_name=data['last_name'], email=data['email'],
        ).first()
        if existing:
            skipped_duplicate += 1
            continue

        now = datetime.now(timezone.utc)
        participant = Participant(
            circle_slug=circle_slug,
            created_at=data['created_at'] or now,
            updated_at=data['updated_at'] or now,
            **{k: v for k, v in data.items() if k not in ('created_at', 'updated_at')},
        )
        session.add(participant)
        inserted += 1

    print(f"\n{source_label}: {inserted} to insert, {skipped_duplicate} already present "
          f"(identity match), {skipped_invalid} skipped (missing name/email).")
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

    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--csv-dir', help='directory of *.csv files to import (one per year)')
    source.add_argument('--firestore', action='store_true', help='read from Firestore instead of CSV')

    fs = parser.add_argument_group('firestore options')
    fs.add_argument('--project', help='GCP project ID')
    fs.add_argument('--database', help='Firestore database ID (not "(default)" for named-database projects)')
    fs.add_argument('--collection', help='Firestore collection name, e.g. participants_2025')
    fs.add_argument('--year', type=int, help='fallback year if a document has no year field')

    args = parser.parse_args()

    if args.firestore and not (args.project and args.database and args.collection and args.year):
        parser.error('--firestore requires --project, --database, --collection, and --year')

    session = get_db_session()
    try:
        if args.csv_dir:
            records = list(iter_csv_rows(args.csv_dir))
            label = f"CSV import from {args.csv_dir}"
        else:
            records = list(iter_firestore_docs(args.project, args.database, args.collection, args.year))
            label = f"Firestore import from {args.project}/{args.database}/{args.collection}"

        return import_data(session, args.circle, label, records, args.dry_run)
    finally:
        session.close()


if __name__ == '__main__':
    sys.exit(main())
