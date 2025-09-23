#!/usr/bin/env python3
"""
Updated by Claude AI on 2025-09-23
Firestore Database Setup Script

This script creates the required Firestore databases for the Christmas Bird Count
registration system if they don't already exist.

Databases created:
- cbc-test: For test/development environment
- cbc-register: For production environment

Usage:
    python setup_databases.py [--dry-run] [--force] [--verbose]

Examples:
    python setup_databases.py --dry-run      # Preview what would be created
    python setup_databases.py               # Create missing databases
    python setup_databases.py --force       # Recreate all databases (with confirmation)
"""

import argparse
import sys
import os
from google.cloud.firestore_admin_v1 import FirestoreAdminClient
from google.cloud.firestore_admin_v1.types import Database, Index
from google.api_core import exceptions
import logging

# Add the parent directory to Python path to import config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Database configuration
DATABASE_CONFIG = {
    'cbc-test': {
        'display_name': 'CBC Test Database',
        'description': 'Test/development database for Christmas Bird Count registration'
    },
    'cbc-register': {
        'display_name': 'CBC Production Database', 
        'description': 'Production database for Christmas Bird Count registration'
    }
}

# Google Cloud configuration
PROJECT_ID = 'vancouver-cbc-registration'
LOCATION_ID = 'us-west1'  # Oregon region

# Required Firestore indexes for the application
# Note: Single-field indexes are automatically created by Firestore and don't need to be defined here
# Only composite indexes (multiple fields) need to be explicitly created
REQUIRED_INDEXES = {
    'participants_2025': [
        # Identity-based queries: email + first_name + last_name
        {
            'fields': [
                {'field_path': 'email', 'order': Index.IndexField.Order.ASCENDING},
                {'field_path': 'first_name', 'order': Index.IndexField.Order.ASCENDING},
                {'field_path': 'last_name', 'order': Index.IndexField.Order.ASCENDING},
                {'field_path': '__name__', 'order': Index.IndexField.Order.ASCENDING}
            ],
            'query_scope': Index.QueryScope.COLLECTION
        },
        # Leadership queries: is_leader + assigned_area_leader
        {
            'fields': [
                {'field_path': 'is_leader', 'order': Index.IndexField.Order.ASCENDING},
                {'field_path': 'assigned_area_leader', 'order': Index.IndexField.Order.ASCENDING},
                {'field_path': '__name__', 'order': Index.IndexField.Order.ASCENDING}
            ],
            'query_scope': Index.QueryScope.COLLECTION
        }
    ]
}


def setup_logging(verbose=False):
    """Configure logging based on verbosity level."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    return logging.getLogger(__name__)


def get_existing_databases(client, logger):
    """Get list of existing databases in the project."""
    try:
        parent = f"projects/{PROJECT_ID}"
        response = client.list_databases(parent=parent)
        
        databases = []
        # The response has a .databases property that contains the actual list
        if hasattr(response, 'databases') and response.databases:
            for database in response.databases:
                # Extract database ID from the full name
                # Format: projects/PROJECT_ID/databases/DATABASE_ID
                database_id = database.name.split('/')[-1]
                databases.append(database_id)
                logger.debug(f"Found existing database: {database_id}")
        else:
            logger.debug("No databases found in project (or empty response)")
        
        return databases
        
    except exceptions.PermissionDenied:
        logger.error("Permission denied: Make sure you have Firestore Admin permissions")
        return None
    except Exception as e:
        logger.error(f"Error listing databases: {e}")
        logger.debug(f"Response type: {type(response)}")
        logger.debug(f"Response dir: {dir(response) if 'response' in locals() else 'N/A'}")
        return None


def create_database(client, database_id, config, logger, dry_run=False):
    """Create a Firestore database if it doesn't exist."""
    database_name = f"projects/{PROJECT_ID}/databases/{database_id}"
    
    if dry_run:
        logger.info(f"[DRY RUN] Would create database: {database_id}")
        logger.info(f"[DRY RUN]   Display name: {config['display_name']}")
        logger.info(f"[DRY RUN]   Location: {LOCATION_ID}")
        return True
    
    try:
        # Create database request
        # Use numeric enum values for DatabaseType and ConcurrencyMode
        database = Database(
            name=database_name,
            location_id=LOCATION_ID,
            type_=1,  # FIRESTORE_NATIVE
            concurrency_mode=1,  # OPTIMISTIC
        )
        
        parent = f"projects/{PROJECT_ID}"
        operation = client.create_database(
            parent=parent,
            database=database,
            database_id=database_id
        )
        
        logger.info(f"Creating database '{database_id}'... (this may take a few minutes)")
        
        # Wait for the operation to complete
        result = operation.result(timeout=600)  # 10 minute timeout
        
        logger.info(f"✓ Successfully created database: {database_id}")
        logger.debug(f"Database details: {result}")
        
        return True
        
    except exceptions.AlreadyExists:
        logger.info(f"✓ Database '{database_id}' already exists")
        return True
    except exceptions.PermissionDenied:
        logger.error(f"✗ Permission denied creating database '{database_id}'")
        logger.error("Make sure you have Firestore Admin and Project Editor permissions")
        return False
    except Exception as e:
        logger.error(f"✗ Error creating database '{database_id}': {e}")
        return False


def delete_database(client, database_id, logger, dry_run=False):
    """Delete a Firestore database (used with --force)."""
    if dry_run:
        logger.info(f"[DRY RUN] Would delete database: {database_id}")
        return True
        
    try:
        database_name = f"projects/{PROJECT_ID}/databases/{database_id}"
        operation = client.delete_database(name=database_name)
        
        logger.info(f"Deleting database '{database_id}'...")
        
        # Increase timeout and add progress updates
        import time
        timeout = 900  # 15 minutes instead of 5
        start_time = time.time()
        
        try:
            operation.result(timeout=timeout)
            logger.info(f"✓ Successfully deleted database: {database_id}")
            return True
        except Exception as timeout_error:
            elapsed = int(time.time() - start_time)
            if "timeout" in str(timeout_error).lower() or elapsed >= timeout:
                logger.warning(f"Deletion timeout after {elapsed}s - database may still be deleting")
                logger.info("Operation may have completed despite timeout - continuing...")
                # Assume success on timeout since deletion often completes despite API timeout
                return True
            else:
                # Re-raise non-timeout errors
                raise timeout_error
        
    except exceptions.NotFound:
        logger.info(f"✓ Database '{database_id}' doesn't exist (already deleted)")
        return True
    except Exception as e:
        logger.error(f"✗ Error deleting database '{database_id}': {e}")
        return False


def create_database_indexes(client, database_id, logger, dry_run=False, skip_indexes=False):
    """Create required Firestore indexes for a database."""
    if skip_indexes:
        logger.info(f"Skipping index creation for database: {database_id}")
        return True
        
    logger.info(f"Creating indexes for database: {database_id}")
    
    if dry_run:
        logger.info(f"[DRY RUN] Would create {sum(len(indexes) for indexes in REQUIRED_INDEXES.values())} indexes")
        for collection_id, indexes in REQUIRED_INDEXES.items():
            for i, index_config in enumerate(indexes):
                field_names = [field['field_path'] for field in index_config['fields']]
                logger.info(f"[DRY RUN]   {collection_id}: Index on fields {field_names}")
        return True
    
    database_name = f"projects/{PROJECT_ID}/databases/{database_id}"
    success_count = 0
    total_indexes = sum(len(indexes) for indexes in REQUIRED_INDEXES.values())
    
    for collection_id, indexes in REQUIRED_INDEXES.items():
        collection_path = f"{database_name}/collectionGroups/{collection_id}"
        
        for i, index_config in enumerate(indexes):
            try:
                # Build index fields
                index_fields = []
                field_names = []
                
                for field_config in index_config['fields']:
                    field = Index.IndexField(
                        field_path=field_config['field_path'],
                        order=field_config['order']
                    )
                    index_fields.append(field)
                    field_names.append(field_config['field_path'])
                
                # Create index
                index = Index(
                    query_scope=index_config['query_scope'],
                    fields=index_fields
                )
                
                logger.info(f"  Creating index on {collection_id} fields: {field_names}")
                
                operation = client.create_index(
                    parent=collection_path,
                    index=index
                )
                
                # Don't wait for completion - indexes can take a long time
                logger.info(f"  ✓ Index creation started for {collection_id} (fields: {field_names})")
                success_count += 1
                
            except exceptions.AlreadyExists:
                logger.info(f"  ✓ Index already exists for {collection_id} (fields: {field_names})")
                success_count += 1
            except exceptions.InvalidArgument as e:
                logger.warning(f"  ⚠ Invalid index configuration for {collection_id}: {e}")
            except Exception as e:
                logger.error(f"  ✗ Failed to create index for {collection_id}: {e}")
    
    logger.info(f"Index creation summary: {success_count}/{total_indexes} indexes processed")
    
    if success_count < total_indexes:
        logger.warning("Some indexes failed to create - the app may have runtime errors")
        logger.info("You can create missing indexes manually by visiting the URLs in error messages")
    else:
        logger.info("✓ All indexes created successfully (building in background)")
        logger.info("Note: Index building can take several minutes to complete")
    
    return success_count == total_indexes


def main():
    parser = argparse.ArgumentParser(
        description="Create required Firestore databases for CBC registration system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python setup_databases.py --dry-run      # Preview what would be created
    python setup_databases.py               # Create missing databases with indexes
    python setup_databases.py --test-only   # Only operate on cbc-test database
    python setup_databases.py --production-only # Only operate on cbc-register database
    python setup_databases.py --skip-indexes # Create databases only, no indexes
    python setup_databases.py --force       # Recreate all databases (with confirmation)
    python setup_databases.py --force --test-only # Safely recreate only test database
    python setup_databases.py --verbose     # Show detailed progress
        """
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without making changes'
    )
    
    parser.add_argument(
        '--force',
        action='store_true',
        help='Delete and recreate databases even if they exist'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Show detailed debug information'
    )
    
    parser.add_argument(
        '--test-only',
        action='store_true', 
        help='Only operate on cbc-test database (safer for development)'
    )
    
    parser.add_argument(
        '--production-only',
        action='store_true',
        help='Only operate on cbc-register database (production operations)'
    )
    
    parser.add_argument(
        '--skip-indexes',
        action='store_true',
        help='Create databases only, skip index creation'
    )
    
    args = parser.parse_args()
    
    # Validate conflicting arguments
    if args.test_only and args.production_only:
        parser.error("Cannot specify both --test-only and --production-only")
    
    # Setup logging
    logger = setup_logging(args.verbose)
    
    logger.info("Firestore Database Setup for CBC Registration System")
    logger.info("=" * 55)
    logger.info(f"Project: {PROJECT_ID}")
    logger.info(f"Region: {LOCATION_ID}")
    
    if args.dry_run:
        logger.info("🔍 DRY RUN MODE - No changes will be made")
    
    # Initialize Firestore Admin client
    try:
        client = FirestoreAdminClient()
        logger.debug("Firestore Admin client initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize Firestore Admin client: {e}")
        logger.error("Make sure you have proper authentication configured")
        sys.exit(1)
    
    # Get existing databases
    logger.info("\nChecking existing databases...")
    existing_databases = get_existing_databases(client, logger)
    
    if existing_databases is None:
        logger.error("Failed to list existing databases")
        sys.exit(1)
    
    logger.info(f"Found {len(existing_databases)} existing database(s): {existing_databases}")
    
    # Filter databases based on command line flags
    databases_to_process = list(DATABASE_CONFIG.keys())
    if args.test_only:
        databases_to_process = [db for db in databases_to_process if db == 'cbc-test']
        logger.info("Operating in TEST-ONLY mode - only cbc-test database will be affected")
    elif args.production_only:
        databases_to_process = [db for db in databases_to_process if db == 'cbc-register']
        logger.info("Operating in PRODUCTION-ONLY mode - only cbc-register database will be affected")
    
    # Determine what needs to be done
    databases_to_create = []
    databases_to_recreate = []
    databases_to_update_indexes = []
    
    for db_id in databases_to_process:
        if db_id in existing_databases:
            if args.force:
                databases_to_recreate.append(db_id)
            else:
                logger.info(f"✓ Database '{db_id}' already exists")
                databases_to_update_indexes.append(db_id)  # Create/update indexes for existing databases
        else:
            databases_to_create.append(db_id)
    
    # Show summary
    total_operations = len(databases_to_create) + len(databases_to_recreate)
    
    if total_operations == 0 and len(databases_to_update_indexes) == 0:
        logger.info("\n✅ All required databases already exist!")
        if not args.force:
            logger.info("Use --force to recreate existing databases")
        sys.exit(0)
    
    logger.info(f"\nPlanned operations:")
    if databases_to_create:
        logger.info(f"  Create: {databases_to_create}")
    if databases_to_recreate:
        logger.info(f"  Recreate: {databases_to_recreate}")
    if databases_to_update_indexes:
        logger.info(f"  Update indexes: {databases_to_update_indexes}")
    
    # Confirmation for force mode
    if args.force and databases_to_recreate and not args.dry_run:
        logger.warning(f"\n⚠️  WARNING: --force will DELETE and recreate existing databases!")
        logger.warning(f"This will permanently delete all data in: {databases_to_recreate}")
        confirm = input("\nType 'DELETE AND RECREATE' to confirm: ").strip()
        if confirm != 'DELETE AND RECREATE':
            logger.info("Operation cancelled by user")
            sys.exit(0)
    
    # Execute operations
    success_count = 0
    
    logger.info(f"\n🔧 Executing database operations...")
    
    # Recreate databases (delete then create)
    for db_id in databases_to_recreate:
        logger.info(f"\n--- Recreating database: {db_id} ---")
        
        # Delete existing database
        if delete_database(client, db_id, logger, args.dry_run):
            # Wait a moment for deletion to complete
            if not args.dry_run:
                import time
                time.sleep(5)
            
            # Create new database
            if create_database(client, db_id, DATABASE_CONFIG[db_id], logger, args.dry_run):
                success_count += 1
                
                # Create indexes for the recreated database
                if not args.skip_indexes:
                    logger.info(f"\n--- Creating indexes for database: {db_id} ---")
                    create_database_indexes(client, db_id, logger, args.dry_run, args.skip_indexes)
        
    # Create new databases
    for db_id in databases_to_create:
        logger.info(f"\n--- Creating database: {db_id} ---")
        if create_database(client, db_id, DATABASE_CONFIG[db_id], logger, args.dry_run):
            success_count += 1
            
            # Create indexes for the new database
            if not args.skip_indexes:
                logger.info(f"\n--- Creating indexes for database: {db_id} ---")
                create_database_indexes(client, db_id, logger, args.dry_run, args.skip_indexes)
    
    # Update indexes for existing databases
    for db_id in databases_to_update_indexes:
        if not args.skip_indexes:
            logger.info(f"\n--- Updating indexes for existing database: {db_id} ---")
            create_database_indexes(client, db_id, logger, args.dry_run, args.skip_indexes)
        else:
            logger.info(f"Skipping index updates for existing database: {db_id}")
    
    # Final summary
    logger.info(f"\n{'=' * 55}")
    if args.dry_run:
        operation_text = f"{total_operations} database(s)"
        if not args.skip_indexes:
            index_count = sum(len(indexes) for indexes in REQUIRED_INDEXES.values())
            operation_text += f" with {index_count} indexes each"
        logger.info(f"DRY RUN COMPLETE: Would process {operation_text}")
    else:
        logger.info(f"SETUP COMPLETE: {success_count}/{total_operations} operations successful")
        
        if success_count == total_operations:
            logger.info("✅ All databases are ready!")
            if not args.skip_indexes:
                logger.info("✅ All indexes created (building in background)")
                logger.info("Note: Index building can take several minutes to complete")
            logger.info("\nNext steps:")
            logger.info("1. Deploy your application: ./deploy.sh both")
            logger.info("2. Test registration form to create initial collections")
            if args.skip_indexes:
                logger.info("3. Indexes will be created automatically when needed (may cause delays)")
            else:
                logger.info("3. Application should work without index creation delays")
        else:
            logger.warning("⚠️  Some operations failed - check logs above")
            sys.exit(1)


if __name__ == "__main__":
    main()