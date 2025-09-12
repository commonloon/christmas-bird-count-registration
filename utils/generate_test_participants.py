#!/usr/bin/env python3
"""
Updated by Claude AI on 2025-09-12
Test Participant Data Generator for Christmas Bird Count Registration

This script generates test participants by submitting data to the registration endpoint.
It creates realistic test data for testing the admin interface and registration system.

Usage:
    python generate_test_participants.py [num_regular] [--seq starting_number]
    
Examples:
    python generate_test_participants.py                    # 20 regular + 5 leadership + random scribes
    python generate_test_participants.py 50                # 50 regular + 5 leadership + random scribes  
    python generate_test_participants.py 10 --seq 100      # 10 regular + 5 leadership, emails start at 0100
    python generate_test_participants.py 0 --seq 5000      # 0 regular + 5 leadership, emails start at 5000
    python generate_test_participants.py 20 --scribes 5    # 20 regular + 5 leadership + 5 explicit scribes
"""

import argparse
import random
import requests
import sys
import time
from datetime import datetime
from faker import Faker

# Configuration
REGISTRATION_URL = "https://cbc-test.naturevancouver.ca/register"
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
    
    # Add equipment randomly
    if random.random() < 0.7:  # 70% have binoculars
        data['has_binoculars'] = 'on'
    if random.random() < 0.3:  # 30% can bring spotting scope
        data['spotting_scope'] = 'on'
    
    # Add leadership interest for specific participants (only for regular participants)
    if interested_in_leadership and participation_type == 'regular':
        data['interested_in_leadership'] = 'on'
    
    # Add scribe interest for regular participants (pilot program)
    if participation_type == 'regular':
        # Either forced scribe interest or 10% random chance
        if interested_in_scribe or random.random() < 0.1:
            data['interested_in_scribe'] = 'on'
    
    return data


def submit_registration(session, participant_data):
    """Submit registration data to the endpoint."""
    try:
        response = session.post(
            REGISTRATION_URL,
            data=participant_data,
            timeout=30,
            allow_redirects=True
        )
        
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


def main():
    parser = argparse.ArgumentParser(
        description="Generate test participants for Christmas Bird Count registration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python generate_test_participants.py                    # 20 regular + 5 leadership + random scribes
    python generate_test_participants.py 50                # 50 regular + 5 leadership + random scribes  
    python generate_test_participants.py 10 --seq 100      # 10 regular + 5 leadership, emails start at 0100
    python generate_test_participants.py 0 --seq 5000      # 0 regular + 5 leadership, emails start at 5000
    python generate_test_participants.py 20 --scribes 5    # 20 regular + 5 leadership + 5 explicit scribes
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
    
    args = parser.parse_args()
    
    # Validate arguments
    if args.num_regular < 0:
        print("Error: Number of regular participants cannot be negative")
        sys.exit(1)
    
    # Calculate totals
    num_regular = args.num_regular
    num_leadership = 5  # Always create 5 leadership-interested participants
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
    
    successful_registrations = 0
    failed_registrations = 0
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
            
            success, status_code, final_url = submit_registration(session, participant_data)
            
            if success:
                print(" OK")
                successful_registrations += 1
            else:
                print(f" FAIL (HTTP {status_code})")
                failed_registrations += 1
            
            current_seq += 1
            
            # Small delay to be respectful to the server
            time.sleep(0.5)
    
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
        
        success, status_code, final_url = submit_registration(session, participant_data)
        
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
            
            success, status_code, final_url = submit_registration(session, participant_data)
            
            if success:
                print(" OK")
                successful_registrations += 1
            else:
                print(f" FAIL (HTTP {status_code})")
                failed_registrations += 1
            
            current_seq += 1
            
            # Small delay to be respectful to the server
            time.sleep(0.5)
    
    # Summary
    print()
    print("Registration Summary:")
    print(f"  Successful: {successful_registrations}")
    print(f"  Failed: {failed_registrations}")
    print(f"  Total attempted: {total_participants}")
    
    if failed_registrations > 0:
        print(f"  Success rate: {(successful_registrations/total_participants)*100:.1f}%")
        sys.exit(1)
    else:
        print("  All registrations completed successfully! ✓")
        sys.exit(0)


if __name__ == "__main__":
    main()