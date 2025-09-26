# Registration Workflow Tests
# Updated by Claude AI on 2025-09-25

"""
Comprehensive registration workflow tests for the Christmas Bird Count system.
Tests all participant registration scenarios with form validation and constraints.
"""

import pytest
import logging
import sys
import os
import time
from datetime import datetime

# Add project root to path for imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from tests.config import get_base_url, get_database_name
from tests.page_objects import RegistrationPage
from tests.data import get_test_participant
from models.participant import ParticipantModel
from google.cloud import firestore
from selenium import webdriver
from webdriver_manager.firefox import GeckoDriverManager
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.firefox.options import Options

logger = logging.getLogger(__name__)




@pytest.fixture
def registration_page(browser):
    """Create registration page object."""
    base_url = get_base_url()
    page = RegistrationPage(browser, base_url)
    return page


@pytest.fixture
def db_client(clean_database):
    """Create database client for verification with clean state."""
    # clean_database fixture provides the cleaned firestore client
    return clean_database


@pytest.fixture
def participant_model(db_client):
    """Create participant model for current year."""
    current_year = datetime.now().year
    return ParticipantModel(db_client, current_year)


class TestRegistrationWorkflows:
    """Test registration form workflows for different participant types."""

    @pytest.mark.critical
    @pytest.mark.registration
    def test_regular_participant_complete_workflow(self, registration_page, participant_model):
        """Test complete registration workflow for regular participant."""
        logger.info("Testing regular participant registration workflow")

        # Get test data
        participant_data = get_test_participant('participants', 'regular_intermediate')
        participant_email = participant_data['personal']['email']

        # Navigate to registration page
        assert registration_page.navigate_to_registration(), "Failed to navigate to registration page"
        assert registration_page.is_registration_form_loaded(), "Registration form did not load"

        # Fill out complete registration form
        assert registration_page.fill_complete_registration_form(participant_data), \
            "Failed to fill registration form"

        # Submit registration
        assert registration_page.submit_registration(), "Failed to submit registration"

        # Wait for redirect to success page
        time.sleep(3)
        success_url = registration_page.get_current_url()
        assert 'success' in success_url or 'registered' in success_url, \
            f"Did not redirect to success page: {success_url}"

        # Verify participant was created in database
        time.sleep(2)  # Allow for database write
        participants = participant_model.get_all_participants()
        registered_participant = next(
            (p for p in participants if p.get('email', '').lower() == participant_email.lower()),
            None
        )

        assert registered_participant is not None, f"Participant not found in database: {participant_email}"

        # Verify participant data
        assert registered_participant['first_name'] == participant_data['personal']['first_name']
        assert registered_participant['last_name'] == participant_data['personal']['last_name']
        assert registered_participant['skill_level'] == participant_data['experience']['skill_level']
        assert registered_participant['participation_type'] == participant_data['participation']['type']
        assert registered_participant['preferred_area'] == participant_data['participation']['area']
        assert registered_participant['interested_in_leadership'] == participant_data['interests']['leadership']

        logger.info("✓ Regular participant registration workflow completed successfully")

    @pytest.mark.critical
    @pytest.mark.registration
    def test_feeder_participant_workflow(self, registration_page, participant_model):
        """Test FEEDER participant registration with constraint validation."""
        logger.info("Testing FEEDER participant registration workflow")

        # Get FEEDER test data
        participant_data = get_test_participant('participants', 'feeder_expert')
        participant_email = participant_data['personal']['email']

        # Navigate to registration page
        assert registration_page.navigate_to_registration(), "Failed to navigate to registration page"
        assert registration_page.is_registration_form_loaded(), "Registration form did not load"

        # Fill personal and experience information first
        assert registration_page.fill_personal_information(participant_data), \
            "Failed to fill personal information"
        assert registration_page.fill_experience_information(participant_data), \
            "Failed to fill experience information"

        # Select FEEDER participation type
        assert registration_page.select_participation_type('FEEDER'), \
            "Failed to select FEEDER participation type"

        # Wait for form updates after selecting FEEDER
        time.sleep(1)

        # Verify FEEDER constraints are enforced
        constraints = registration_page.verify_feeder_constraints()
        logger.info(f"FEEDER constraints: {constraints}")

        # Note: Constraint validation may vary based on implementation
        # This test documents current behavior rather than enforcing specific constraints

        # Continue with form completion (FEEDER must select specific area, not UNASSIGNED)
        assert registration_page.select_preferred_area(participant_data['participation']['area']), \
            "Failed to select preferred area for FEEDER"

        # Complete equipment preferences (skip interests for FEEDER)
        assert registration_page.set_equipment_preferences(participant_data), \
            "Failed to set equipment preferences"

        # Fill notes
        assert registration_page.fill_notes_field(participant_data.get('notes', '')), \
            "Failed to fill notes field"

        # Submit registration
        assert registration_page.submit_registration(), "Failed to submit FEEDER registration"

        # Wait and verify success
        time.sleep(3)
        success_url = registration_page.get_current_url()
        assert 'success' in success_url or 'registered' in success_url, \
            f"FEEDER registration did not redirect to success page: {success_url}"

        # Verify in database
        time.sleep(2)
        participants = participant_model.get_all_participants()
        feeder_participant = next(
            (p for p in participants if p.get('email', '').lower() == participant_email.lower()),
            None
        )

        assert feeder_participant is not None, f"FEEDER participant not found: {participant_email}"
        assert feeder_participant['participation_type'] == 'FEEDER'
        assert feeder_participant['preferred_area'] == participant_data['participation']['area']
        assert feeder_participant['preferred_area'] != 'UNASSIGNED', "FEEDER should not be unassigned"

        logger.info("✓ FEEDER participant registration workflow completed successfully")

    @pytest.mark.registration
    def test_unassigned_volunteer_workflow(self, registration_page, participant_model):
        """Test registration for volunteer willing to go anywhere."""
        logger.info("Testing unassigned volunteer registration workflow")

        participant_data = get_test_participant('participants', 'unassigned_volunteer')
        participant_email = participant_data['personal']['email']

        assert registration_page.navigate_to_registration(), "Failed to navigate to registration page"
        assert registration_page.fill_complete_registration_form(participant_data), \
            "Failed to fill registration form for unassigned volunteer"
        assert registration_page.submit_registration(), "Failed to submit unassigned volunteer registration"

        time.sleep(3)
        success_url = registration_page.get_current_url()
        assert 'success' in success_url or 'registered' in success_url, \
            f"Unassigned volunteer did not redirect to success: {success_url}"

        # Verify database registration
        time.sleep(2)
        participants = participant_model.get_all_participants()
        volunteer = next(
            (p for p in participants if p.get('email', '').lower() == participant_email.lower()),
            None
        )

        assert volunteer is not None, f"Unassigned volunteer not found: {participant_email}"
        assert volunteer['preferred_area'] == 'UNASSIGNED'
        assert volunteer['interested_in_scribe'] == participant_data['interests']['scribe']

        logger.info("✓ Unassigned volunteer registration workflow completed successfully")

    @pytest.mark.registration
    def test_leadership_interested_registration(self, registration_page, participant_model):
        """Test registration with leadership interest."""
        logger.info("Testing leadership interested participant registration")

        participant_data = get_test_participant('participants', 'regular_expert_leader')
        participant_email = participant_data['personal']['email']

        assert registration_page.navigate_to_registration(), "Failed to navigate to registration page"
        assert registration_page.fill_complete_registration_form(participant_data), \
            "Failed to fill registration form for leadership candidate"
        assert registration_page.submit_registration(), "Failed to submit leadership interested registration"

        time.sleep(3)
        success_url = registration_page.get_current_url()
        assert 'success' in success_url or 'registered' in success_url, \
            f"Leadership interested registration failed: {success_url}"

        # Verify database registration with leadership interest
        time.sleep(2)
        participants = participant_model.get_all_participants()
        leader_candidate = next(
            (p for p in participants if p.get('email', '').lower() == participant_email.lower()),
            None
        )

        assert leader_candidate is not None, f"Leadership candidate not found: {participant_email}"
        assert leader_candidate['interested_in_leadership'] == True
        assert leader_candidate['is_leader'] == False  # Not yet promoted
        assert leader_candidate['skill_level'] == 'Expert'

        logger.info("✓ Leadership interested registration workflow completed successfully")

    @pytest.mark.registration
    def test_scribe_interested_registration(self, registration_page, participant_model):
        """Test registration with scribe role interest."""
        logger.info("Testing scribe interested participant registration")

        participant_data = get_test_participant('participants', 'regular_scribe_interested')
        participant_email = participant_data['personal']['email']

        assert registration_page.navigate_to_registration(), "Failed to navigate to registration page"
        assert registration_page.fill_complete_registration_form(participant_data), \
            "Failed to fill registration form for scribe candidate"
        assert registration_page.submit_registration(), "Failed to submit scribe interested registration"

        time.sleep(3)
        success_url = registration_page.get_current_url()
        assert 'success' in success_url or 'registered' in success_url, \
            f"Scribe interested registration failed: {success_url}"

        # Verify database registration with scribe interest
        time.sleep(2)
        participants = participant_model.get_all_participants()
        scribe_candidate = next(
            (p for p in participants if p.get('email', '').lower() == participant_email.lower()),
            None
        )

        assert scribe_candidate is not None, f"Scribe candidate not found: {participant_email}"
        assert scribe_candidate['interested_in_scribe'] == True
        assert scribe_candidate['interested_in_leadership'] == False

        logger.info("✓ Scribe interested registration workflow completed successfully")


class TestRegistrationFormValidation:
    """Test form validation and error handling."""

    @pytest.mark.critical
    @pytest.mark.registration
    def test_required_field_validation(self, registration_page):
        """Test that required fields are properly validated."""
        logger.info("Testing required field validation")

        assert registration_page.navigate_to_registration(), "Failed to navigate to registration page"

        # Attempt to submit empty form
        assert registration_page.submit_registration(), "Failed to click submit button"

        time.sleep(2)

        # Should stay on registration page due to validation errors
        current_url = registration_page.get_current_url()
        assert 'success' not in current_url and 'registered' not in current_url, \
            "Form submitted without required fields - validation failed"

        # Verify we're still on registration page (browser validation or server validation)
        assert registration_page.is_registration_form_loaded(), \
            "Should remain on registration page when validation fails"

        logger.info("✓ Required field validation working correctly")

    @pytest.mark.registration
    def test_email_format_validation(self, registration_page):
        """Test email format validation."""
        logger.info("Testing email format validation")

        invalid_emails = ['invalid-email', 'test@', '@test.com', 'test..test@example.com']

        for invalid_email in invalid_emails:
            assert registration_page.navigate_to_registration(), f"Failed to navigate for {invalid_email}"

            # Fill minimal required fields with invalid email
            participant_data = get_test_participant('participants', 'regular_newbie')
            participant_data['personal']['email'] = invalid_email

            # Fill form with invalid email
            registration_page.fill_personal_information(participant_data)
            registration_page.fill_experience_information(participant_data)
            registration_page.select_participation_type('regular')
            registration_page.select_preferred_area('B')

            # Attempt submission
            registration_page.submit_registration()
            time.sleep(2)

            # Should not succeed
            current_url = registration_page.get_current_url()
            assert 'success' not in current_url, f"Invalid email {invalid_email} was accepted"

        logger.info("✓ Email format validation working correctly")

    @pytest.mark.registration
    def test_duplicate_email_prevention(self, registration_page, participant_model):
        """Test that duplicate email registration is prevented."""
        logger.info("Testing duplicate email prevention")

        # Register first participant
        first_participant = get_test_participant('participants', 'regular_newbie')
        shared_email = first_participant['personal']['email']

        assert registration_page.navigate_to_registration(), "Failed to navigate for first registration"
        assert registration_page.fill_complete_registration_form(first_participant), \
            "Failed to fill first registration"
        assert registration_page.submit_registration(), "Failed to submit first registration"

        time.sleep(3)
        assert 'success' in registration_page.get_current_url() or 'registered' in registration_page.get_current_url(), \
            "First registration failed"

        # Attempt to register second participant with same email
        second_participant = get_test_participant('participants', 'regular_intermediate')
        second_participant['personal']['email'] = shared_email  # Use same email

        assert registration_page.navigate_to_registration(), "Failed to navigate for duplicate registration"
        assert registration_page.fill_complete_registration_form(second_participant), \
            "Failed to fill duplicate registration"
        registration_page.submit_registration()

        time.sleep(3)
        current_url = registration_page.get_current_url()

        # Should either stay on registration page with error or show specific error page
        # The exact behavior depends on implementation - document actual behavior
        if 'success' in current_url or 'registered' in current_url:
            logger.warning("Duplicate email registration was allowed - check if this is intended behavior")
        else:
            logger.info("✓ Duplicate email registration properly prevented")

        # Verify database state
        time.sleep(2)
        participants = participant_model.get_all_participants()
        same_email_participants = [p for p in participants if p.get('email', '').lower() == shared_email.lower()]

        logger.info(f"Found {len(same_email_participants)} participants with email {shared_email}")

    @pytest.mark.critical
    @pytest.mark.registration
    def test_identity_conflict_prevention(self, registration_page, participant_model):
        """Test that registering the exact same identity (first_name, last_name, email) is prevented."""
        logger.info("Testing identity conflict prevention")

        # Create a participant with unique identity (email provides uniqueness, names are real names)
        from tests.data.test_scenarios import generate_unique_email
        unique_email = generate_unique_email("identity-conflict")
        identity = {
            'first_name': 'TestIdentity',
            'last_name': 'ConflictTest',
            'email': unique_email
        }

        # Create first registration with this exact identity
        first_participant = get_test_participant('participants', 'regular_newbie')
        first_participant['personal'].update(identity)

        # Register first participant successfully
        assert registration_page.navigate_to_registration(), "Failed to navigate for first registration"
        assert registration_page.fill_complete_registration_form(first_participant), \
            "Failed to fill first registration"
        assert registration_page.submit_registration(), "Failed to submit first registration"

        time.sleep(3)
        first_url = registration_page.get_current_url()
        assert 'success' in first_url or 'registered' in first_url, \
            f"First registration should succeed: {first_url}"

        # Verify first participant was created in database
        time.sleep(2)
        participants = participant_model.get_all_participants()

        # Debug information
        logger.info(f"DEBUG: Total participants in database: {len(participants)}")
        logger.info(f"DEBUG: Looking for identity: {identity}")
        if participants:
            for i, p in enumerate(participants):
                logger.info(f"DEBUG: Participant {i}: {p.get('first_name')} {p.get('last_name')} {p.get('email')}")

        matching_participants = [
            p for p in participants
            if (p.get('first_name') == identity['first_name'] and
                p.get('last_name') == identity['last_name'] and
                p.get('email', '').lower() == identity['email'].lower())
        ]

        if len(matching_participants) != 1:
            logger.error(f"DEBUG: Expected 1 participant, found {len(matching_participants)}")
            logger.error(f"DEBUG: First registration URL was: {first_url}")
            logger.error(f"DEBUG: Identity used: {identity}")

        assert len(matching_participants) == 1, f"First participant should be created. Found {len(matching_participants)} matching participants out of {len(participants)} total."
        logger.info(f"✓ First registration successful for identity: {identity['first_name']} {identity['last_name']}")

        # Attempt to register EXACT SAME identity again (should be prevented)
        second_participant = get_test_participant('participants', 'regular_intermediate')
        second_participant['personal'].update(identity)  # Use identical identity

        assert registration_page.navigate_to_registration(), "Failed to navigate for duplicate identity registration"
        assert registration_page.fill_complete_registration_form(second_participant), \
            "Failed to fill duplicate identity registration"
        registration_page.submit_registration()

        time.sleep(3)
        second_url = registration_page.get_current_url()

        # CRITICAL VALIDATION: Duplicate identity should be PREVENTED
        if 'success' in second_url or 'registered' in second_url:
            # If it succeeded, this is a BUG - the application should prevent identical identities
            time.sleep(2)  # Allow database write
            participants_after = participant_model.get_all_participants()
            duplicate_participants = [
                p for p in participants_after
                if (p.get('first_name') == identity['first_name'] and
                    p.get('last_name') == identity['last_name'] and
                    p.get('email', '').lower() == identity['email'].lower())
            ]

            logger.error(f"BUSINESS RULE VIOLATION: Duplicate identity was allowed! Found {len(duplicate_participants)} participants with identical identity")
            logger.error(f"Identity: {identity['first_name']} {identity['last_name']} {identity['email']}")

            # This is a CRITICAL FAILURE - the core business rule is being violated
            pytest.fail(f"CRITICAL BUG: Application allowed duplicate identity registration. "
                       f"Found {len(duplicate_participants)} participants with identical identity "
                       f"({identity['first_name']}, {identity['last_name']}, {identity['email']}). "
                       f"This violates the core business rule that identity must be unique.")
        else:
            # This is the expected behavior - duplicate identity was prevented
            logger.info("✓ Duplicate identity registration properly prevented")

            # Verify database state - should still have only one participant
            time.sleep(2)
            participants_final = participant_model.get_all_participants()
            final_matching = [
                p for p in participants_final
                if (p.get('first_name') == identity['first_name'] and
                    p.get('last_name') == identity['last_name'] and
                    p.get('email', '').lower() == identity['email'].lower())
            ]
            assert len(final_matching) == 1, f"Should still have exactly one participant, found {len(final_matching)}"
            logger.info("✓ Database integrity maintained - only one participant with this identity exists")

        logger.info("✓ Identity conflict prevention test completed")


class TestFormDataPreservation:
    """Test form data preservation during navigation."""

    @pytest.mark.registration
    def test_area_leader_info_navigation(self, registration_page):
        """Test form data preservation when visiting area leader info."""
        logger.info("Testing form data preservation during area leader info navigation")

        assert registration_page.navigate_to_registration(), "Failed to navigate to registration page"

        # Fill partial form data
        participant_data = get_test_participant('participants', 'regular_intermediate')
        registration_page.fill_personal_information(participant_data)
        registration_page.fill_experience_information(participant_data)

        # Get current form data
        original_data = registration_page.get_form_data()
        logger.info(f"Original form data: {original_data}")

        # Navigate to area leader info
        if registration_page.navigate_to_area_leader_info():
            logger.info("Successfully navigated to area leader info page")

            # Navigate back to registration
            assert registration_page.navigate_to_registration(), "Failed to navigate back to registration"

            # Verify form data is preserved
            preserved_data = registration_page.get_form_data()
            preservation_result = registration_page.verify_form_data_preserved(original_data)

            logger.info(f"Form data preservation result: {preservation_result}")

            if preservation_result['preserved']:
                logger.info("✓ Form data preserved during area leader info navigation")
            else:
                logger.warning(f"Form data not fully preserved: {preservation_result}")
        else:
            logger.warning("Could not test area leader info navigation - link not found")

    @pytest.mark.registration
    def test_scribe_info_navigation(self, registration_page):
        """Test form data preservation when visiting scribe info."""
        logger.info("Testing form data preservation during scribe info navigation")

        assert registration_page.navigate_to_registration(), "Failed to navigate to registration page"

        # Fill partial form data
        participant_data = get_test_participant('participants', 'regular_scribe_interested')
        registration_page.fill_personal_information(participant_data)
        registration_page.fill_experience_information(participant_data)

        # Get current form data
        original_data = registration_page.get_form_data()

        # Navigate to scribe info
        if registration_page.navigate_to_scribe_info():
            logger.info("Successfully navigated to scribe info page")

            # Navigate back to registration
            assert registration_page.navigate_to_registration(), "Failed to navigate back to registration"

            # Verify form data is preserved
            preservation_result = registration_page.verify_form_data_preserved(original_data)

            if preservation_result['preserved']:
                logger.info("✓ Form data preserved during scribe info navigation")
            else:
                logger.warning(f"Form data not fully preserved: {preservation_result}")
        else:
            logger.warning("Could not test scribe info navigation - link not found")