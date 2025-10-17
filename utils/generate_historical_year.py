#!/usr/bin/env python3
# Created by Claude AI on 2025-10-16
"""
Generate historical year data for demo/testing purposes.

Creates a "completed" count year with:
- At least one leader per area
- Multiple participants per area
- No unassigned participants
- Realistic distribution across areas

Usage:
    python generate_historical_year.py --year 2024
    python generate_historical_year.py --year 2024 --participants-per-area 3-7
    python generate_historical_year.py --year 2024 --min-participants 2 --max-participants 8
"""

import argparse
import random
import sys
import os
from datetime import datetime, timedelta
from typing import Dict, List

# Add parent directory to path to import config modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from faker import Faker
from config.database import get_firestore_client
from config.areas import get_public_areas
from config.organization import get_organization_variables

# Initialize faker for realistic names
fake = Faker()

# Valid form values
SKILL_LEVELS = ["Newbie", "Beginner", "Intermediate", "Expert"]
EXPERIENCE_LEVELS = ["None", "1-2 counts", "3+ counts"]
PARTICIPATION_TYPES = ["regular", "FEEDER"]

# Get organization email domain
org_vars = get_organization_variables()
EMAIL_DOMAIN = org_vars['count_contact'].split('@')[1]

# Canadian area codes for realistic phone numbers
AREA_CODES = ["604", "778", "236"]


def generate_phone_number():
    """Generate a realistic Canadian phone number."""
    area_code = random.choice(AREA_CODES)
    exchange = random.randint(200, 999)
    number = random.randint(1000, 9999)
    return f"({area_code}) {exchange}-{number}"


def generate_participant(area_code: str, year: int, is_leader: bool = False,
                        participant_num: int = 1) -> Dict:
    """Generate a realistic participant record."""
    first_name = fake.first_name()
    last_name = fake.last_name()

    # Create email with year and area to ensure uniqueness
    email = f"cbc{year}-{area_code.lower()}-{participant_num:02d}@{EMAIL_DOMAIN}"

    # 20% FEEDER participants, but leaders must be regular
    if is_leader:
        participation_type = 'regular'
    else:
        participation_type = random.choice(PARTICIPATION_TYPES)

    # Generate random dates from the count year (typically mid-December)
    # For 2024, use dates in December 2023 (registration) to January 2024 (after count)
    registration_date = datetime(year - 1, 12, random.randint(1, 20))
    updated_date = registration_date + timedelta(days=random.randint(0, 30))

    participant = {
        'first_name': first_name,
        'last_name': last_name,
        'email': email,
        'phone': generate_phone_number(),
        'phone2': generate_phone_number() if random.random() < 0.3 else None,  # 30% have secondary phone
        'skill_level': random.choice(SKILL_LEVELS),
        'experience': random.choice(EXPERIENCE_LEVELS),
        'preferred_area': area_code,
        'participation_type': participation_type,
        'has_binoculars': random.random() < 0.7,  # 70% have binoculars
        'spotting_scope': random.random() < 0.3,  # 30% have spotting scope
        'interested_in_leadership': is_leader or (random.random() < 0.1),  # Leaders + 10% others
        'interested_in_scribe': random.random() < 0.1 if participation_type == 'regular' else False,
        'notes_to_organizers': generate_notes() if random.random() < 0.3 else '',
        'is_leader': is_leader,
        'assigned_area_leader': area_code if is_leader else None,
        'leadership_assigned_by': 'admin@example.com' if is_leader else None,
        'leadership_assigned_at': registration_date if is_leader else None,
        'leadership_removed_by': None,
        'leadership_removed_at': None,
        'auto_assigned': False,
        'assigned_by': None,
        'assigned_at': None,
        'created_at': registration_date,
        'updated_at': updated_date,
        'year': year
    }

    return participant


def generate_notes():
    """Generate realistic notes to organizers."""
    notes_options = [
        "I would like to carpool if possible",
        "This is my first time participating",
        "I have mobility limitations and prefer accessible locations",
        "I'd like to be with an experienced team leader",
        "I can drive others if needed for carpooling",
        "I'm particularly interested in waterfowl identification",
        "I have experience with raptors and can help with identification",
        "Happy to help with whatever area needs volunteers"
    ]
    return random.choice(notes_options)


def generate_year_data(db_client, year: int, min_participants: int = 2,
                      max_participants: int = 8, clear_existing: bool = False):
    """
    Generate a complete year's worth of participant data.

    Args:
        db_client: Firestore client
        year: Year to generate data for
        min_participants: Minimum participants per area (including leader)
        max_participants: Maximum participants per area
        clear_existing: If True, clear existing data for this year first
    """
    collection_name = f'participants_{year}'
    areas = get_public_areas()

    print(f"Generating historical data for {year}")
    print(f"Target collection: {collection_name}")
    print(f"Areas: {', '.join(areas)} ({len(areas)} total)")
    print(f"Participants per area: {min_participants}-{max_participants}")
    print()

    # Clear existing data if requested
    if clear_existing:
        print(f"Clearing existing data in {collection_name}...")
        collection_ref = db_client.collection(collection_name)
        batch = db_client.batch()
        docs = collection_ref.limit(500).stream()

        delete_count = 0
        for doc in docs:
            batch.delete(doc.reference)
            delete_count += 1
            if delete_count % 500 == 0:
                batch.commit()
                batch = db_client.batch()

        if delete_count % 500 != 0:
            batch.commit()

        print(f"  Deleted {delete_count} existing documents")
        print()

    # Generate participants for each area
    collection_ref = db_client.collection(collection_name)
    total_created = 0

    for area_code in areas:
        # Determine how many participants for this area
        num_participants = random.randint(min_participants, max_participants)

        # At least one must be a leader
        num_leaders = random.randint(1, 2) if num_participants >= 3 else 1

        print(f"Area {area_code}: Creating {num_participants} participants ({num_leaders} leader(s))...")

        # Create leaders first
        for i in range(num_leaders):
            participant = generate_participant(area_code, year, is_leader=True, participant_num=i+1)
            collection_ref.add(participant)
            print(f"  ✓ {participant['first_name']} {participant['last_name']} [LEADER]")
            total_created += 1

        # Create remaining participants
        for i in range(num_leaders, num_participants):
            participant = generate_participant(area_code, year, is_leader=False, participant_num=i+1)
            collection_ref.add(participant)

            type_indicator = f" [{participant['participation_type'].upper()}]" if participant['participation_type'] == 'FEEDER' else ""
            print(f"  ✓ {participant['first_name']} {participant['last_name']}{type_indicator}")
            total_created += 1

    print()
    print("=" * 50)
    print(f"✓ Successfully created {total_created} participants for {year}")
    print(f"  Areas covered: {len(areas)}")
    print(f"  Average per area: {total_created / len(areas):.1f}")
    print("=" * 50)


def main():
    parser = argparse.ArgumentParser(
        description='Generate historical year data for demo/testing',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python generate_historical_year.py --year 2024
    python generate_historical_year.py --year 2024 --min-participants 3 --max-participants 8
    python generate_historical_year.py --year 2024 --clear-existing
        """
    )

    parser.add_argument(
        '--year',
        type=int,
        required=True,
        help='Year to generate data for (e.g., 2024)'
    )

    parser.add_argument(
        '--min-participants',
        type=int,
        default=2,
        help='Minimum participants per area including leaders (default: 2)'
    )

    parser.add_argument(
        '--max-participants',
        type=int,
        default=8,
        help='Maximum participants per area (default: 8)'
    )

    parser.add_argument(
        '--clear-existing',
        action='store_true',
        help='Clear existing data for this year before generating'
    )

    args = parser.parse_args()

    # Validate arguments
    if args.min_participants < 1:
        print("Error: Minimum participants must be at least 1")
        sys.exit(1)

    if args.max_participants < args.min_participants:
        print("Error: Maximum participants must be >= minimum participants")
        sys.exit(1)

    # Get Firestore client
    try:
        print("Connecting to Firestore...")
        db, database_name = get_firestore_client()
        print(f"Connected to database: {database_name}")
        print()
    except Exception as e:
        print(f"Error: Failed to connect to Firestore: {e}")
        sys.exit(1)

    # Confirm if clearing existing data
    if args.clear_existing:
        response = input(f"WARNING: This will DELETE all data in participants_{args.year}. Continue? (yes/no): ")
        if response.lower() != 'yes':
            print("Aborted.")
            sys.exit(0)

    # Generate data
    try:
        generate_year_data(
            db,
            year=args.year,
            min_participants=args.min_participants,
            max_participants=args.max_participants,
            clear_existing=args.clear_existing
        )
        sys.exit(0)

    except Exception as e:
        print(f"Error: Failed to generate data: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
