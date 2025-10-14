#!/usr/bin/env python3
"""
Updated by Claude AI on 2025-10-14
Firestore Index Verification Script

This script verifies that all required Firestore indexes exist for the current year's
collections. It's designed to be run by non-technical volunteers at the start of each
registration season.

The script will:
1. Check if this year's collections exist (participants_YYYY, removal_log_YYYY)
2. Create dummy data if collections don't exist yet
3. Verify all required indexes exist
4. Create any missing indexes automatically
5. Provide clear, non-technical status messages

Usage:
    python verify_indexes.py [database_name]

Examples:
    python verify_indexes.py <test-db>       # Check test database
    python verify_indexes.py <prod-db>       # Check production database
    python verify_indexes.py                 # Prompts for database choice
"""

import sys
import os
from datetime import datetime
from google.cloud.firestore_admin_v1 import FirestoreAdminClient
from google.cloud.firestore_admin_v1.types import Index
from google.cloud import firestore
from google.api_core import exceptions
import logging

# Add parent directory to path for config imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.cloud import GCP_PROJECT_ID, GCP_LOCATION, TEST_DATABASE, PRODUCTION_DATABASE

# Current year for collection names
CURRENT_YEAR = datetime.now().year

# Required composite indexes for the application
# These are needed for complex queries with multiple filter conditions
REQUIRED_INDEXES = {
    f'participants_{CURRENT_YEAR}': [
        {
            'name': 'Identity-based queries',
            'fields': [
                {'field_path': 'email', 'order': Index.IndexField.Order.ASCENDING},
                {'field_path': 'first_name', 'order': Index.IndexField.Order.ASCENDING},
                {'field_path': 'last_name', 'order': Index.IndexField.Order.ASCENDING},
                {'field_path': '__name__', 'order': Index.IndexField.Order.ASCENDING}
            ],
            'query_scope': Index.QueryScope.COLLECTION
        },
        {
            'name': 'Leadership assignment queries',
            'fields': [
                {'field_path': 'is_leader', 'order': Index.IndexField.Order.ASCENDING},
                {'field_path': 'assigned_area_leader', 'order': Index.IndexField.Order.ASCENDING},
                {'field_path': '__name__', 'order': Index.IndexField.Order.ASCENDING}
            ],
            'query_scope': Index.QueryScope.COLLECTION
        },
        {
            'name': 'Leadership interest queries',
            'fields': [
                {'field_path': 'interested_in_leadership', 'order': Index.IndexField.Order.ASCENDING},
                {'field_path': 'is_leader', 'order': Index.IndexField.Order.ASCENDING},
                {'field_path': '__name__', 'order': Index.IndexField.Order.ASCENDING}
            ],
            'query_scope': Index.QueryScope.COLLECTION
        },
        {
            'name': 'Email-based leader verification',
            'fields': [
                {'field_path': 'email', 'order': Index.IndexField.Order.ASCENDING},
                {'field_path': 'is_leader', 'order': Index.IndexField.Order.ASCENDING},
                {'field_path': '__name__', 'order': Index.IndexField.Order.ASCENDING}
            ],
            'query_scope': Index.QueryScope.COLLECTION
        },
        {
            'name': 'Area-specific leader verification',
            'fields': [
                {'field_path': 'email', 'order': Index.IndexField.Order.ASCENDING},
                {'field_path': 'is_leader', 'order': Index.IndexField.Order.ASCENDING},
                {'field_path': 'assigned_area_leader', 'order': Index.IndexField.Order.ASCENDING},
                {'field_path': '__name__', 'order': Index.IndexField.Order.ASCENDING}
            ],
            'query_scope': Index.QueryScope.COLLECTION
        }
    ],
    f'removal_log_{CURRENT_YEAR}': [
        {
            'name': 'Email notification tracking',
            'fields': [
                {'field_path': 'emailed', 'order': Index.IndexField.Order.ASCENDING},
                {'field_path': 'area_code', 'order': Index.IndexField.Order.ASCENDING},
                {'field_path': '__name__', 'order': Index.IndexField.Order.ASCENDING}
            ],
            'query_scope': Index.QueryScope.COLLECTION
        },
        {
            'name': 'Area removal history (ascending)',
            'fields': [
                {'field_path': 'area_code', 'order': Index.IndexField.Order.ASCENDING},
                {'field_path': 'removed_at', 'order': Index.IndexField.Order.ASCENDING},
                {'field_path': '__name__', 'order': Index.IndexField.Order.ASCENDING}
            ],
            'query_scope': Index.QueryScope.COLLECTION
        },
        {
            'name': 'Area removal history (descending)',
            'fields': [
                {'field_path': 'area_code', 'order': Index.IndexField.Order.ASCENDING},
                {'field_path': 'removed_at', 'order': Index.IndexField.Order.DESCENDING},
                {'field_path': '__name__', 'order': Index.IndexField.Order.DESCENDING}
            ],
            'query_scope': Index.QueryScope.COLLECTION
        }
    ]
}


def print_banner():
    """Print welcome banner."""
    print("\n" + "=" * 70)
    print(" CBC Registration System - Index Verification")
    print("=" * 70)
    print(f" Year: {CURRENT_YEAR}")
    print(f" Project: {GCP_PROJECT_ID}")
    print("=" * 70 + "\n")


def get_database_choice():
    """Prompt user to choose which database to check."""
    print("Which database would you like to verify?")
    print(f"  1. {TEST_DATABASE} (test/development)")
    print(f"  2. {PRODUCTION_DATABASE} (production)")
    print()

    while True:
        choice = input("Enter choice (1 or 2): ").strip()
        if choice == '1':
            return TEST_DATABASE
        elif choice == '2':
            return PRODUCTION_DATABASE
        else:
            print("Invalid choice. Please enter 1 or 2.")


def check_collection_exists(db_client, collection_name):
    """Check if a collection exists by trying to read from it."""
    try:
        # Try to get one document from the collection
        docs = db_client.collection(collection_name).limit(1).stream()
        # Convert to list to actually execute the query
        return len(list(docs)) >= 0  # Collection exists even if empty
    except Exception as e:
        logging.debug(f"Collection check error for {collection_name}: {e}")
        return False


def create_dummy_removal(db_client, year):
    """Create a permanent dummy removal log entry to prevent collection auto-deletion."""
    collection_name = f'removal_log_{year}'
    dummy_removal = {
        'participant_name': '_DUMMY_INDEX_SETUP_',
        'participant_email': f'dummy-index-setup-{year}@example.com',
        'area_code': 'UNASSIGNED',
        'removed_by': 'verify_indexes.py',
        'reason': 'Permanent dummy entry to prevent Firestore auto-deletion of empty collection',
        'removed_at': datetime.now(),
        'year': year,
        'emailed': False
    }

    # Add the dummy removal and leave it (prevents auto-deletion)
    doc_ref = db_client.collection(collection_name).add(dummy_removal)
    return doc_ref[1].id


def get_existing_indexes(admin_client, database_id):
    """Get list of existing composite indexes in the database."""
    try:
        database_name = f"projects/{GCP_PROJECT_ID}/databases/{database_id}"
        existing_indexes = {}

        # List all collection groups to find indexes
        for collection_id in [f'participants_{CURRENT_YEAR}', f'removal_log_{CURRENT_YEAR}']:
            collection_path = f"{database_name}/collectionGroups/{collection_id}"

            try:
                indexes_list = admin_client.list_indexes(parent=collection_path)
                collection_indexes = []

                for index in indexes_list:
                    # Extract field paths from the index
                    field_paths = tuple(field.field_path for field in index.fields)
                    collection_indexes.append(field_paths)

                existing_indexes[collection_id] = collection_indexes
            except exceptions.NotFound:
                # Collection doesn't have indexes yet
                existing_indexes[collection_id] = []
            except Exception as e:
                logging.debug(f"Error listing indexes for {collection_id}: {e}")
                existing_indexes[collection_id] = []

        return existing_indexes
    except Exception as e:
        logging.error(f"Error getting existing indexes: {e}")
        return {}


def index_exists(field_paths, existing_indexes):
    """Check if an index with the given field paths already exists."""
    field_tuple = tuple(field['field_path'] for field in field_paths)
    return field_tuple in existing_indexes


def create_missing_indexes(admin_client, database_id, existing_indexes):
    """Create any missing indexes."""
    database_name = f"projects/{GCP_PROJECT_ID}/databases/{database_id}"
    created_count = 0
    already_exists_count = 0
    failed_count = 0

    print("\n>> Checking indexes...")
    print()

    for collection_id, indexes in REQUIRED_INDEXES.items():
        collection_existing = existing_indexes.get(collection_id, [])
        collection_path = f"{database_name}/collectionGroups/{collection_id}"

        for index_config in indexes:
            index_name = index_config['name']
            field_names = [field['field_path'] for field in index_config['fields']]

            if index_exists(index_config['fields'], collection_existing):
                print(f"  [OK] {index_name}")
                print(f"       Collection: {collection_id}")
                print(f"       Fields: {', '.join(field_names)}")
                already_exists_count += 1
            else:
                print(f"  [CREATING] {index_name}")
                print(f"             Collection: {collection_id}")
                print(f"             Fields: {', '.join(field_names)}")
                print(f"             Status: Creating...")

                try:
                    # Build index fields
                    index_fields = []
                    for field_config in index_config['fields']:
                        field = Index.IndexField(
                            field_path=field_config['field_path'],
                            order=field_config['order']
                        )
                        index_fields.append(field)

                    # Create index
                    index = Index(
                        query_scope=index_config['query_scope'],
                        fields=index_fields
                    )

                    operation = admin_client.create_index(
                        parent=collection_path,
                        index=index
                    )

                    print(f"             [OK] Index creation started (building in background)")
                    created_count += 1

                except exceptions.AlreadyExists:
                    print(f"             [OK] Index already exists")
                    already_exists_count += 1
                except Exception as e:
                    print(f"             ERROR: Failed to create: {e}")
                    failed_count += 1

            print()  # Blank line between indexes

    return created_count, already_exists_count, failed_count


def main():
    """Main function."""
    # Setup logging
    logging.basicConfig(level=logging.INFO, format='%(message)s')

    print_banner()

    # Get database choice
    if len(sys.argv) > 1:
        database_id = sys.argv[1]
        if database_id not in [TEST_DATABASE, PRODUCTION_DATABASE]:
            print(f"❌ Error: Invalid database '{database_id}'")
            print(f"   Valid options: {TEST_DATABASE}, {PRODUCTION_DATABASE}")
            sys.exit(1)
    else:
        database_id = get_database_choice()

    print(f"\n>> Checking database: {database_id}")
    print()

    # Initialize clients
    try:
        admin_client = FirestoreAdminClient()
        db_client = firestore.Client(project=GCP_PROJECT_ID, database=database_id)
    except Exception as e:
        print(f"ERROR: Could not connect to Google Cloud")
        print(f"   {e}")
        print()
        print("Troubleshooting:")
        print("   1. Make sure you're logged in: gcloud auth login")
        print("   2. Check your project: gcloud config get-value project")
        print("   3. Verify you have Firestore permissions")
        sys.exit(1)

    # Check if collections exist
    participants_collection = f'participants_{CURRENT_YEAR}'
    removal_log_collection = f'removal_log_{CURRENT_YEAR}'

    print(f">> Checking collections for {CURRENT_YEAR}...")

    participants_exists = check_collection_exists(db_client, participants_collection)
    removal_log_exists = check_collection_exists(db_client, removal_log_collection)

    if not participants_exists:
        print(f"   WARNING: {participants_collection} doesn't exist yet")
        print(f"   ACTION REQUIRED: Please register yourself first at the registration page")
        print(f"      This will create the collection needed for index setup")
        print()
        print(f"   After registering, run this script again.")
        sys.exit(0)
    else:
        print(f"   [OK] {participants_collection} exists")

    if not removal_log_exists:
        print(f"   WARNING: {removal_log_collection} doesn't exist yet")
        print(f"   Creating collection with permanent dummy entry...")
        try:
            # Create permanent dummy removal entry (prevents Firestore auto-deletion)
            dummy_id = create_dummy_removal(db_client, CURRENT_YEAR)
            print(f"   [OK] {removal_log_collection} created with dummy entry (ID: {dummy_id})")
            print(f"   NOTE: Dummy entry will remain to prevent auto-deletion of empty collection")
        except Exception as e:
            print(f"   ERROR: Failed to create collection: {e}")
            sys.exit(1)
    else:
        print(f"   [OK] {removal_log_collection} exists")

    print()

    # Get existing indexes
    existing_indexes = get_existing_indexes(admin_client, database_id)

    # Create missing indexes
    created, exists, failed = create_missing_indexes(admin_client, database_id, existing_indexes)

    # Summary
    print("\n" + "=" * 70)
    print(" Summary")
    print("=" * 70)
    print(f"  [OK] Indexes already existed: {exists}")
    print(f"  [NEW] New indexes created: {created}")
    if failed > 0:
        print(f"  [FAIL] Failed to create: {failed}")
    print("=" * 70 + "\n")

    if created > 0:
        print("NOTE: New indexes are building in the background.")
        print("   This can take several minutes. The application will work")
        print("   correctly even while indexes are building.")
        print()

    if failed > 0:
        print("WARNING: Some indexes failed to create. Check the error messages above.")
        print("   The application may experience slow queries until all indexes exist.")
        print()
        sys.exit(1)
    else:
        print("SUCCESS: All indexes are ready!")
        print()
        print("Next steps:")
        print("   1. Your database is ready for the registration season")
        print("   2. Test the registration form to confirm everything works")
        print("   3. Share the registration URL with participants")
        print()


if __name__ == "__main__":
    main()
