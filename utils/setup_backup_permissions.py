#!/usr/bin/env python3
"""
Setup IAM permissions for Firestore backup system.
This script automates the tricky IAM configuration required for backups.

Usage:
    python utils/setup_backup_permissions.py
"""

import subprocess
import sys
import time


def run_command(cmd, description):
    """Run a command and handle errors."""
    print(f"Running: {description}")
    print(f"Command: {' '.join(cmd)}")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print("✅ Success")
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"❌ Error: {e.stderr}")
        return None


def get_project_info():
    """Get current project ID and number."""
    print("Getting project information...")

    # Get project ID
    project_id = run_command(
        ['gcloud', 'config', 'get-value', 'project'],
        "Getting current project ID"
    )

    if not project_id:
        print("❌ No project set. Run: gcloud config set project YOUR_PROJECT_ID")
        return None, None

    # Get project number
    project_number = run_command(
        ['gcloud', 'projects', 'describe', project_id, '--format', 'value(projectNumber)'],
        f"Getting project number for {project_id}"
    )

    if not project_number:
        print("❌ Could not get project number")
        return project_id, None

    print(f"📋 Project ID: {project_id}")
    print(f"📋 Project Number: {project_number}")

    return project_id, project_number


def setup_service_account_permissions(project_id, project_number):
    """Set up the required IAM permissions for the backup service account."""

    service_account = f"{project_number}-compute@developer.gserviceaccount.com"
    print(f"📋 Service Account: {service_account}")

    permissions = [
        {
            'role': 'roles/datastore.importExportAdmin',
            'description': 'Firestore export/import permissions'
        },
        {
            'role': 'roles/storage.admin',
            'description': 'Cloud Storage admin permissions'
        }
    ]

    print(f"\nGranting permissions to service account...")

    success_count = 0
    for perm in permissions:
        print(f"\n🔑 Granting {perm['description']}...")

        cmd = [
            'gcloud', 'projects', 'add-iam-policy-binding', project_id,
            '--member', f'serviceAccount:{service_account}',
            '--role', perm['role']
        ]

        result = run_command(cmd, f"Grant {perm['role']}")
        if result:
            success_count += 1
        else:
            print(f"❌ Failed to grant {perm['role']}")

    return success_count == len(permissions)


def verify_permissions(project_id, project_number):
    """Verify that permissions were granted correctly."""
    print(f"\n🔍 Verifying permissions...")

    service_account = f"{project_number}-compute@developer.gserviceaccount.com"

    cmd = [
        'gcloud', 'projects', 'get-iam-policy', project_id,
        '--flatten', 'bindings[].members',
        '--format', 'table(bindings.role)',
        '--filter', f'bindings.members:serviceAccount:{service_account}'
    ]

    result = run_command(cmd, "Checking current permissions")

    if result:
        print(f"✅ Current roles for {service_account}:")
        print(result)

        # Check for required roles
        required_roles = ['roles/datastore.importExportAdmin', 'roles/storage.admin']
        missing_roles = []

        for role in required_roles:
            if role not in result:
                missing_roles.append(role)

        if missing_roles:
            print(f"❌ Missing required roles: {missing_roles}")
            return False
        else:
            print("✅ All required permissions are present")
            return True
    else:
        print("❌ Could not verify permissions")
        return False


def enable_required_apis(project_id):
    """Enable the required Google Cloud APIs."""
    print(f"\n🔧 Enabling required APIs...")

    apis = [
        'cloudfunctions.googleapis.com',
        'cloudscheduler.googleapis.com',
        'storage.googleapis.com'
    ]

    for api in apis:
        print(f"\n📡 Enabling {api}...")

        cmd = ['gcloud', 'services', 'enable', api, '--project', project_id]
        result = run_command(cmd, f"Enable {api}")

        if not result:
            print(f"❌ Failed to enable {api}")
            return False

    print("✅ All APIs enabled successfully")
    return True


def main():
    """Main setup function."""
    print("Firestore Backup IAM Permissions Setup")
    print("=" * 50)
    print("This script will configure the IAM permissions required")
    print("for the Firestore backup system to work properly.")
    print("")

    # Get project information
    project_id, project_number = get_project_info()
    if not project_id or not project_number:
        print("❌ Setup failed: Could not get project information")
        sys.exit(1)

    # Enable required APIs
    if not enable_required_apis(project_id):
        print("❌ Setup failed: Could not enable required APIs")
        sys.exit(1)

    # Set up permissions
    if not setup_service_account_permissions(project_id, project_number):
        print("❌ Setup failed: Could not grant all required permissions")
        sys.exit(1)

    # Wait a moment for permissions to propagate
    print("\n⏱️  Waiting 10 seconds for permissions to propagate...")
    time.sleep(10)

    # Verify permissions
    if not verify_permissions(project_id, project_number):
        print("❌ Setup completed but verification failed")
        print("   Permissions may still be propagating. Try testing in a few minutes.")
        sys.exit(1)

    print(f"\n🎉 Setup completed successfully!")
    print(f"✅ Project: {project_id}")
    print(f"✅ Service account: {project_number}-compute@developer.gserviceaccount.com")
    print(f"✅ Required permissions granted")
    print(f"✅ APIs enabled")
    print(f"\nNext step: Deploy the backup system with:")
    print(f"   python utils/deploy_backup_function.py YOUR_BACKUP_BUCKET_NAME")


if __name__ == '__main__':
    main()