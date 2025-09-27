#!/usr/bin/env python3
"""
Firestore backup utility with change detection.
Checks for database changes and creates backups only when needed.

Usage:
    python backup_firestore.py [--dry-run] [--force]

Options:
    --dry-run   Show what would be backed up without creating backup
    --force     Create backup regardless of change detection
"""

import os
import sys
import json
import argparse
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to Python path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from google.cloud import firestore
from google.cloud import storage
import google.cloud.firestore_admin_v1 as firestore_admin


def main():
    parser = argparse.ArgumentParser(description='Backup Firestore database with change detection')
    parser.add_argument('--bucket', help='Cloud Storage bucket name (default: vancouver-cbc-backups)')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be backed up')
    parser.add_argument('--force', action='store_true', help='Force backup regardless of changes')
    args = parser.parse_args()

    try:
        backup_manager = FirestoreBackupManager(bucket_name=args.bucket)

        print(f"Database: {backup_manager.database_id}")
        print(f"Project: {backup_manager.project_id}")
        print(f"Bucket: {backup_manager.bucket_name}")
        print()

        if args.force:
            print("Force backup requested - skipping change detection")
            result = backup_manager.create_backup(dry_run=args.dry_run)
        else:
            result = backup_manager.backup_if_changed(dry_run=args.dry_run)

        print(f"Result: {result}")

    except Exception as e:
        print(f"Backup failed: {e}")
        sys.exit(1)


class FirestoreBackupManager:
    """Manages Firestore backups with change detection."""

    def __init__(self, bucket_name=None):
        # Get configuration from local sources
        from config.database import get_database_config

        self.database_id = get_database_config()
        self.bucket_name = bucket_name or f'vancouver-cbc-backups'
        self.metadata_file = 'backup_metadata.json'

        # Get project ID from gcloud
        try:
            self.project_id = self._run_gcloud_command(['config', 'get-value', 'project'])
            if not self.project_id:
                raise Exception("No default project set. Run 'gcloud config set project PROJECT_ID' first.")
        except Exception as e:
            raise Exception(f"Could not get project ID from gcloud: {e}")

        # Initialize clients
        self.db = firestore.Client(database=self.database_id)
        self.storage_client = storage.Client()
        self.admin_client = firestore_admin.FirestoreAdminClient()

        # Ensure bucket exists
        self._ensure_bucket_exists()


    def _run_gcloud_command(self, args):
        """Run a gcloud command with proper error handling."""
        import subprocess
        import shutil

        gcloud_path = shutil.which('gcloud')
        if not gcloud_path:
            raise Exception("Could not find gcloud command in PATH. Please install Google Cloud SDK.")

        cmd = [gcloud_path] + args

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            raise Exception(f"gcloud command failed: {e.stderr}")
        except FileNotFoundError:
            raise Exception(f"Could not execute gcloud command: {' '.join(cmd)}")

    def backup_if_changed(self, dry_run=False):
        """Create backup only if database changed since last backup."""
        last_backup = self._get_last_backup_timestamp()

        if not self._database_changed_since(last_backup):
            return "No changes detected since last backup - skipping"

        return self.create_backup(dry_run)

    def create_backup(self, dry_run=False):
        """Create a new Firestore backup."""
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        backup_name = f"cbc_backup_{timestamp}"

        if dry_run:
            return f"DRY RUN: Would create backup '{backup_name}'"

        # Create backup using Admin API
        database_path = self.admin_client.database_path(
            self.project_id,
            self.database_id
        )
        output_uri = f'gs://{self.bucket_name}/{backup_name}'

        print(f"Starting backup: {backup_name}")
        print(f"Output location: {output_uri}")

        operation = self.admin_client.export_documents(
            request={
                'name': database_path,
                'output_uri_prefix': output_uri,
                'collection_ids': []  # Empty = all collections
            }
        )

        print(f"Backup operation started: {operation.name}")

        # Update metadata
        self._update_backup_metadata(backup_name, timestamp)

        return f"Backup created: {backup_name}"

    def _database_changed_since(self, timestamp):
        """Check if any critical collections changed since timestamp."""
        if not timestamp:
            return True  # No previous backup

        current_year = datetime.now().year
        collections_to_check = [
            f'participants_{current_year}',
            f'area_leaders_{current_year}',
            f'removal_log_{current_year}',
            # Check previous year too during transition periods
            f'participants_{current_year - 1}',
            f'area_leaders_{current_year - 1}'
        ]

        for collection_name in collections_to_check:
            if self._collection_changed_since(collection_name, timestamp):
                print(f"Changes detected in collection: {collection_name}")
                return True

        return False

    def _collection_changed_since(self, collection_name, timestamp):
        """Check if specific collection changed since timestamp."""
        try:
            # Look for documents with updated_at > timestamp
            query = (self.db.collection(collection_name)
                    .where('updated_at', '>', timestamp)
                    .limit(1))

            docs = list(query.stream())
            return len(docs) > 0

        except Exception as e:
            print(f"Warning: Could not check collection {collection_name}: {e}")
            return True  # Assume changed if can't check

    def _get_last_backup_timestamp(self):
        """Get timestamp of last backup from metadata."""
        try:
            bucket = self.storage_client.bucket(self.bucket_name)
            blob = bucket.blob(self.metadata_file)

            if not blob.exists():
                return None

            metadata = json.loads(blob.download_as_text())
            last_backup_str = metadata.get('last_backup_timestamp')

            if last_backup_str:
                return datetime.fromisoformat(last_backup_str)

        except Exception as e:
            print(f"Warning: Could not read backup metadata: {e}")

        return None

    def _update_backup_metadata(self, backup_name, timestamp_str):
        """Update backup metadata in Cloud Storage."""
        try:
            metadata = {
                'last_backup_name': backup_name,
                'last_backup_timestamp': datetime.utcnow().isoformat(),
                'created_at': timestamp_str
            }

            bucket = self.storage_client.bucket(self.bucket_name)
            blob = bucket.blob(self.metadata_file)
            blob.upload_from_string(json.dumps(metadata, indent=2))

        except Exception as e:
            print(f"Warning: Could not update backup metadata: {e}")

    def _ensure_bucket_exists(self):
        """Ensure backup bucket exists."""
        try:
            bucket = self.storage_client.bucket(self.bucket_name)
            if not bucket.exists():
                bucket = self.storage_client.create_bucket(self.bucket_name)
                print(f"Created backup bucket: {self.bucket_name}")
        except Exception as e:
            print(f"Warning: Could not verify/create bucket: {e}")


if __name__ == '__main__':
    main()