#!/usr/bin/env python3
"""
Updated by Claude AI on 2025-09-26
Test Participant Data Generator for Christmas Bird Count Registration

This script generates test participants by submitting data to the registration endpoint.
It creates realistic test data for testing the admin interface and registration system.

Usage:
    python generate_test_participants.py [num_regular] [--seq starting_number] [--leaders N] [--scribes N]

Examples:
    python generate_test_participants.py                    # 20 regular + 5 leadership (default --leaders=5)
    python generate_test_participants.py 50                # 50 regular + 5 leadership (default --leaders=5)
    python generate_test_participants.py 10 --seq 100      # 10 regular + 5 leadership, emails start at 0100
    python generate_test_participants.py 0 --seq 5000      # 0 regular + 5 leadership, emails start at 5000
    python generate_test_participants.py 20 --scribes 5    # 20 regular + 5 leadership + 5 explicit scribes
    python generate_test_participants.py 20 --leaders 10   # 20 regular + 10 leadership (override default)
    python generate_test_participants.py 30 --leaders 0    # 30 regular + 0 leadership (no leaders)

Note: 10% of all participants randomly receive scribe interest regardless of --scribes flag
"""

import argparse
import random
import re
import requests
import sys
import time
from datetime import datetime
from faker import Faker
from bs4 import BeautifulSoup

# Configuration
BASE_URL = "https://cbc-test.naturevancouver.ca"
REGISTRATION_URL = f"{BASE_URL}/register"
EMAIL_DOMAIN = "naturevancouver.ca"

# Initialize faker for realistic names
fake = Faker()

# Valid form values based on the registration form
SKILL_LEVELS = ["Newbie", "Beginner", "Intermediate", "Expert"]
EXPERIENCE_LEVELS = ["None", "1-2 counts", "3+ counts"]
AREAS = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", 
         "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "UNASSIGNED"]

# Canadian area codes for realistic phone numbers
AREA_CODES = ["604", "778", "236"]


def generate_phone_number():
    """Generate a realistic Canadian phone number."""
    area_code = random.choice(AREA_CODES)
    exchange = random.randint(200, 999)
    number = random.randint(1000, 9999)
    return f"({area_code}) {exchange}-{number}"


def get_csrf_token(session):
    """Fetch CSRF token from the registration page."""
    try:
        response = session.get(BASE_URL, timeout=30)
        if response.status_code != 200:
            print(f"Warning: Could not fetch registration page (HTTP {response.status_code})")
            return None
        
        # Try BeautifulSoup first (more reliable)
        try:
            soup = BeautifulSoup(response.text, 'html.parser')
            # Look for CSRF token in hidden input or meta tag
            csrf_input = soup.find('input', {'name': 'csrf_token'})
            if csrf_input and csrf_input.get('value'):
                return csrf_input['value']
            
            # Alternative: look for csrf_token() function output
            csrf_meta = soup.find('meta', {'name': 'csrf-token'})
            if csrf_meta and csrf_meta.get('content'):
                return csrf_meta['content']
                
        except Exception as e:
            print(f"Warning: BeautifulSoup parsing failed: {e}")
        
        # Fallback: regex search for CSRF token patterns
        csrf_patterns = [
            r'name="csrf_token"[^>]*value="([^"]+)"',
            r'csrf_token[\'"]?\s*:\s*[\'"]([^"\']+)[\'"]',
            r'<input[^>]*name=[\'"]csrf_token[\'"][^>]*value=[\'"]([^"\']+)[\'"]'
        ]
        
        for pattern in csrf_patterns:
            match = re.search(pattern, response.text, re.IGNORECASE)
            if match:
                return match.group(1)
        
        print("Warning: Could not find CSRF token in page")
        return None
        
    except requests.exceptions.RequestException as e:
        print(f"Warning: Failed to fetch CSRF token: {e}")
        return None


def generate_email(date_str, sequence_num):
    """Generate sequential email address with timestamp for uniqueness."""
    import time
    timestamp = str(int(time.time()))[-6:]  # Last 6 digits of unix timestamp
    return f"birdcount-{date_str}-{timestamp}-{sequence_num:04d}@{EMAIL_DOMAIN}"


def generate_notes():
    """Generate realistic notes to organizers."""
    notes_options = [
        "",  # Many participants won't have notes
        "I would like to car pool to the meeting point",
        "I would prefer to be assigned to an area in East Vancouver", 
        "This is my first time participating, please assign me to a beginner-friendly area",
        "I have mobility limitations and prefer accessible locations",
        "I'd like to be with an experienced team leader",
        "I can drive others if needed for carpooling",
        "Please let me know about early morning meeting times",
        "I'm particularly interested in waterfowl identification",
        "I have experience with raptors and can help with identification"
    ]
    return random.choice(notes_options)


def create_participant_data(email, interested_in_leadership=False, interested_in_scribe=False, force_unassigned=False):
    """Create realistic participant data with new fields."""
    first_name = fake.first_name()
    last_name = fake.last_name()
    
    # 20% FEEDER participants, 80% regular participants
    # BUT: participants explicitly requested to be leadership-interested must be regular
    if interested_in_leadership:
        participation_type = 'regular'  # Force regular type for leadership-interested participants
    else:
        participation_type = 'FEEDER' if random.random() < 0.2 else 'regular'

    # FEEDER participants: specific area (never UNASSIGNED), no leadership interest
    if participation_type == 'FEEDER':
        # Choose from specific areas only (exclude UNASSIGNED)
        specific_areas = [area for area in AREAS if area != 'UNASSIGNED']
        preferred_area = random.choice(specific_areas)
        interested_in_leadership = False  # FEEDER participants cannot be leaders
    else:
        # Regular participants: any area including UNASSIGNED if requested
        if force_unassigned:
            preferred_area = "UNASSIGNED"
        else:
            preferred_area = random.choice(AREAS)
    
    data = {
        'first_name': first_name,
        'last_name': last_name,
        'email': email,
        'phone': generate_phone_number(),
        'skill_level': random.choice(SKILL_LEVELS),
        'experience': random.choice(EXPERIENCE_LEVELS),
        'preferred_area': preferred_area,
        'participation_type': participation_type,
        'notes_to_organizers': generate_notes()
    }
    
    # Add equipment randomly (send 'on' like HTML checkboxes)
    if random.random() < 0.7:  # 70% have binoculars
        data['has_binoculars'] = 'on'
    if random.random() < 0.3:  # 30% can bring spotting scope
        data['spotting_scope'] = 'on'

    # Add leadership interest for specific participants (only for regular participants)
    # Send 'on' like HTML checkboxes do when checked
    if interested_in_leadership and participation_type == 'regular':
        data['interested_in_leadership'] = 'on'

    # Add scribe interest for regular participants (pilot program)
    if participation_type == 'regular':
        # Either forced scribe interest or 10% random chance
        if interested_in_scribe or random.random() < 0.1:
            data['interested_in_scribe'] = 'on'
    
    return data


def submit_registration(session, participant_data, csrf_token=None):
    """Submit registration data to the endpoint with CSRF protection."""
    try:
        # Add CSRF token if provided
        if csrf_token:
            participant_data['csrf_token'] = csrf_token
        
        response = session.post(
            REGISTRATION_URL,
            data=participant_data,
            timeout=30,
            allow_redirects=True
        )
        
        # Check for rate limiting
        if response.status_code == 429:
            return False, 429, "Rate limited"
        
        # Check for CSRF errors (both when token provided and when missing)
        if response.status_code == 400:
            if csrf_token:
                return False, 400, "CSRF validation failed"
            else:
                return False, 400, "CSRF token missing"
        
        # Check if registration was successful
        # The endpoint redirects to /success on successful registration
        success = (response.status_code == 200 and '/success' in response.url)
        
        # Debug: Print response details for failed registrations (comment out when working)
        # if not success and response.status_code == 200:
        #     print(f"\nDEBUG: Registration failed but got 200")
        #     print(f"Final URL: {response.url}")
        #     print(f"Form data sent: {participant_data}")
        #     print()
        
        return success, response.status_code, response.url
        
    except requests.exceptions.RequestException as e:
        return False, 0, str(e)


def test_rate_limiting(starting_seq=1):
    """Test rate limiting by sending 100 registrations as fast as possible."""
    print(f"Rate Limiting Test Mode")
    print(f"======================")
    print(f"Target endpoint: {REGISTRATION_URL}")
    print(f"Sending 100 registrations as fast as possible to test rate limiting...")
    print(f"Expected: Some registrations should be blocked with HTTP 429 responses")
    print()
    
    # Generate current date string
    current_date = datetime.now().strftime('%Y-%m-%d')
    
    # Create HTTP session
    session = requests.Session()
    
    # Get CSRF token
    print("Fetching CSRF token...")
    csrf_token = get_csrf_token(session)
    if not csrf_token:
        print("ERROR: Could not fetch CSRF token. Aborting test.")
        return 1
    print(f"CSRF token acquired: {csrf_token[:16]}...")
    print()
    
    successful_registrations = 0
    rate_limited_count = 0
    other_failures = 0
    current_seq = starting_seq
    
    print("Sending registrations (fast mode - 0.1 second delays):")
    
    for i in range(100):
        # Generate test participant data
        email = generate_email(current_date, current_seq)
        participant_data = create_participant_data(email, interested_in_leadership=False)
        
        print(f"  [{current_seq:04d}] {participant_data['first_name']} {participant_data['last_name']} ({email})", end="")
        
        success, status_code, final_url = submit_registration(session, participant_data, csrf_token)
        
        if success:
            print(" OK")
            successful_registrations += 1
        elif status_code == 429:
            print(" RATE_LIMITED (expected)")
            rate_limited_count += 1
        else:
            print(f" FAIL (HTTP {status_code})")
            other_failures += 1
        
        current_seq += 1
        
        # Very short delay to send rapidly
        time.sleep(0.1)
    
    print()
    print("Rate Limiting Test Results:")
    print(f"  Successful registrations: {successful_registrations}")
    print(f"  Rate limited (HTTP 429): {rate_limited_count}")
    print(f"  Other failures: {other_failures}")
    print()
    
    if rate_limited_count > 0:
        print("✅ SUCCESS: Rate limiting is working correctly!")
    else:
        print("⚠️  WARNING: No rate limiting detected. Check configuration.")
    
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Generate test participants for Christmas Bird Count registration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python generate_test_participants.py                    # 20 regular + 5 leadership (default --leaders=5)
    python generate_test_participants.py 50                # 50 regular + 5 leadership (default --leaders=5)
    python generate_test_participants.py 10 --seq 100      # 10 regular + 5 leadership, emails start at 0100
    python generate_test_participants.py 0 --seq 5000      # 0 regular + 5 leadership, emails start at 5000
    python generate_test_participants.py 20 --scribes 5    # 20 regular + 5 leadership + 5 explicit scribes
    python generate_test_participants.py 20 --leaders 10   # 20 regular + 10 leadership (override default)
    python generate_test_participants.py 30 --leaders 0    # 30 regular + 0 leadership (no leaders)
    python generate_test_participants.py --test-rate-limit # Send 100 registrations rapidly to test rate limiting

Note: 10% of all participants randomly receive scribe interest regardless of --scribes flag
        """
    )
    
    parser.add_argument(
        'num_regular', 
        nargs='?', 
        type=int, 
        default=20,
        help='Number of regular participants to create (default: 20)'
    )
    
    parser.add_argument(
        '--seq', 
        type=int, 
        default=1,
        choices=range(1, 10000),
        metavar='1-9999',
        help='Starting sequence number for email addresses (default: 1)'
    )
    
    parser.add_argument(
        '--scribes',
        type=int,
        default=0,
        help='Number of participants specifically interested in scribe role (default: 0, relies on random 10%% generation)'
    )

    parser.add_argument(
        '--leaders',
        type=int,
        default=5,
        help='Number of participants specifically interested in leadership role (default: 5)'
    )
    
    parser.add_argument(
        '--test-rate-limit',
        action='store_true',
        help='Test rate limiting by sending 100 registrations as fast as possible (ignores other limits)'
    )
    
    args = parser.parse_args()
    
    # Validate arguments
    if args.num_regular < 0:
        print("Error: Number of regular participants cannot be negative")
        sys.exit(1)
    
    # Special handling for rate limit testing
    if args.test_rate_limit:
        return test_rate_limiting(args.seq)
    
    # Calculate totals
    num_regular = args.num_regular
    num_leadership = args.leaders  # Number of leadership-interested participants
    num_scribes = args.scribes  # Number of explicitly scribe-interested participants
    total_participants = num_regular + num_leadership + num_scribes
    starting_seq = args.seq
    
    # Generate current date string
    current_date = datetime.now().strftime('%Y-%m-%d')
    
    print(f"Christmas Bird Count Test Data Generator")
    print(f"========================================")
    print(f"Target endpoint: {REGISTRATION_URL}")
    print(f"Regular participants: {num_regular}")
    print(f"Leadership-interested participants: {num_leadership}")
    print(f"Scribe-interested participants: {num_scribes}")
    print(f"Total participants: {total_participants}")
    print(f"Starting sequence number: {starting_seq}")
    print(f"Email format: birdcount-{current_date}-NNNN@{EMAIL_DOMAIN}")
    print()
    
    # Create HTTP session for better performance
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'CBC-Test-Data-Generator/1.0'
    })
    
    # Get CSRF token
    print("Fetching CSRF token...")
    csrf_token = get_csrf_token(session)
    if not csrf_token:
        print("ERROR: Could not fetch CSRF token. Registration will likely fail.")
        print("Continuing anyway to test error handling...")
    else:
        print(f"CSRF token acquired: {csrf_token[:16]}...")
    print()
    
    successful_registrations = 0
    failed_registrations = 0
    csrf_failures = 0
    rate_limited_count = 0
    current_seq = starting_seq
    
    # Create regular participants
    if num_regular > 0:
        print(f"Creating {num_regular} regular participants...")
        for i in range(num_regular):
            email = generate_email(current_date, current_seq)
            
            # Force the first regular participant to be unassigned
            force_unassigned = (i == 0)
            participant_data = create_participant_data(email, interested_in_leadership=False, force_unassigned=force_unassigned)
            
            unassigned_indicator = " [UNASSIGNED]" if force_unassigned else ""
            scribe_indicator = " [SCRIBE]" if participant_data.get('interested_in_scribe') == 'on' else ""
            print(f"  [{current_seq:04d}] {participant_data['first_name']} {participant_data['last_name']} ({email}){unassigned_indicator}{scribe_indicator}", end="")
            
            success, status_code, final_url = submit_registration(session, participant_data, csrf_token)
            
            if success:
                print(" OK")
                successful_registrations += 1
            elif status_code == 429:
                print(" RATE_LIMITED")
                rate_limited_count += 1
            elif status_code == 400:
                print(" CSRF_FAIL")
                csrf_failures += 1
            else:
                print(f" FAIL (HTTP {status_code})")
                failed_registrations += 1
            
            current_seq += 1
            
            # Small delay to respect rate limits (50/minute = 1.2 seconds)
            time.sleep(1.2)
    
    # Create leadership-interested participants
    print(f"Creating {num_leadership} leadership-interested participants...")
    for i in range(num_leadership):
        email = generate_email(current_date, current_seq)
        
        # If no regular participants were created, make the first leadership participant unassigned
        force_unassigned = (num_regular == 0 and i == 0)
        participant_data = create_participant_data(email, interested_in_leadership=True, force_unassigned=force_unassigned)
        
        leader_indicator = " [LEADER]"
        unassigned_indicator = " [UNASSIGNED]" if force_unassigned else ""
        print(f"  [{current_seq:04d}] {participant_data['first_name']} {participant_data['last_name']} ({email}){leader_indicator}{unassigned_indicator}", end="")
        
        success, status_code, final_url = submit_registration(session, participant_data, csrf_token)
        
        if success:
            print(" ✓")
            successful_registrations += 1
        else:
            print(f" ✗ (HTTP {status_code})")
            failed_registrations += 1
        
        current_seq += 1
        
        # Small delay to be respectful to the server
        time.sleep(0.5)
    
    # Create scribe-interested participants
    if num_scribes > 0:
        print(f"Creating {num_scribes} scribe-interested participants...")
        for i in range(num_scribes):
            email = generate_email(current_date, current_seq)
            
            # Scribe participants are regular participants with scribe interest
            participant_data = create_participant_data(email, interested_in_leadership=False, interested_in_scribe=True, force_unassigned=False)
            
            scribe_indicator = " [SCRIBE]"
            print(f"  [{current_seq:04d}] {participant_data['first_name']} {participant_data['last_name']} ({email}){scribe_indicator}", end="")
            
            success, status_code, final_url = submit_registration(session, participant_data, csrf_token)
            
            if success:
                print(" OK")
                successful_registrations += 1
            elif status_code == 429:
                print(" RATE_LIMITED")
                rate_limited_count += 1
            elif status_code == 400:
                print(" CSRF_FAIL")
                csrf_failures += 1
            else:
                print(f" FAIL (HTTP {status_code})")
                failed_registrations += 1
            
            current_seq += 1
            
            # Small delay to respect rate limits (50/minute = 1.2 seconds)
            time.sleep(1.2)
    
    # Summary
    print()
    print("Registration Summary:")
    print(f"  Successful: {successful_registrations}")
    print(f"  Rate limited (HTTP 429): {rate_limited_count}")
    print(f"  CSRF failures (HTTP 400): {csrf_failures}")
    print(f"  Other failures: {failed_registrations}")
    print(f"  Total attempted: {total_participants}")
    
    total_failures = failed_registrations + csrf_failures + rate_limited_count
    if total_failures > 0:
        print(f"  Success rate: {(successful_registrations/total_participants)*100:.1f}%")
        if rate_limited_count > 0:
            print("  Note: Rate limiting is working correctly!")
        if csrf_failures > 0:
            print("  Note: CSRF protection is active!")
        sys.exit(1)
    else:
        print("  All registrations completed successfully! ✓")
        sys.exit(0)


if __name__ == "__main__":
    main()