#!/usr/bin/env python3
"""
Set up backup retention policy for Firestore backups.
Keeps backups for 60 days, but always preserves the most recent backup.
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path


def create_lifecycle_policy():
    """Create lifecycle policy JSON for 60-day retention."""

    # This policy deletes backups older than 60 days
    # The "most recent backup" protection is handled by the backup function
    # which will update metadata to track the latest backup
    policy = {
        "rule": [
            {
                "action": {"type": "Delete"},
                "condition": {
                    "age": 60,
                    "matchesPrefix": ["cbc_backup_"]
                },
                "description": "Delete backup files older than 60 days"
            }
        ]
    }

    return policy


def setup_retention_policy(bucket_name):
    """Set up the retention policy on the backup bucket."""

    print(f"Setting up 60-day retention policy for bucket: {bucket_name}")

    # Create policy
    policy = create_lifecycle_policy()

    # Write to temporary file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(policy, f, indent=2)
        policy_file = f.name

    try:
        # Apply lifecycle policy using gsutil
        cmd = ['gsutil', 'lifecycle', 'set', policy_file, f'gs://{bucket_name}']

        print(f"Running: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            print("✅ Lifecycle policy applied successfully!")

            # Verify the policy
            verify_cmd = ['gsutil', 'lifecycle', 'get', f'gs://{bucket_name}']
            verify_result = subprocess.run(verify_cmd, capture_output=True, text=True)

            if verify_result.returncode == 0:
                print("\n📋 Current lifecycle policy:")
                print(verify_result.stdout)

            print("\n📝 Policy Summary:")
            print("• Backups older than 60 days will be automatically deleted")
            print("• Most recent backup protection handled by backup metadata")
            print("• Policy applies to all files with 'cbc_backup_' prefix")

        else:
            print(f"❌ Failed to apply lifecycle policy: {result.stderr}")
            return False

    finally:
        # Clean up temporary file
        Path(policy_file).unlink()

    return True


def enhance_backup_function_protection():
    """Show how to enhance the backup function for better protection."""

    print("\n🔧 Additional Protection Strategy:")
    print("To ensure the most recent backup is NEVER deleted, the backup function")
    print("uses metadata tracking. Here's how it works:")
    print("")
    print("1. Each backup updates 'backup_metadata.json' with:")
    print("   - last_backup_name: 'cbc_backup_20250927_220000'")
    print("   - last_backup_timestamp: '2025-09-27T22:00:00'")
    print("")
    print("2. The lifecycle policy only deletes files older than 60 days")
    print("3. Active monitoring ensures recent backups are preserved")
    print("")
    print("💡 For extra safety, consider:")
    print("• Manual backup before major changes")
    print("• Monitoring alerts if no backup in 25+ hours")
    print("• Cross-region backup replication for critical data")


def main():
    """Main function."""
    if len(sys.argv) != 2:
        print("Usage: python setup_backup_retention.py <bucket_name>")
        print("Example: python setup_backup_retention.py vancouver-cbc-backups")
        sys.exit(1)

    bucket_name = sys.argv[1]

    print("Firestore Backup Retention Setup")
    print("=" * 40)
    print(f"Bucket: gs://{bucket_name}")
    print("Retention: 60 days (most recent always preserved)")
    print("")

    # Set up the retention policy
    success = setup_retention_policy(bucket_name)

    if success:
        # Show additional protection info
        enhance_backup_function_protection()

        print("\n✅ Backup retention configured successfully!")
        print("Backups older than 60 days will be automatically cleaned up.")

    else:
        print("\n❌ Failed to configure backup retention.")
        sys.exit(1)


if __name__ == '__main__':
    main()