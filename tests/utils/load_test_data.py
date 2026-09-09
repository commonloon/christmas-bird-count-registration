#!/usr/bin/env python3
# Created by Claude AI on 2025-10-01
# Updated by Claude AI on 2026-09-08
"""
Load test participant data from CSV fixtures into Postgres.

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

from models.db import Participant, RemovalLog
from models.participant import ParticipantModel, DuplicateParticipantError
from tests.test_config import TEST_CIRCLE_SLUG

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
    bool_fields = ['has_binoculars', 'spotting_scope', 'interested_in_leadership', 'is_leader']
    datetime_fields = ['created_at', 'updated_at', 'assigned_at',
                      'leadership_assigned_at', 'leadership_removed_at']
    int_fields = ['year']

    # Stale columns from the CSV's Firestore-era schema with no matching Postgres
    # column: 'id' (old Firestore doc ID - new int IDs are generated on insert),
    # 'interested_in_scribe' (Scribe field removed entirely), 'auto_assigned'
    # (never became a real column).
    skip_fields = ('id', 'interested_in_scribe', 'auto_assigned')

    participant = {}

    for key, value in row.items():
        if key in skip_fields:
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


def load_participants_to_postgres(db_session,
                                   year: int,
                                   participants: List[Dict],
                                   clear_first: bool = True,
                                   circle_slug: Optional[str] = None) -> int:
    """
    Load participants into Postgres for the specified year/circle.

    Args:
        db_session: SQLAlchemy session (config.database.get_db_session())
        year: Year for the records (e.g., 2025)
        participants: List of participant dictionaries
        clear_first: If True, delete existing rows for this year/circle before loading
        circle_slug: Circle to load into (defaults to TEST_CIRCLE_SLUG, the dedicated
            test circle - there is no app-wide default circle to fall back on)

    Returns:
        Number of participants loaded
    """
    circle_slug = circle_slug or TEST_CIRCLE_SLUG

    if clear_first:
        logger.info(f"Clearing existing {circle_slug} participants/removal_log for year {year}")
        db_session.query(Participant).filter_by(circle_slug=circle_slug, year=year).delete()
        db_session.query(RemovalLog).filter_by(circle_slug=circle_slug, year=year).delete()
        db_session.commit()

    logger.info(f"Loading {len(participants)} participants into {circle_slug} {year}")
    model = ParticipantModel(db_session, year=year, circle_slug=circle_slug)
    loaded_count = 0
    skipped_count = 0
    first_error = None

    for participant in participants:
        # Update year field to match target year
        row = dict(participant)
        row['year'] = year

        try:
            model.add_participant(row)
            loaded_count += 1
        except DuplicateParticipantError as e:
            skipped_count += 1
            logger.warning(f"Skipped duplicate identity for {row.get('email')}: {e}")
        except Exception as e:
            skipped_count += 1
            if first_error is None:
                first_error = e
            logger.error(f"Failed to load participant {row.get('email')}: {e}")

    if loaded_count == 0:
        error_msg = f"Failed to load ANY participants into {circle_slug} {year}!"
        if first_error:
            error_msg += f" First error: {first_error}"
        logger.error(error_msg)
        raise RuntimeError(error_msg)

    if skipped_count > 0:
        logger.warning(f"Loaded {loaded_count} participants but {skipped_count} skipped/failed")
    else:
        logger.info(f"Successfully loaded {loaded_count} participants")

    return loaded_count


def load_test_fixture(db_session,
                     years: List[int],
                     csv_filename: str = 'test_participants_2025.csv',
                     max_count: Optional[int] = None,
                     areas: Optional[List[str]] = None,
                     clear_first: bool = True,
                     circle_slug: Optional[str] = None) -> Dict[int, int]:
    """
    Load test data from CSV fixture into multiple years.

    Args:
        db_session: SQLAlchemy session
        years: List of years to load data into
        csv_filename: Name of CSV file in tests/fixtures/
        max_count: Maximum participants per year (None = all)
        areas: Area codes to include (None = all)
        clear_first: Clear existing rows before loading
        circle_slug: Circle to load into (defaults to TEST_CIRCLE_SLUG - the test
            circle's area codes are a copy of Vancouver's, translated 45km northwest,
            so this fixture's Vancouver-lettered area codes still line up)

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
        count = load_participants_to_postgres(db_session, year, participants, clear_first, circle_slug)
        results[year] = count

    return results


if __name__ == '__main__':
    """Command-line usage for manual testing."""
    import argparse
    from config.database import get_db_session

    parser = argparse.ArgumentParser(description='Load test participant data into Postgres')
    parser.add_argument('--years', type=int, nargs='+', default=[datetime.now().year],
                       help='Years to load data into (default: current year)')
    parser.add_argument('--max-count', type=int, default=None,
                       help='Maximum participants to load (default: all)')
    parser.add_argument('--areas', type=str, nargs='+', default=None,
                       help='Area codes to include (default: all)')
    parser.add_argument('--no-clear', action='store_true',
                       help='Do not clear existing rows before loading')
    parser.add_argument('--csv', type=str, default='test_participants_2025.csv',
                       help='CSV filename in tests/fixtures/')
    parser.add_argument('--circle', type=str, default=None,
                       help='Circle slug to load into (default: the test circle)')

    args = parser.parse_args()

    # Set up logging
    logging.basicConfig(level=logging.INFO,
                       format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Get a Postgres session
    try:
        session = get_db_session()
    except Exception as e:
        logger.error(f"Failed to connect to Postgres: {e}")
        sys.exit(1)

    # Load test data
    try:
        results = load_test_fixture(
            session,
            years=args.years,
            csv_filename=args.csv,
            max_count=args.max_count,
            areas=args.areas,
            clear_first=not args.no_clear,
            circle_slug=args.circle
        )

        print("\n=== Load Results ===")
        for year, count in results.items():
            print(f"Year {year}: {count} participants loaded")

    except Exception as e:
        logger.error(f"Failed to load test data: {e}")
        sys.exit(1)
