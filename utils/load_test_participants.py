#!/usr/bin/env python3
"""
Updated by Claude AI on 2026-10-20
Reload the 'test' circle's participants for the current year from the CSV fixture.

Writes straight to the local database through ParticipantModel - no form submissions,
so no confirmation emails are sent (unlike generate_test_participants.py). Use it after
running the test suite, whose fixtures clear the test circle's participants.

Usage:
    python utils/load_test_participants.py

Replaces ALL existing 'test'-circle participants for the current year; never touches
any other circle. Refuses to run unless DATABASE_URL points at localhost.
"""
import os
import sys
from datetime import datetime

from dotenv import load_dotenv
from sqlalchemy.engine import make_url

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
load_dotenv()

from config.database import get_db_session
from tests.test_config import TEST_CIRCLE_SLUG
from tests.utils.load_test_data import load_csv_participants, load_participants_to_postgres

CSV_PATH = os.path.join(os.path.dirname(__file__), '..', 'tests', 'fixtures', 'test_participants_2025.csv')


def main():
    host = make_url(os.environ.get('DATABASE_URL', '')).host
    if host not in ('localhost', '127.0.0.1'):
        sys.exit(f"Refusing to run: DATABASE_URL host {host!r} is not localhost/127.0.0.1.")

    year = datetime.now().year
    participants = load_csv_participants(CSV_PATH)
    loaded = load_participants_to_postgres(
        get_db_session(), year, participants, clear_first=True, circle_slug=TEST_CIRCLE_SLUG)
    print(f"Loaded {loaded} of {len(participants)} participants into the '{TEST_CIRCLE_SLUG}' circle for {year}.")


if __name__ == '__main__':
    main()
