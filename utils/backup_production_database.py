#!/usr/bin/env python3
"""
Backup production Firestore database to Google Cloud Storage.

This script creates a backup of the production database to the
vancouver-cbc-backup bucket with timestamped naming for easy restoration.

USAGE:
    python backup_production_database.py [OPTIONS]

OPTIONS:
    --bucket BUCKET_NAME    Backup bucket (default: vancouver-cbc-backup)
    --database DATABASE     Override production database name (default: from config)
    --dry-run              Show what would be backed up without executing
    --collections COLS     Comma-separated list of collections to backup (default: all)
    --help                 Show this help message

EXAMPLES:
    # Backup all collections to default bucket
    python backup_production_database.py

    # Dry run to see what would be backed up
    python backup_production_database.py --dry-run

    # Backup specific collections only
    python backup_production_database.py --collections participants_2025,area_leaders_2025

    # Override database name
    python backup_production_database.py --database cbc-register-alt

SECURITY:
    - Reads production database name from config/database.py
    - Requires appropriate IAM permissions for Firestore export and Cloud Storage write
    - Creates timestamped backups for version control
    - Validates bucket existence before starting backup

RESTORE:
    To restore from backup, use gcloud command:
    gcloud firestore import gs://vancouver-cbc-backup/[BACKUP_FOLDER]
"""

import argparse
import os
import sys
from datetime import datetime
from typing import List, Optional
import subprocess
import json

# Add project root to Python path for imports
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

def get_default_bucket_name() -> str:
    """Get the default backup bucket name from organization configuration."""
    try:
        from config.organization import ORGANIZATION_NAME

        # Convert organization name to bucket-friendly format
        # e.g. "Nature Vancouver" -> "nature-vancouver-cbc-backup"
        bucket_name = ORGANIZATION_NAME.lower().replace(' ', '-') + '-cbc-backup'
        print(f"📋 Default backup bucket from config: {bucket_name}")
        return bucket_name

    except ImportError as e:
        print(f"❌ Cannot import organization configuration: {e}")
        print("   Using fallback bucket name: cbc-backup")
        return 'cbc-backup'
    except Exception as e:
        print(f"❌ Error reading organization configuration: {e}")
        print("   Using fallback bucket name: cbc-backup")
        return 'cbc-backup'

def get_production_database() -> str:
    """Get the production database name from configuration."""
    try:
        # Import the database configuration
        from config.database import get_database_config

        # Temporarily set environment to production to get production database
        original_flask_env = os.environ.get('FLASK_ENV')
        original_test_mode = os.environ.get('TEST_MODE')

        # Set production environment variables
        os.environ['FLASK_ENV'] = 'production'
        os.environ['TEST_MODE'] = 'false'

        try:
            # Get production database name
            database_name = get_database_config()
            print(f"📋 Production database from config: {database_name}")
            return database_name
        finally:
            # Restore original environment variables
            if original_flask_env is not None:
                os.environ['FLASK_ENV'] = original_flask_env
            else:
                os.environ.pop('FLASK_ENV', None)

            if original_test_mode is not None:
                os.environ['TEST_MODE'] = original_test_mode
            else:
                os.environ.pop('TEST_MODE', None)

    except ImportError as e:
        print(f"❌ Cannot import database configuration: {e}")
        print("   Make sure you're running from the project root directory")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error reading database configuration: {e}")
        sys.exit(1)

def find_gcloud_executable():
    """Find the gcloud executable on Windows, handling common PATH issues."""
    import shutil

    # First try the standard PATH lookup
    gcloud_path = shutil.which('gcloud')
    if gcloud_path:
        return gcloud_path

    # On Windows, try common Google Cloud SDK installation paths
    import platform
    if platform.system() == 'Windows':
        common_paths = [
            os.path.expanduser('~\\AppData\\Local\\Google\\Cloud SDK\\google-cloud-sdk\\bin\\gcloud.cmd'),
            'C:\\Program Files (x86)\\Google\\Cloud SDK\\google-cloud-sdk\\bin\\gcloud.cmd',
            'C:\\Program Files\\Google\\Cloud SDK\\google-cloud-sdk\\bin\\gcloud.cmd',
            os.path.expanduser('~\\google-cloud-sdk\\bin\\gcloud.cmd'),
        ]

        for path in common_paths:
            if os.path.exists(path):
                return path

    return None

def validate_environment():
    """Validate that we're properly configured for backup operations."""
    print("🔍 Validating environment...")

    # Find gcloud executable
    gcloud_cmd = find_gcloud_executable()
    if not gcloud_cmd:
        print("❌ gcloud CLI not found.")
        print("   Install Google Cloud SDK from: https://cloud.google.com/sdk/docs/install")
        print("   Then run: gcloud auth login")
        return False

    print(f"✅ Found gcloud at: {gcloud_cmd}")

    # Check gcloud is authenticated
    try:
        result = subprocess.run([gcloud_cmd, 'auth', 'list', '--filter=status:ACTIVE', '--format=value(account)'],
                              capture_output=True, text=True, check=True)
        active_account = result.stdout.strip()
        if not active_account:
            print("❌ No active gcloud authentication found.")
            print("   Run: gcloud auth login")
            return False
        print(f"✅ Authenticated as: {active_account}")
    except subprocess.CalledProcessError as e:
        print("❌ gcloud authentication failed.")
        print(f"   Error: {e.stderr if e.stderr else 'Unknown error'}")
        print("   Run: gcloud auth login")
        return False

    # Check project configuration
    try:
        result = subprocess.run([gcloud_cmd, 'config', 'get-value', 'project'],
                              capture_output=True, text=True, check=True)
        project = result.stdout.strip()
        if project != 'vancouver-cbc-registration':
            print(f"❌ Wrong project configured: {project}")
            print("   Run: gcloud config set project vancouver-cbc-registration")
            return False
        print(f"✅ Project configured: {project}")
    except subprocess.CalledProcessError:
        print("❌ No project configured.")
        print("   Run: gcloud config set project vancouver-cbc-registration")
        return False

    return True

def validate_bucket(bucket_name: str) -> bool:
    """Validate that the backup bucket exists and is accessible."""
    print(f"🪣 Validating bucket: {bucket_name}")

    # Find gsutil (should be in same directory as gcloud)
    gcloud_cmd = find_gcloud_executable()
    if gcloud_cmd:
        gsutil_cmd = gcloud_cmd.replace('gcloud.cmd', 'gsutil.cmd').replace('gcloud', 'gsutil')
    else:
        gsutil_cmd = 'gsutil'  # Fallback

    try:
        result = subprocess.run([gsutil_cmd, 'ls', f'gs://{bucket_name}/'],
                              capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ Bucket {bucket_name} is accessible")
            return True
        else:
            print(f"❌ Cannot access bucket {bucket_name}")
            print(f"   Error: {result.stderr.strip()}")
            print()
            print("📝 To create the backup bucket:")
            print(f"   gsutil mb gs://{bucket_name}")
            print(f'   echo \'{{"rule":[{{"action":{{"type":"Delete"}},"condition":{{"age":90}}}}]}}\' > lifecycle.json')
            print(f"   gsutil lifecycle set lifecycle.json gs://{bucket_name}")
            print("   rm lifecycle.json")
            print()
            print("   This will create the bucket and auto-delete backups after 90 days")
            return False
    except FileNotFoundError:
        print("❌ gsutil not found. Install Google Cloud SDK.")
        return False

def get_available_collections(database_name: str) -> List[str]:
    """Get list of collections to backup based on project patterns."""
    print(f"📋 Discovering collections for database: {database_name}")

    # For Firestore, we'll use known patterns from the project
    current_year = datetime.now().year

    # Standard collections based on project structure
    collections = [
        f'participants_{current_year}',
        f'area_leaders_{current_year}',
        f'removal_log_{current_year}'
    ]

    # Add previous year collections (common to have 2-3 years of data)
    for year in range(current_year - 2, current_year):
        collections.extend([
            f'participants_{year}',
            f'area_leaders_{year}',
            f'removal_log_{year}'
        ])

    print(f"📋 Will backup collections: {', '.join(collections)}")
    print("   Note: Empty collections will be skipped automatically")

    return collections

def create_backup(database_name: str, bucket_name: str, collections: Optional[List[str]] = None, dry_run: bool = False) -> bool:
    """Create a Firestore backup to Cloud Storage."""
    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    backup_path = f"gs://{bucket_name}/firestore-backup-{timestamp}"

    print(f"💾 Creating backup...")
    print(f"   Source: {database_name} database")
    print(f"   Target: {backup_path}")

    if collections:
        print(f"   Collections: {', '.join(collections)}")
        collection_args = []
        for collection in collections:
            collection_args.extend(['--collection-ids', collection])
    else:
        print("   Collections: ALL")
        collection_args = []

    if dry_run:
        print("🏃 DRY RUN: Would execute the following command:")
        cmd = [
            'gcloud', 'firestore', 'export',
            backup_path,
            f'--database={database_name}'
        ] + collection_args
        print(f"   {' '.join(cmd)}")
        return True

    # Get gcloud executable
    gcloud_cmd = find_gcloud_executable()
    if not gcloud_cmd:
        print("❌ gcloud not found")
        return False

    try:
        cmd = [
            gcloud_cmd, 'firestore', 'export',
            backup_path,
            f'--database={database_name}'
        ] + collection_args

        print("⏳ Executing backup (this may take several minutes)...")
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)

        print("✅ Backup completed successfully!")
        print(f"   Backup location: {backup_path}")
        print(f"   Operation: {result.stdout.strip()}")

        # Show backup size
        try:
            gsutil_cmd = gcloud_cmd.replace('gcloud.cmd', 'gsutil.cmd').replace('gcloud', 'gsutil')
            size_result = subprocess.run([
                gsutil_cmd, 'du', '-sh', backup_path
            ], capture_output=True, text=True)
            if size_result.returncode == 0:
                size = size_result.stdout.strip().split('\t')[0]
                print(f"   Backup size: {size}")
        except:
            pass  # Size info is nice-to-have but not critical

        return True

    except subprocess.CalledProcessError as e:
        print(f"❌ Backup failed: {e}")
        print(f"   Error output: {e.stderr}")
        return False

def list_recent_backups(bucket_name: str, limit: int = 10):
    """List recent backups in the bucket."""
    print(f"📜 Recent backups in {bucket_name}:")

    # Find gsutil executable
    gcloud_cmd = find_gcloud_executable()
    if gcloud_cmd:
        gsutil_cmd = gcloud_cmd.replace('gcloud.cmd', 'gsutil.cmd').replace('gcloud', 'gsutil')
    else:
        gsutil_cmd = 'gsutil'

    try:
        result = subprocess.run([
            gsutil_cmd, 'ls', '-l', f'gs://{bucket_name}/firestore-backup-*'
        ], capture_output=True, text=True)

        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            backup_lines = [line for line in lines if 'firestore-backup-' in line]

            if backup_lines:
                # Sort by timestamp (newest first) and limit
                backup_lines.sort(reverse=True)
                for line in backup_lines[:limit]:
                    parts = line.split()
                    if len(parts) >= 3:
                        size = parts[0]
                        date = parts[1]
                        time = parts[2]
                        path = parts[-1]
                        backup_name = path.split('/')[-1]
                        print(f"   {backup_name} ({size}, {date} {time})")
            else:
                print("   No firestore backups found")
        else:
            print(f"   Could not list backups: {result.stderr.strip()}")

    except Exception as e:
        print(f"   Error listing backups: {e}")

def main():
    parser = argparse.ArgumentParser(
        description='Backup production Firestore database to Cloud Storage',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                                    # Backup all collections
  %(prog)s --dry-run                          # Show what would be backed up
  %(prog)s --collections participants_2025   # Backup specific collections
  %(prog)s --bucket my-backup-bucket          # Use different bucket
  %(prog)s --database cbc-register-alt        # Override database name

To restore a backup:
  gcloud firestore import gs://vancouver-cbc-backup/firestore-backup-TIMESTAMP --database=DATABASE_NAME
        """
    )

    # Get default bucket name from organization config
    default_bucket = get_default_bucket_name()

    parser.add_argument(
        '--bucket',
        default=default_bucket,
        help=f'Backup bucket name (default: {default_bucket})'
    )

    parser.add_argument(
        '--database',
        help='Override production database name (default: from config/database.py)'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be backed up without executing'
    )

    parser.add_argument(
        '--collections',
        help='Comma-separated list of collections to backup (default: all)'
    )

    parser.add_argument(
        '--list-backups',
        action='store_true',
        help='List recent backups and exit'
    )

    args = parser.parse_args()

    print("🚀 CBC Registration Database Backup Utility")
    print("=" * 50)

    # Get database name from config or command line
    if args.database:
        database_name = args.database
        print(f"📋 Using database from command line: {database_name}")
    else:
        database_name = get_production_database()

    # Validate environment
    if not validate_environment():
        return 1

    # Validate bucket
    if not validate_bucket(args.bucket):
        return 1

    # List backups and exit if requested
    if args.list_backups:
        list_recent_backups(args.bucket)
        return 0

    # Parse collections if specified
    collections = None
    if args.collections:
        collections = [col.strip() for col in args.collections.split(',')]
        print(f"📋 Will backup specific collections: {', '.join(collections)}")
    else:
        # Auto-discover collections based on project patterns
        collections = get_available_collections(database_name)

    # Create backup
    success = create_backup(database_name, args.bucket, collections, args.dry_run)

    if success and not args.dry_run:
        print()
        list_recent_backups(args.bucket, 5)

        print()
        print("📖 Next steps:")
        print("   - Backup is stored with timestamp for easy identification")
        print(f"   - To restore: gcloud firestore import gs://vancouver-cbc-backup/firestore-backup-TIMESTAMP --database={database_name}")
        print("   - Set up automated backups using Cloud Scheduler if needed")

    return 0 if success else 1

if __name__ == '__main__':
    sys.exit(main())