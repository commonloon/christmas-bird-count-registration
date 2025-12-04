# Updated by Claude AI on 2025-12-02
"""
Composite Index Management for Firestore

Creates, lists, and verifies composite indexes required for the withdrawal feature.
Must be run AFTER data is added to collections.

Usage:
    python manage_indexes.py --create [--database=cbc-test]
    python manage_indexes.py --list [--database=cbc-test]
    python manage_indexes.py --check [--database=cbc-test]
"""

import argparse
import logging
from google.cloud.firestore_admin_v1 import FirestoreAdminClient, Index
from google.cloud.firestore_admin_v1.services.firestore_admin import pagers
from google.api_core.exceptions import AlreadyExists
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Required composite indexes for withdrawal feature
REQUIRED_INDEXES = [
    {
        'collection': 'participants_{year}',
        'fields': [
            {'field_path': 'status', 'order': Index.Field.Order.ASCENDING},
            {'field_path': 'preferred_area', 'order': Index.Field.Order.ASCENDING}
        ],
        'description': 'For filtering active participants by area'
    },
    {
        'collection': 'participants_{year}',
        'fields': [
            {'field_path': 'status', 'order': Index.Field.Order.ASCENDING},
            {'field_path': 'assigned_area_leader', 'order': Index.Field.Order.ASCENDING}
        ],
        'description': 'For filtering active leaders by area'
    }
]


def get_project_id():
    """Get GCP project ID from environment."""
    import os
    project_id = os.getenv('GOOGLE_CLOUD_PROJECT')
    if not project_id:
        # Try to get from gcloud config
        try:
            import subprocess
            result = subprocess.run(['gcloud', 'config', 'get-value', 'project'],
                                  capture_output=True, text=True)
            project_id = result.stdout.strip()
        except:
            pass

    if not project_id:
        logger.error("Could not determine GCP project ID. Set GOOGLE_CLOUD_PROJECT environment variable.")
        return None

    return project_id


def get_current_year():
    """Get current year for collection naming."""
    return datetime.now().year


def create_indexes(database_id='cbc-register'):
    """Create required composite indexes."""
    project_id = get_project_id()
    if not project_id:
        return False

    client = FirestoreAdminClient()
    parent = client.database_path(project_id, database_id)

    current_year = get_current_year()
    created_count = 0

    for index_config in REQUIRED_INDEXES:
        collection = index_config['collection'].format(year=current_year)

        try:
            # Create index definition
            fields = []
            for field_spec in index_config['fields']:
                field = Index.Field()
                field.field_path = field_spec['field_path']
                field.order = field_spec['order']
                fields.append(field)

            index = Index()
            index.query_scope = Index.QueryScope.COLLECTION
            index.collection_id = collection
            index.fields = fields

            logger.info(f"Creating index for {collection}: {' + '.join(f['field_path'] for f in index_config['fields'])}")

            # Create the index
            operation = client.create_index(request={"parent": parent, "index": index})

            # Wait for operation to complete
            result = operation.result(timeout=300)  # 5 minute timeout
            logger.info(f"✓ Index created successfully for {collection}")
            created_count += 1

        except AlreadyExists:
            logger.info(f"✓ Index already exists for {collection}")
        except Exception as e:
            logger.error(f"✗ Failed to create index for {collection}: {e}")

    logger.info(f"\nCompleted: {created_count} index(es) created or verified")
    return True


def list_indexes(database_id='cbc-register'):
    """List all existing composite indexes."""
    project_id = get_project_id()
    if not project_id:
        return False

    client = FirestoreAdminClient()
    parent = client.database_path(project_id, database_id)

    logger.info(f"Existing indexes in database '{database_id}':\n")

    indexes = client.list_indexes(request={"parent": parent})

    index_count = 0
    for index in indexes:
        index_count += 1
        collection = index.collection_id
        fields = [f.field_path for f in index.fields]
        state = "READY" if index.state == 2 else "CREATING"  # 2 = READY
        logger.info(f"{index_count}. Collection: {collection}")
        logger.info(f"   Fields: {' + '.join(fields)}")
        logger.info(f"   State: {state}")
        logger.info("")

    if index_count == 0:
        logger.info("No composite indexes found.")

    return True


def check_indexes(database_id='cbc-register'):
    """Check if all required indexes exist."""
    project_id = get_project_id()
    if not project_id:
        return False

    client = FirestoreAdminClient()
    parent = client.database_path(project_id, database_id)

    current_year = get_current_year()
    existing_indexes = list(client.list_indexes(request={"parent": parent}))

    logger.info(f"Checking required indexes for database '{database_id}':\n")

    all_present = True
    for index_config in REQUIRED_INDEXES:
        collection = index_config['collection'].format(year=current_year)
        required_fields = set(f['field_path'] for f in index_config['fields'])

        found = False
        for existing_index in existing_indexes:
            if existing_index.collection_id == collection:
                existing_fields = set(f.field_path for f in existing_index.fields)
                if required_fields == existing_fields:
                    found = True
                    break

        status = "✓ FOUND" if found else "✗ MISSING"
        fields_str = ' + '.join(f['field_path'] for f in index_config['fields'])
        logger.info(f"{status}: {collection} ({fields_str})")
        logger.info(f"        {index_config['description']}")

        if not found:
            all_present = False

    logger.info("")
    if all_present:
        logger.info("✓ All required indexes are present!")
        return True
    else:
        logger.warning("✗ Some required indexes are missing. Run 'python manage_indexes.py --create' to create them.")
        return False


def main():
    parser = argparse.ArgumentParser(
        description='Manage composite indexes for Firestore withdrawal feature'
    )
    parser.add_argument(
        '--create',
        action='store_true',
        help='Create all required composite indexes'
    )
    parser.add_argument(
        '--list',
        action='store_true',
        help='List all existing composite indexes'
    )
    parser.add_argument(
        '--check',
        action='store_true',
        help='Check if all required indexes exist'
    )
    parser.add_argument(
        '--database',
        default='cbc-register',
        help='Target database (cbc-test or cbc-register, default: cbc-register)'
    )

    args = parser.parse_args()

    # Default to check if no action specified
    if not any([args.create, args.list, args.check]):
        args.check = True

    try:
        if args.create:
            logger.info(f"Creating indexes for database '{args.database}'...\n")
            success = create_indexes(args.database)
        elif args.list:
            success = list_indexes(args.database)
        elif args.check:
            success = check_indexes(args.database)

        return 0 if success else 1
    except Exception as e:
        logger.error(f"Error: {e}")
        return 1


if __name__ == '__main__':
    exit(main())
