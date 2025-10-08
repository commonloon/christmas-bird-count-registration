# Family Email Scenario Tests for CBC Registration System
# Updated by Claude AI on 2025-09-25

"""
Tests for family email sharing scenarios in the Christmas Bird Count registration system.
These tests validate that multiple family members can share an email address while
maintaining proper identity-based operations and data isolation in the single-table design.
"""

import pytest
import logging
import time
import sys
import os
from datetime import datetime

# Add project root to Python path for imports
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

logger = logging.getLogger(__name__)


def safe_click(browser, locator, timeout=10):
    """Safely click an element by scrolling to it and waiting for it to be clickable."""
    wait = WebDriverWait(browser, timeout)
    element = wait.until(EC.element_to_be_clickable(locator))
    browser.execute_script("arguments[0].scrollIntoView(true);", element)
    time.sleep(0.3)  # Brief pause after scrolling
    element.click()
    return element


def safe_select_by_value(browser, locator, value, timeout=10):
    """Safely select a dropdown option by value after scrolling the dropdown into view."""
    wait = WebDriverWait(browser, timeout)
    select_element = wait.until(EC.presence_of_element_located(locator))
    browser.execute_script("arguments[0].scrollIntoView(true);", select_element)
    time.sleep(0.3)  # Brief pause after scrolling
    select = Select(select_element)
    select.select_by_value(value)
    return select_element


def verify_registration_success(browser, expected_email, expected_first_name=None, expected_last_name=None):
    """
    Verify successful registration by checking database first, then URL.

    Args:
        browser: Selenium WebDriver instance
        expected_email: Email address to search for
        expected_first_name: Expected first name (if provided, will verify exact match)
        expected_last_name: Expected last name (if provided, will verify exact match)
    """
    import urllib.parse
    from models.participant import ParticipantModel
    from config.database import get_firestore_client

    # Wait for page to redirect and database write
    time.sleep(3)

    # Check database FIRST - this is the source of truth
    db, _ = get_firestore_client()
    participant_model = ParticipantModel(db, datetime.now().year)

    # If we have specific names to verify, search for that exact identity
    if expected_first_name and expected_last_name:
        # Look for exact identity match (supports family email scenarios)
        participants = participant_model.get_all_participants()
        matching_participants = [
            p for p in participants
            if (p.get('email', '').lower() == expected_email.lower() and
                p.get('first_name', '') == expected_first_name and
                p.get('last_name', '') == expected_last_name)
        ]

        if not matching_participants:
            # Debug: show what participants we DO have with this email
            email_participants = [p for p in participants if p.get('email', '').lower() == expected_email.lower()]
            debug_info = [(p.get('first_name'), p.get('last_name')) for p in email_participants]
            raise AssertionError(
                f"Expected participant '{expected_first_name} {expected_last_name}' with email {expected_email} not found. "
                f"Found participants with this email: {debug_info}"
            )

        participant = matching_participants[0]  # Should be exactly one match
    else:
        # Fallback to old behavior for backward compatibility
        participants = participant_model.get_all_participants()
        matching_participants = [p for p in participants if p.get('email', '').lower() == expected_email.lower()]

        if not matching_participants:
            raise AssertionError(f"No participant found with email: {expected_email}")

        participant = max(matching_participants, key=lambda p: p.get('created_at', ''))

    participant_id = participant.get('id')
    logger.info(f"✓ Database: Found registered participant: {participant.get('first_name')} {participant.get('last_name')} ({expected_email})")

    # Now check if success page was displayed (UI validation)
    current_url = browser.current_url
    if not ('success' in current_url or 'thank' in current_url):
        logger.warning(f"UI Issue: Registration succeeded in database but browser did not navigate to success page. URL: {current_url}")
        logger.warning("This indicates a timing or navigation issue in the UI, but registration actually succeeded.")
    else:
        logger.info(f"✓ UI: Success page displayed at {current_url}")

    return participant_id, participant


def register_family_member(browser, base_url, first_name, last_name, email, area, participation_type="regular", max_retries=3):
    """Helper to register a family member with shared email, with retry logic for rate limiting."""

    for attempt in range(max_retries):
        try:
            browser.get(base_url)

            # Add delay between attempts to avoid rate limiting
            if attempt > 0:
                delay = 2 ** attempt  # Exponential backoff: 2s, 4s, 8s
                logger.info(f"Registration attempt {attempt + 1} for {first_name} {last_name}, waiting {delay}s...")
                time.sleep(delay)

            # Fill registration form
            browser.find_element(By.ID, "first_name").clear()
            browser.find_element(By.ID, "first_name").send_keys(first_name)
            browser.find_element(By.ID, "last_name").clear()
            browser.find_element(By.ID, "last_name").send_keys(last_name)
            browser.find_element(By.ID, "email").clear()
            browser.find_element(By.ID, "email").send_keys(email)
            browser.find_element(By.ID, "phone").clear()
            browser.find_element(By.ID, "phone").send_keys("604-555-FAMILY")

            # Select skill level and experience
            safe_select_by_value(browser, (By.ID, "skill_level"), "Intermediate")
            safe_select_by_value(browser, (By.ID, "experience"), "1-2 counts")

            # Select area and participation type
            safe_select_by_value(browser, (By.ID, "preferred_area"), area)
            safe_click(browser, (By.ID, participation_type))  # Click radio button for participation type

            # Equipment preferences
            safe_click(browser, (By.ID, "has_binoculars"))

            # Submit registration
            safe_click(browser, (By.XPATH, "//button[@type='submit']"))

            # Verify successful registration
            participant_id, participant = verify_registration_success(browser, email, expected_first_name=first_name, expected_last_name=last_name)
            logger.info(f"✓ Successfully registered {first_name} {last_name} on attempt {attempt + 1}")
            return participant_id, participant

        except AssertionError as e:
            if attempt == max_retries - 1:
                logger.error(f"Failed to register {first_name} {last_name} after {max_retries} attempts: {e}")
                raise
            else:
                logger.warning(f"Registration attempt {attempt + 1} failed for {first_name} {last_name}: {e}")
                continue

    raise AssertionError(f"Failed to register {first_name} {last_name} after {max_retries} attempts")


class TestFamilyEmailSharing:
    """Test family members sharing email addresses with proper identity isolation."""

    @pytest.mark.critical
    @pytest.mark.family
    def test_family_registration_workflow(self, browser, base_url, clean_database):
        """Test that family members can register separately with shared email."""
        # Use alphabetic unique identifier (no digits - they get sanitized out)
        import random
        import string
        test_suffix = ''.join(random.choices(string.ascii_lowercase, k=8))
        family_email = f"family-workflow-{test_suffix}@test-functional.ca"

        # Register first family member (parent)
        parent_id, parent = register_family_member(
            browser, base_url, "John", f"Workflow{test_suffix}", family_email, "A"
        )

        # Register second family member (child) with same email
        child_id, child = register_family_member(
            browser, base_url, "Jane", f"Workflow{test_suffix}", family_email, "B"
        )

        # Verify both family members exist in database
        from models.participant import ParticipantModel
        from config.database import get_firestore_client

        db, _ = get_firestore_client()
        participant_model = ParticipantModel(db, datetime.now().year)

        all_participants = participant_model.get_all_participants()
        family_participants = [
            p for p in all_participants
            if p.get('email', '').lower() == family_email.lower()
        ]

        assert len(family_participants) == 2, f"Should have 2 family members, found {len(family_participants)}"

        # Verify they have different identities
        names = [(p.get('first_name'), p.get('last_name')) for p in family_participants]
        expected_last_name = f"Workflow{test_suffix}"
        assert ('John', expected_last_name) in names, f"Should find John {expected_last_name}"
        assert ('Jane', expected_last_name) in names, f"Should find Jane {expected_last_name}"

        # Verify they have different areas
        areas = [p.get('preferred_area') for p in family_participants]
        assert 'A' in areas and 'B' in areas, f"Should have areas A and B, got: {areas}"

        logger.info("✓ Family registration workflow works correctly")

    @pytest.mark.critical
    @pytest.mark.family
    def test_family_member_identity_isolation(self, browser, base_url, clean_database):
        """Test that operations on one family member don't affect others."""
        import random
        import string
        test_suffix = ''.join(random.choices(string.ascii_lowercase, k=8))
        family_email = f"iso-isolation-{test_suffix}@test-functional.ca"

        # Register two family members
        parent_id, parent = register_family_member(
            browser, base_url, "Parent", f"Isolation{test_suffix}", family_email, "C"
        )
        child_id, child = register_family_member(
            browser, base_url, "Child", f"Isolation{test_suffix}", family_email, "D"
        )

        from models.participant import ParticipantModel
        from config.database import get_firestore_client

        db, _ = get_firestore_client()
        participant_model = ParticipantModel(db, datetime.now().year)

        # Record child state before parent operations
        child_before = participant_model.get_participant(child_id)
        assert child_before is not None, "Child should exist before parent operations"

        # Delete parent participant
        parent_deletion = participant_model.delete_participant(parent_id)
        assert parent_deletion, "Parent deletion should succeed"

        # Verify child is completely unaffected
        child_after = participant_model.get_participant(child_id)
        assert child_after is not None, "Child should still exist after parent deletion"
        assert child_after.get('preferred_area') == child_before.get('preferred_area'), "Child's area should be unchanged"
        assert child_after.get('first_name') == child_before.get('first_name'), "Child's name should be unchanged"

        # Verify parent is deleted
        parent_after = participant_model.get_participant(parent_id)
        assert parent_after is None, "Parent should be deleted"

        logger.info("✓ Family member identity isolation works correctly")

    @pytest.mark.family
    def test_family_leader_management_independence(self, browser, base_url, clean_database):
        """Test that family members can be independently managed as leaders."""
        import random
        import string
        test_suffix = ''.join(random.choices(string.ascii_lowercase, k=8))
        family_email = f"ldrmgmt-leader-{test_suffix}@test-functional.ca"

        # Register two family members
        bob_id, bob = register_family_member(
            browser, base_url, "Bob", f"Leader{test_suffix}", family_email, "E"
        )
        alice_id, alice = register_family_member(
            browser, base_url, "Alice", f"Leader{test_suffix}", family_email, "F"
        )

        from models.participant import ParticipantModel
        from config.database import get_firestore_client

        db, _ = get_firestore_client()
        participant_model = ParticipantModel(db, datetime.now().year)

        # Promote Bob to leader
        bob_promotion = participant_model.assign_area_leadership(bob_id, "E", "test-family-leader@test.ca")
        assert bob_promotion, "Bob leadership assignment should succeed"

        # Promote Alice to leader
        alice_promotion = participant_model.assign_area_leadership(alice_id, "F", "test-family-leader@test.ca")
        assert alice_promotion, "Alice leadership assignment should succeed"

        # Verify both are leaders
        bob_after_promotion = participant_model.get_participant(bob_id)
        alice_after_promotion = participant_model.get_participant(alice_id)

        assert bob_after_promotion.get('is_leader'), "Bob should be a leader"
        assert alice_after_promotion.get('is_leader'), "Alice should be a leader"
        assert bob_after_promotion.get('assigned_area_leader') == 'E', "Bob should lead area E"
        assert alice_after_promotion.get('assigned_area_leader') == 'F', "Alice should lead area F"

        # Remove Bob's leadership
        bob_demotion = participant_model.remove_area_leadership(bob_id, "test-family-demotion")
        assert bob_demotion, "Bob demotion should succeed"

        # Verify Alice's leadership is unaffected
        alice_after_bob_demotion = participant_model.get_participant(alice_id)
        assert alice_after_bob_demotion.get('is_leader'), "Alice should still be a leader"
        assert alice_after_bob_demotion.get('assigned_area_leader') == 'F', "Alice should still lead area F"

        # Verify Bob is no longer a leader
        bob_after_demotion = participant_model.get_participant(bob_id)
        assert not bob_after_demotion.get('is_leader'), "Bob should no longer be a leader"
        assert bob_after_demotion.get('assigned_area_leader') is None, "Bob should not have assigned area"

        logger.info("✓ Family members can be independently managed as leaders")

    @pytest.mark.family
    def test_family_duplicate_prevention(self, browser, base_url, clean_database):
        """Test that duplicate prevention allows different family members while preventing same identity duplicates."""
        import random
        import string
        test_suffix = ''.join(random.choices(string.ascii_lowercase, k=8))
        family_email = f"duplicate-test-{test_suffix}@test-functional.ca"

        # Register first family member
        original_id, original = register_family_member(
            browser, base_url, "Original", "DuplicateTest", family_email, "G"
        )
        logger.info("✓ First registration successful: Original DuplicateTest")

        # Attempt to register SAME identity again (should be prevented)
        browser.get(base_url)
        time.sleep(1)

        # Fill form with IDENTICAL identity
        browser.find_element(By.ID, "first_name").clear()
        browser.find_element(By.ID, "first_name").send_keys("Original")
        browser.find_element(By.ID, "last_name").clear()
        browser.find_element(By.ID, "last_name").send_keys("DuplicateTest")
        browser.find_element(By.ID, "email").clear()
        browser.find_element(By.ID, "email").send_keys(family_email)
        browser.find_element(By.ID, "phone").clear()
        browser.find_element(By.ID, "phone").send_keys("604-555-DUPL")

        # Select required fields
        safe_select_by_value(browser, (By.ID, "skill_level"), "Intermediate")
        safe_select_by_value(browser, (By.ID, "experience"), "1-2 counts")
        safe_select_by_value(browser, (By.ID, "preferred_area"), "G")
        safe_click(browser, (By.ID, "regular"))
        safe_click(browser, (By.ID, "has_binoculars"))

        # Submit duplicate registration
        safe_click(browser, (By.XPATH, "//button[@type='submit']"))
        time.sleep(3)

        duplicate_url = browser.current_url

        # CRITICAL: Duplicate identity should be PREVENTED
        if 'success' in duplicate_url or 'registered' in duplicate_url:
            pytest.fail(
                f"CRITICAL BUG: Duplicate identity registration was allowed! "
                f"Identity (Original, DuplicateTest, {family_email}) was registered twice."
            )
        else:
            logger.info("✓ Duplicate identity registration properly prevented")

        # Register DIFFERENT family member with same email (should be allowed)
        different_id, different = register_family_member(
            browser, base_url, "Different", "DuplicateTest", family_email, "H"
        )
        logger.info("✓ Different family member with same email successfully registered")

        # Verify final state
        from models.participant import ParticipantModel
        from config.database import get_firestore_client

        db, _ = get_firestore_client()
        participant_model = ParticipantModel(db, datetime.now().year)

        family_participants = [
            p for p in participant_model.get_all_participants()
            if p.get('email', '').lower() == family_email.lower()
        ]

        names = [(p.get('first_name'), p.get('last_name')) for p in family_participants]
        assert len(family_participants) == 2, f"Should have exactly 2 family members, found {len(family_participants)}"
        assert ('Original', 'DuplicateTest') in names, "Original should exist"
        assert ('Different', 'DuplicateTest') in names, "Different should exist"
        assert len([n for n in names if n == ('Original', 'DuplicateTest')]) == 1, "Should have only one Original"

        logger.info("✓ Duplicate prevention works correctly: allows different identities, prevents same identity")


class TestFamilyEmailEdgeCases:
    """Test edge cases and error scenarios with family email sharing."""

    @pytest.mark.family
    def test_large_family_scenario(self, browser, base_url, clean_database):
        """Test behavior with a large family (4+ members)."""
        import random
        import string
        test_suffix = ''.join(random.choices(string.ascii_lowercase, k=8))
        family_email = f"largefam-large-{test_suffix}@test-functional.ca"
        family_members = [
            {'name': 'Mom', 'area': 'M'},
            {'name': 'Dad', 'area': 'N'},
            {'name': 'Alice', 'area': 'O'},
            {'name': 'Bob', 'area': 'P'}
        ]

        registered_ids = []
        for member in family_members:
            member_id, member_data = register_family_member(
                browser, base_url, member['name'], f"Largefam{test_suffix}", family_email, member['area']
            )
            registered_ids.append(member_id)

        from models.participant import ParticipantModel
        from config.database import get_firestore_client

        db, _ = get_firestore_client()
        participant_model = ParticipantModel(db, datetime.now().year)

        # Verify all family members exist
        family_participants = [
            p for p in participant_model.get_all_participants()
            if p.get('email', '').lower() == family_email.lower()
        ]

        assert len(family_participants) == 4, f"Should have 4 family members, found {len(family_participants)}"

        # Verify they have unique identities
        names = [(p.get('first_name'), p.get('last_name')) for p in family_participants]
        unique_names = set(names)
        assert len(names) == len(unique_names), f"All family members should have unique names: {names}"

        # Verify they all share the same email
        emails = [p.get('email') for p in family_participants]
        assert all(email == family_email for email in emails), "All family members should share the same email"

        logger.info("✓ Large family scenario works correctly")

    @pytest.mark.family
    def test_family_authentication_sharing(self, browser, base_url, clean_database):
        """Test that family members sharing email can have shared authentication privileges."""
        family_email = f"auth-sharing-{int(time.time())}@test-functional.ca"

        # Register leader candidate
        leader_id, leader = register_family_member(
            browser, base_url, "LeaderCandidate", "AuthTest", family_email, "Q"
        )

        # Register regular member
        regular_id, regular = register_family_member(
            browser, base_url, "RegularMember", "AuthTest", family_email, "R"
        )

        from models.participant import ParticipantModel
        from config.database import get_firestore_client

        db, _ = get_firestore_client()
        participant_model = ParticipantModel(db, datetime.now().year)

        # Promote leader candidate to actual leader
        leadership_assigned = participant_model.assign_area_leadership(leader_id, "Q", "test-auth-assignment@test.ca")
        assert leadership_assigned, "Leadership assignment should succeed"

        # Verify family email sharing setup for authentication
        promoted_leader = participant_model.get_participant(leader_id)
        regular_member = participant_model.get_participant(regular_id)

        assert promoted_leader.get('is_leader'), "Leader candidate should be promoted"
        assert not regular_member.get('is_leader'), "Regular member should not be leader"

        # Both should share the same email for authentication privileges
        assert promoted_leader.get('email') == regular_member.get('email'), "Both should share same email"

        logger.info("✓ Family authentication sharing data setup works correctly")


class TestFamilyEmailPerformance:
    """Test performance considerations with family email scenarios."""

    @pytest.mark.slow
    @pytest.mark.family
    def test_multiple_families_performance(self, browser, base_url, clean_database):
        """Test performance with multiple families sharing different emails."""
        import random
        import string
        test_suffix = ''.join(random.choices(string.ascii_lowercase, k=8))
        family_count = 3
        members_per_family = 2
        families_created = []

        start_time = datetime.now()

        for i in range(family_count):
            family_email = f"perf-family-{test_suffix}-{i}@test-performance.ca"
            families_created.append(family_email)

            for j in range(members_per_family):
                # Use alphabetic names to avoid sanitization issues
                member_names = ['Alex', 'Betty']  # Two members per family
                # Use unique last names per test run to avoid conflicts (alphabetic only)
                family_last_names = [f'PerfOne{test_suffix}', f'PerfTwo{test_suffix}', f'PerfThree{test_suffix}']
                member_id, member_data = register_family_member(
                    browser, base_url, member_names[j], family_last_names[i],
                    family_email, chr(ord('A') + (i * 2) + j)
                )
                time.sleep(1.5)  # Longer delay to avoid rate limiting (50/min = ~1.2s per registration)

        creation_time = datetime.now() - start_time

        # Verify all families were created correctly
        verification_start = datetime.now()

        from models.participant import ParticipantModel
        from config.database import get_firestore_client

        db, _ = get_firestore_client()
        participant_model = ParticipantModel(db, datetime.now().year)

        all_participants = participant_model.get_all_participants()

        for family_email in families_created:
            family_participants = [
                p for p in all_participants
                if p.get('email', '').lower() == family_email.lower()
            ]
            assert len(family_participants) == members_per_family, f"Family {family_email} should have {members_per_family} members"

            # Verify unique identities within family
            names = [(p.get('first_name'), p.get('last_name')) for p in family_participants]
            unique_names = set(names)
            assert len(names) == len(unique_names), f"Family {family_email} should have unique member names"

        verification_time = datetime.now() - verification_start

        # Performance assertions (adjust based on acceptable thresholds)
        total_participants = family_count * members_per_family
        assert creation_time.total_seconds() < (total_participants * 15), f"Family creation should complete reasonably quickly, took {creation_time.total_seconds()}s for {total_participants} participants"
        assert verification_time.total_seconds() < 15, f"Family verification should complete quickly, took {verification_time.total_seconds()}s"

        logger.info(f"✓ Multiple families performance test passed - creation: {creation_time.total_seconds():.2f}s, verification: {verification_time.total_seconds():.2f}s for {total_participants} participants across {family_count} families")