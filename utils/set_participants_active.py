#!/usr/bin/env python3
# Updated by Claude AI on 2025-12-11
"""
Set Participants to Active Status (Only Missing Status)

This script updates participants that don't have a status field set to have
status='active'. Participants that already have a status (active or withdrawn)
are left unchanged. This is useful for migrating old data that predates the
status field.

IMPORTANT: This script modifies production data. Use --dry-run first to preview changes.

Usage:
    python set_participants_active.py --database production --year 2025 --dry-run
    python set_participants_active.py --database production --year 2025
    python set_participants_active.py --database test --year 2025

Examples:
    # Preview changes on production for current year
    python set_participants_active.py --dry-run

    # Actually update production for 2025
    python set_participants_active.py --year 2025

    # Update test database
    python set_participants_active.py --database test --year 2025
"""

import argparse
import sys
import os
from datetime import datetime
from google.cloud import firestore

# Add parent directory to path to import config modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config.cloud import GCP_PROJECT_ID, TEST_DATABASE, PRODUCTION_DATABASE


def get_firestore_client(database_id: str):
    """
    Get Firestore client for specified database.

    Args:
        database_id: The database ID (cbc-test or cbc-register)

    Returns:
        Firestore client instance
    """
    return firestore.Client(project=GCP_PROJECT_ID, database=database_id)


def get_participants(db, year: int):
    """
    Get all participants for the specified year.

    Args:
        db: Firestore client
        year: Year to query

    Returns:
        List of (doc_id, participant_data) tuples
    """
    collection_name = f'participants_{year}'
    participants = []

    docs = db.collection(collection_name).stream()
    for doc in docs:
        data = doc.to_dict()
        participants.append((doc.id, data))

    return participants


def set_all_participants_active(db, year: int, dry_run: bool = False):
    """
    Set participants without a status field to active status.
    Leaves participants that already have a status (active or withdrawn) unchanged.

    Args:
        db: Firestore client
        year: Year to update
        dry_run: If True, only preview changes without applying them

    Returns:
        Tuple of (total_participants, updated_count, missing_status_count)
    """
    collection_name = f'participants_{year}'
    participants = get_participants(db, year)

    total_count = len(participants)
    missing_status_count = 0
    updated_count = 0
    active_count = 0
    withdrawn_count = 0

    print(f"\nAnalyzing {total_count} participants in {collection_name}...")

    # Count participants by status
    for doc_id, data in participants:
        status = data.get('status')
        if status is None:
            missing_status_count += 1
        elif status == 'active':
            active_count += 1
        elif status == 'withdrawn':
            withdrawn_count += 1

    print(f"Status breakdown:")
    print(f"  - Missing status: {missing_status_count}")
    print(f"  - Active: {active_count}")
    print(f"  - Withdrawn: {withdrawn_count}")

    if missing_status_count == 0:
        print(f"\n✓ All {total_count} participants already have a status field")
        return total_count, 0, 0

    print(f"\nFound {missing_status_count} participants without a status field")

    if dry_run:
        print("\n[DRY RUN] Would update the following participants to status='active':")
        for doc_id, data in participants:
            if data.get('status') is None:
                name = f"{data.get('first_name', '')} {data.get('last_name', '')}"
                area = data.get('preferred_area', 'UNASSIGNED')
                email = data.get('email', '')
                print(f"  - {name} ({email}) in Area {area}")
        print(f"\n[DRY RUN] Would update {missing_status_count} participants to status='active'")
        print(f"[DRY RUN] Would leave {withdrawn_count} withdrawn and {active_count} active participants unchanged")
        return total_count, missing_status_count, missing_status_count

    # Confirm before proceeding
    print(f"\nThis will update {missing_status_count} participants to status='active'")
    print(f"Withdrawn ({withdrawn_count}) and active ({active_count}) participants will be left unchanged")
    response = input("\nContinue? (yes/no): ").strip().lower()
    if response not in ['yes', 'y']:
        print("Operation cancelled")
        return total_count, 0, missing_status_count

    # Perform updates
    print("\nUpdating participants...")
    batch = db.batch()
    batch_count = 0

    for doc_id, data in participants:
        if data.get('status') is None:
            doc_ref = db.collection(collection_name).document(doc_id)
            batch.update(doc_ref, {
                'status': 'active',
                'updated_at': datetime.now()
            })
            batch_count += 1
            updated_count += 1

            # Commit batch every 500 operations (Firestore limit is 500)
            if batch_count >= 500:
                batch.commit()
                print(f"  Committed {batch_count} updates...")
                batch = db.batch()
                batch_count = 0

    # Commit remaining updates
    if batch_count > 0:
        batch.commit()
        print(f"  Committed {batch_count} updates...")

    print(f"\n✓ Successfully updated {updated_count} participants to status='active'")
    return total_count, updated_count, missing_status_count


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description='Set all participants to active status',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Preview changes on production for current year
  python set_participants_active.py --dry-run

  # Update production for 2025
  python set_participants_active.py --year 2025

  # Update test database
  python set_participants_active.py --database test --year 2025

IMPORTANT: Always use --dry-run first to preview changes before applying them.
        """
    )

    parser.add_argument(
        '--database',
        choices=['test', 'production', 'prod'],
        default='production',
        help='Target database (default: production)'
    )

    parser.add_argument(
        '--year',
        type=int,
        default=datetime.now().year,
        help=f'Year to update (default: {datetime.now().year})'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview changes without applying them'
    )

    args = parser.parse_args()

    # Normalize database name
    db_name = 'production' if args.database == 'prod' else args.database

    # Get appropriate database ID
    database_id = TEST_DATABASE if db_name == 'test' else PRODUCTION_DATABASE

    print("=" * 70)
    print("SET PARTICIPANTS TO ACTIVE STATUS (MISSING STATUS ONLY)")
    print("=" * 70)
    print(f"Database: {database_id} ({db_name})")
    print(f"Year: {args.year}")
    print(f"Mode: {'DRY RUN (preview only)' if args.dry_run else 'LIVE UPDATE'}")
    print("=" * 70)

    if not args.dry_run and db_name == 'production':
        print("\n⚠️  WARNING: This will modify PRODUCTION data!")
        print("Consider running with --dry-run first to preview changes.")
        response = input("\nProceed with production update? (yes/no): ").strip().lower()
        if response not in ['yes', 'y']:
            print("Operation cancelled")
            sys.exit(0)

    # Get Firestore client
    try:
        db = get_firestore_client(database_id)
    except Exception as e:
        print(f"\n[ERROR] Failed to connect to Firestore: {e}")
        print("Make sure you're authenticated with: gcloud auth application-default login")
        sys.exit(1)

    # Perform the update
    try:
        total, updated, withdrawn = set_all_participants_active(db, args.year, args.dry_run)

        print("\n" + "=" * 70)
        print("SUMMARY")
        print("=" * 70)
        print(f"Total participants: {total}")
        print(f"Missing status field: {withdrawn}")
        if args.dry_run:
            print(f"Would update: {updated}")
        else:
            print(f"Updated to active: {updated}")
        print("=" * 70)

        sys.exit(0)

    except Exception as e:
        print(f"\n[ERROR] Operation failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
