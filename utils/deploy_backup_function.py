"""
Deploy Cloud Function for automated Firestore backups.
This creates a serverless solution that runs hourly via Cloud Scheduler.

Usage:
    python deploy_backup_function.py <bucket_name>

Example:
    python deploy_backup_function.py vancouver-cbc-backups
"""

import os
import sys
import tempfile
import subprocess
import argparse
from pathlib import Path

# Add project root to Python path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config.database import get_database_config

def find_gcloud_command():
    """Find the gcloud command on Windows and other platforms."""
    import shutil

    # Try different possible gcloud command names (case insensitive for Windows)
    possible_commands = ['gcloud', 'gcloud.cmd', 'gcloud.CMD', 'gcloud.exe']

    for cmd in possible_commands:
        if shutil.which(cmd):
            return cmd

    # Check common Windows installation paths
    import os
    windows_paths = [
        r'C:\Program Files (x86)\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd',
        r'C:\Program Files\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd',
        r'C:\Users\%USERNAME%\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd'
    ]

    for path in windows_paths:
        expanded_path = os.path.expandvars(path)
        if os.path.exists(expanded_path):
            return expanded_path

    raise Exception(
        "Could not find gcloud command. Please ensure Google Cloud SDK is installed and in PATH.\n"
        "Download from: https://cloud.google.com/sdk/docs/install\n"
        "Or add the Google Cloud SDK bin directory to your PATH environment variable."
    )


def run_gcloud_command(args):
    """Run a gcloud command with proper error handling."""
    # Use shutil.which directly - it returns the full path including extension
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


def get_deployment_config(bucket_name):
    """Get deployment configuration from local sources."""
    config = {}

    # Get database name from config
    config['database_id'] = get_database_config()

    # Get project ID from gcloud
    try:
        config['project_id'] = run_gcloud_command(['config', 'get-value', 'project'])
        if not config['project_id']:
            raise Exception("No default project set. Run 'gcloud config set project PROJECT_ID' first.")
    except Exception as e:
        raise Exception(f"Could not get project ID from gcloud: {e}")

    # Set other deployment parameters
    config['bucket_name'] = bucket_name
    config['region'] = 'us-west1'  # Consistent with deploy.sh
    config['function_name'] = 'backup-firestore-hourly'
    config['scheduler_job_name'] = 'backup-firestore-hourly'
    config['timezone'] = 'America/Vancouver'  # Default from deploy.sh

    return config


def create_function_source(config):
    """Create Cloud Function source code with config values."""
    template = '''
import os
import json
from datetime import datetime, timedelta
from google.cloud import firestore
from google.cloud import storage
from google.cloud.firestore_admin_v1 import FirestoreAdminClient


def backup_firestore_hourly(request):
    """Cloud Function entry point for hourly Firestore backups."""
    try:
        backup_manager = FirestoreBackupManager()
        result = backup_manager.backup_if_changed()

        return {{'status': 'success',
            'message': result,
            'timestamp': datetime.utcnow().isoformat()
        }}

    except Exception as e:
        print(f"Backup function error: {{e}}")
        return {{'status': 'error',
            'message': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }}, 500


class FirestoreBackupManager:
    """Manages Firestore backups with change detection."""

    def __init__(self):
        self.database_id = '{database_id}'
        self.bucket_name = '{bucket_name}'
        self.project_id = '{project_id}'
        self.metadata_file = 'backup_metadata.json'

        self.db = firestore.Client(database=self.database_id)
        self.storage_client = storage.Client()
        self.admin_client = FirestoreAdminClient()

    def backup_if_changed(self):
        """Create backup only if database changed since last backup."""
        last_backup = self._get_last_backup_timestamp()

        if not self._database_changed_since(last_backup):
            return "No changes detected since last backup - skipping"

        return self._create_backup()

    def _create_backup(self):
        """Create a new Firestore backup."""
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        backup_name = f"cbc_backup_{{timestamp}}"

        database_path = self.admin_client.database_path(
            self.project_id,
            self.database_id
        )
        output_uri = f'gs://{{self.bucket_name}}/{{backup_name}}'

        print(f"Creating backup: {{backup_name}}")

        operation = self.admin_client.export_documents(
            request={{'name': database_path,
                'output_uri_prefix': output_uri,
                'collection_ids': []
            }}
        )

        self._update_backup_metadata(backup_name)

        # Clean up old backups (keep most recent, delete others >60 days)
        self._cleanup_old_backups()

        return f"Backup created: {{backup_name}}"

    def _database_changed_since(self, timestamp):
        """Check if any critical collections changed since timestamp."""
        if not timestamp:
            return True

        current_year = datetime.now().year
        collections = [
            f'participants_{{current_year}}',
            f'area_leaders_{{current_year}}',
            f'removal_log_{{current_year}}'
        ]

        for collection_name in collections:
            try:
                query = (self.db.collection(collection_name)
                        .where('updated_at', '>', timestamp)
                        .limit(1))
                if len(list(query.stream())) > 0:
                    print(f"Changes detected in: {{collection_name}}")
                    return True
            except Exception as e:
                print(f"Warning checking {{collection_name}}: {{e}}")
                return True

        return False

    def _get_last_backup_timestamp(self):
        """Get timestamp of last backup."""
        try:
            bucket = self.storage_client.bucket(self.bucket_name)
            blob = bucket.blob(self.metadata_file)

            if blob.exists():
                metadata = json.loads(blob.download_as_text())
                timestamp_str = metadata.get('last_backup_timestamp')
                if timestamp_str:
                    return datetime.fromisoformat(timestamp_str)
        except Exception as e:
            print(f"Could not read backup metadata: {{e}}")

        return None

    def _update_backup_metadata(self, backup_name):
        """Update backup metadata."""
        try:
            metadata = {{'last_backup_name': backup_name,
                'last_backup_timestamp': datetime.utcnow().isoformat()
            }}

            bucket = self.storage_client.bucket(self.bucket_name)
            blob = bucket.blob(self.metadata_file)
            blob.upload_from_string(json.dumps(metadata))

        except Exception as e:
            print(f"Could not update metadata: {{e}}")

    def _cleanup_old_backups(self):
        """Delete backups older than 60 days, but always keep the most recent."""
        try:
            bucket = self.storage_client.bucket(self.bucket_name)
            backups = []

            # Find all backup directories (they end with a slash when listed)
            for blob in bucket.list_blobs(prefix="cbc_backup_", delimiter='/'):
                if blob.name.endswith('/'):  # It's a backup directory
                    # Extract timestamp from backup name: cbc_backup_YYYYMMDD_HHMMSS/
                    backup_name = blob.name.rstrip('/')
                    try:
                        # Parse timestamp from backup name
                        timestamp_str = backup_name.split('_', 2)[2]  # Get YYYYMMDD_HHMMSS part
                        backup_time = datetime.strptime(timestamp_str, '%Y%m%d_%H%M%S')

                        backups.append({{
                            'name': backup_name,
                            'timestamp': backup_time,
                            'age_days': (datetime.utcnow() - backup_time).days
                        }})
                    except (ValueError, IndexError):
                        # Skip malformed backup names
                        continue

            if not backups:
                print("No backups found for cleanup")
                return

            # Sort by timestamp (newest first)
            backups.sort(key=lambda x: x['timestamp'], reverse=True)

            # Always keep the most recent backup (index 0)
            # Delete others that are older than 60 days
            deleted_count = 0
            for i, backup in enumerate(backups):
                if i == 0:
                    print(f"Preserving most recent backup: {{backup['name']}} ({{backup['age_days']}} days old)")
                    continue

                if backup['age_days'] > 60:
                    print(f"Deleting old backup: {{backup['name']}} ({{backup['age_days']}} days old)")
                    self._delete_backup_directory(backup['name'])
                    deleted_count += 1
                else:
                    print(f"Keeping recent backup: {{backup['name']}} ({{backup['age_days']}} days old)")

            if deleted_count > 0:
                print(f"Cleanup completed: deleted {{deleted_count}} old backups")
            else:
                print("Cleanup completed: no old backups to delete")

        except Exception as e:
            print(f"Error during backup cleanup: {{e}}")

    def _delete_backup_directory(self, backup_name):
        """Delete all files in a backup directory."""
        try:
            bucket = self.storage_client.bucket(self.bucket_name)

            # List all objects with this backup prefix
            backup_prefix = f"{{backup_name}}/"
            blobs_to_delete = list(bucket.list_blobs(prefix=backup_prefix))

            # Delete all objects in the backup directory
            for blob in blobs_to_delete:
                blob.delete()

            print(f"  Deleted {{len(blobs_to_delete)}} files from {{backup_name}}")

        except Exception as e:
            print(f"Error deleting backup directory {{backup_name}}: {{e}}")
'''

    return template.format(**config)


REQUIREMENTS_TXT = '''
google-cloud-firestore>=2.11.0
google-cloud-storage>=2.10.0
'''


def deploy_cloud_function(config):
    """Deploy the backup Cloud Function."""

    print(f"Deploying Cloud Function for automated Firestore backups...")
    print(f"Database: {config['database_id']}")
    print(f"Project: {config['project_id']}")
    print(f"Bucket: {config['bucket_name']}")

    # Create temporary directory
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Write function files with config values
        (temp_path / 'main.py').write_text(create_function_source(config))
        (temp_path / 'requirements.txt').write_text(REQUIREMENTS_TXT)

        # Deploy function
        deploy_args = [
            'functions', 'deploy', config['function_name'],
            '--runtime', 'python39',
            '--trigger-http',
            '--allow-unauthenticated',
            '--timeout', '540s',
            '--memory', '256MB',
            '--region', config['region'],
            '--source', str(temp_path),
            '--entry-point', 'backup_firestore_hourly'
        ]

        print("Running deployment command...")
        import shutil
        gcloud_path = shutil.which('gcloud')
        if not gcloud_path:
            raise Exception("Could not find gcloud command in PATH. Please install Google Cloud SDK.")

        cmd = [gcloud_path] + deploy_args
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            print("[OK] Cloud Function deployed successfully!")
            print(result.stdout)

            # Get function URL (try Gen 2 format first, then Gen 1)
            try:
                # Try Gen 2 format first
                function_url = run_gcloud_command([
                    'functions', 'describe', config['function_name'],
                    '--region', config['region'],
                    '--format', 'value(url)'
                ])

                # If empty, try Gen 1 format
                if not function_url:
                    function_url = run_gcloud_command([
                        'functions', 'describe', config['function_name'],
                        '--region', config['region'],
                        '--format', 'value(httpsTrigger.url)'
                    ])

                if function_url:
                    print(f"Function URL: {function_url}")
                    # Set up Cloud Scheduler
                    setup_scheduler(config, function_url)
                else:
                    print("Warning: Could not extract function URL")
                    print("You may need to set up Cloud Scheduler manually.")
            except Exception as e:
                print(f"Warning: Could not get function URL: {e}")
                print("You may need to set up Cloud Scheduler manually.")

        else:
            print("[ERROR] Cloud Function deployment failed:")
            print(result.stderr)
            return False

    return True


def setup_scheduler(config, function_url):
    """Set up Cloud Scheduler to trigger the function hourly."""

    print("Setting up Cloud Scheduler for hourly backups...")

    scheduler_args = [
        'scheduler', 'jobs', 'create', 'http', config['scheduler_job_name'],
        '--schedule', '0 * * * *',  # Every hour
        '--uri', function_url,
        '--http-method', 'GET',
        '--description', 'Hourly Firestore backup with change detection',
        '--time-zone', config['timezone'],
        '--location', config['region']
    ]

    import shutil
    gcloud_path = shutil.which('gcloud')
    if not gcloud_path:
        raise Exception("Could not find gcloud command in PATH. Please install Google Cloud SDK.")

    cmd = [gcloud_path] + scheduler_args
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0:
        print("[OK] Cloud Scheduler job created successfully!")
        print("Hourly backups are now automated.")
    else:
        if "already exists" in result.stderr:
            print("[INFO] Cloud Scheduler job already exists")
        else:
            print("[ERROR] Cloud Scheduler setup failed:")
            print(result.stderr)


def main():
    """Main function with argument parsing."""
    parser = argparse.ArgumentParser(
        description='Deploy Cloud Function for automated Firestore backups',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python deploy_backup_function.py vancouver-cbc-backups
    python deploy_backup_function.py my-project-firestore-backups
        """)

    parser.add_argument('bucket_name',
                       help='Cloud Storage bucket name for storing backups')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show configuration without deploying')

    args = parser.parse_args()

    try:
        # Get configuration from local sources
        config = get_deployment_config(args.bucket_name)

        print("Deployment Configuration:")
        print("=" * 40)
        for key, value in config.items():
            print(f"{key:15}: {value}")
        print()

        if args.dry_run:
            print("DRY RUN: Configuration validated, no deployment performed.")
            return

        # Deploy the backup system
        success = deploy_cloud_function(config)

        if success:
            print("\n[SUCCESS] Backup system deployed successfully!")
            print(f"Backups will be stored in: gs://{config['bucket_name']}")
            print("The system will check for changes every hour and backup when needed.")
        else:
            print("\n[ERROR] Deployment failed. Check the error messages above.")

    except Exception as e:
        print(f"[ERROR] Deployment failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()