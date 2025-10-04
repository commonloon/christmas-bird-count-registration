#!/usr/bin/env python3
# Created by Claude AI on 2025-10-01
"""
Load test participant data from CSV fixtures into Firestore.

This module provides utilities to populate test databases with realistic participant
data for testing purposes. Data is loaded from CSV files in tests/fixtures/.
"""

import csv
import os
import sys
from datetime import datetime
from typing import List, Dict, Optional
import logging

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
sys.path.insert(0, project_root)

from google.cloud import firestore
from models.participant import ParticipantModel

logger = logging.getLogger(__name__)


def parse_csv_value(value: str, field_type: str):
    """Parse CSV string value to appropriate Python type."""
    if value == '' or value is None:
        return None

    if field_type == 'bool':
        return value.lower() in ('yes', 'true', '1')
    elif field_type == 'int':
        return int(value)
    elif field_type == 'datetime':
        # Parse datetime from CSV format: "2025-10-01 19:06"
        try:
            return datetime.strptime(value, '%Y-%m-%d %H:%M')
        except ValueError:
            return None
    else:  # str
        return value


def csv_row_to_participant(row: Dict[str, str]) -> Dict:
    """Convert CSV row to participant dictionary with proper types."""
    # Field type mappings
    bool_fields = ['has_binoculars', 'spotting_scope', 'interested_in_leadership',
                   'interested_in_scribe', 'is_leader', 'auto_assigned']
    datetime_fields = ['created_at', 'updated_at', 'assigned_at',
                      'leadership_assigned_at', 'leadership_removed_at']
    int_fields = ['year']

    participant = {}

    for key, value in row.items():
        if key == 'id':
            # Skip the original Firestore ID - new ones will be generated
            continue
        elif key in bool_fields:
            participant[key] = parse_csv_value(value, 'bool')
        elif key in datetime_fields:
            participant[key] = parse_csv_value(value, 'datetime')
        elif key in int_fields:
            participant[key] = parse_csv_value(value, 'int')
        else:
            # String fields - keep as-is (None if empty)
            participant[key] = value if value else None

    return participant


def load_csv_participants(csv_path: str,
                         max_count: Optional[int] = None,
                         areas: Optional[List[str]] = None) -> List[Dict]:
    """
    Load participants from CSV file.

    Args:
        csv_path: Path to CSV file
        max_count: Maximum number of participants to load (None = all)
        areas: List of area codes to include (None = all areas)

    Returns:
        List of participant dictionaries
    """
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    participants = []

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)

        for row in reader:
            # Apply area filter if specified
            if areas and row.get('preferred_area') not in areas:
                continue

            participant = csv_row_to_participant(row)
            participants.append(participant)

            # Apply count limit if specified
            if max_count and len(participants) >= max_count:
                break

    logger.info(f"Loaded {len(participants)} participants from CSV")
    return participants


def load_participants_to_firestore(db_client,
                                   year: int,
                                   participants: List[Dict],
                                   clear_first: bool = True) -> int:
    """
    Load participants into Firestore collection for specified year.

    Args:
        db_client: Firestore client
        year: Year for the collection (e.g., 2025)
        participants: List of participant dictionaries
        clear_first: If True, clear collection before loading

    Returns:
        Number of participants loaded
    """
    collection_name = f'participants_{year}'

    # Clear collection if requested
    if clear_first:
        logger.info(f"Clearing collection: {collection_name}")
        collection_ref = db_client.collection(collection_name)
        batch = db_client.batch()
        docs = collection_ref.limit(500).stream()

        count = 0
        for doc in docs:
            batch.delete(doc.reference)
            count += 1
            if count % 500 == 0:
                batch.commit()
                batch = db_client.batch()

        if count % 500 != 0:
            batch.commit()

        logger.info(f"Deleted {count} existing documents")

    # Load participants
    logger.info(f"Loading {len(participants)} participants into {collection_name}")
    collection_ref = db_client.collection(collection_name)
    loaded_count = 0

    for participant in participants:
        # Update year field to match target collection
        participant['year'] = year

        # Add to Firestore
        try:
            collection_ref.add(participant)
            loaded_count += 1
        except Exception as e:
            logger.error(f"Failed to load participant {participant.get('email')}: {e}")

    logger.info(f"Successfully loaded {loaded_count} participants")
    return loaded_count


def load_test_fixture(db_client,
                     years: List[int],
                     csv_filename: str = 'test_participants_2025.csv',
                     max_count: Optional[int] = None,
                     areas: Optional[List[str]] = None,
                     clear_first: bool = True) -> Dict[int, int]:
    """
    Load test data from CSV fixture into multiple years.

    Args:
        db_client: Firestore client
        years: List of years to load data into
        csv_filename: Name of CSV file in tests/fixtures/
        max_count: Maximum participants per year (None = all)
        areas: Area codes to include (None = all)
        clear_first: Clear collections before loading

    Returns:
        Dictionary mapping year to count of participants loaded
    """
    # Find CSV file
    fixtures_dir = os.path.join(project_root, 'tests', 'fixtures')
    csv_path = os.path.join(fixtures_dir, csv_filename)

    # Load participants from CSV
    participants = load_csv_participants(csv_path, max_count, areas)

    # Load into each year
    results = {}
    for year in years:
        count = load_participants_to_firestore(db_client, year, participants, clear_first)
        results[year] = count

    return results


if __name__ == '__main__':
    """Command-line usage for manual testing."""
    import argparse
    from config.database import get_firestore_client

    parser = argparse.ArgumentParser(description='Load test participant data into Firestore')
    parser.add_argument('--years', type=int, nargs='+', default=[2025],
                       help='Years to load data into (default: 2025)')
    parser.add_argument('--max-count', type=int, default=None,
                       help='Maximum participants to load (default: all)')
    parser.add_argument('--areas', type=str, nargs='+', default=None,
                       help='Area codes to include (default: all)')
    parser.add_argument('--no-clear', action='store_true',
                       help='Do not clear collections before loading')
    parser.add_argument('--csv', type=str, default='test_participants_2025.csv',
                       help='CSV filename in tests/fixtures/')

    args = parser.parse_args()

    # Set up logging
    logging.basicConfig(level=logging.INFO,
                       format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Get Firestore client
    try:
        db, database_name = get_firestore_client()
        logger.info(f"Connected to database: {database_name}")
    except Exception as e:
        logger.error(f"Failed to connect to Firestore: {e}")
        sys.exit(1)

    # Load test data
    try:
        results = load_test_fixture(
            db,
            years=args.years,
            csv_filename=args.csv,
            max_count=args.max_count,
            areas=args.areas,
            clear_first=not args.no_clear
        )

        print("\n=== Load Results ===")
        for year, count in results.items():
            print(f"Year {year}: {count} participants loaded")

    except Exception as e:
        logger.error(f"Failed to load test data: {e}")
        sys.exit(1)
