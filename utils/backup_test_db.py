#!/usr/bin/env python3
"""
Simple Test Database Backup Script

This script creates a backup of the test database collections before migration.
"""

import sys
import os
import json
from datetime import datetime
from typing import Dict, List

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.database import get_firestore_client


def backup_collection(db, collection_name: str) -> List[Dict]:
    """Backup a single collection to a list of documents."""
    docs = []
    try:
        collection_ref = db.collection(collection_name)
        for doc in collection_ref.stream():
            doc_data = doc.to_dict()
            doc_data['_doc_id'] = doc.id  # Preserve document ID
            docs.append(doc_data)
        print(f"Backed up {len(docs)} documents from {collection_name}")
        return docs
    except Exception as e:
        print(f"Error backing up {collection_name}: {e}")
        return []


def get_collections_to_backup(db) -> List[str]:
    """Get list of collections to backup (participants and area_leaders for all years)."""
    collections = []
    try:
        all_collections = db.collections()
        for collection in all_collections:
            collection_id = collection.id
            if (collection_id.startswith('participants_') or
                collection_id.startswith('area_leaders_') or
                collection_id.startswith('removal_log_')):
                collections.append(collection_id)
        return sorted(collections)
    except Exception as e:
        print(f"Error listing collections: {e}")
        return []


def main():
    """Main backup function."""
    try:
        # Get database client
        db_client, database_id = get_firestore_client()
        print(f"Connected to database: {database_id}")

        # Get collections to backup
        collections = get_collections_to_backup(db_client)
        if not collections:
            print("No collections found to backup")
            return

        print(f"Found collections to backup: {collections}")

        # Create backup
        backup_data = {}
        total_docs = 0

        for collection_name in collections:
            docs = backup_collection(db_client, collection_name)
            backup_data[collection_name] = docs
            total_docs += len(docs)

        # Save backup to file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"test_db_backup_{timestamp}.json"

        with open(backup_filename, 'w') as f:
            json.dump(backup_data, f, indent=2, default=str)

        print(f"\nBackup completed successfully!")
        print(f"Total documents backed up: {total_docs}")
        print(f"Backup saved to: {backup_filename}")

        # Create a restore script
        restore_script = f"""#!/usr/bin/env python3
# Restore script for backup created on {datetime.now()}

import json
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.database import get_firestore_client

def restore_backup():
    db_client, database_id = get_firestore_client()
    print(f"Restoring to database: {{database_id}}")

    with open('{backup_filename}', 'r') as f:
        backup_data = json.load(f)

    for collection_name, docs in backup_data.items():
        print(f"Restoring {{len(docs)}} documents to {{collection_name}}")

        # Clear existing collection first
        collection_ref = db_client.collection(collection_name)
        for doc in collection_ref.stream():
            doc.reference.delete()

        # Restore documents
        for doc_data in docs:
            doc_id = doc_data.pop('_doc_id')
            collection_ref.document(doc_id).set(doc_data)

    print("Restore completed!")

if __name__ == '__main__':
    restore_backup()
"""

        restore_filename = f"restore_test_db_{timestamp}.py"
        with open(restore_filename, 'w') as f:
            f.write(restore_script)

        print(f"Restore script created: {restore_filename}")
        print(f"\nTo restore backup: python {restore_filename}")

    except Exception as e:
        print(f"Backup failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()