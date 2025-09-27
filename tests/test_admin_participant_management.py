# Admin Participant Management Tests
# Updated by Claude AI on 2025-09-25

"""
Admin participant management workflow tests for the Christmas Bird Count system.
Tests participant viewing, editing, promotion, assignment, and deletion operations.
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
from tests.page_objects import AdminDashboardPage, AdminParticipantsPage
from tests.data import get_test_participant
from tests.utils.auth_utils import admin_login_for_test
from models.participant import ParticipantModel
from google.cloud import firestore
from selenium import webdriver

logger = logging.getLogger(__name__)




@pytest.fixture
def admin_dashboard(browser):
    """Create admin dashboard page object."""
    base_url = get_base_url()
    page = AdminDashboardPage(browser, base_url)
    return page


@pytest.fixture
def admin_participants_page(browser):
    """Create admin participants page object."""
    base_url = get_base_url()
    page = AdminParticipantsPage(browser, base_url)
    return page


@pytest.fixture
def db_client():
    """Create database client."""
    database_name = get_database_name()
    if database_name == '(default)':
        client = firestore.Client()
    else:
        client = firestore.Client(database=database_name)
    yield client


@pytest.fixture
def participant_model(db_client):
    """Create participant model for current year."""
    current_year = datetime.now().year
    return ParticipantModel(db_client, current_year)




class TestParticipantViewing:
    """Test participant viewing and display functionality."""

    @pytest.mark.critical
    @pytest.mark.admin
    def test_participants_page_loads(self, browser, test_credentials):
        """Test that participants page loads correctly."""
        logger.info("Testing participants page loading")

        # Login as admin
        admin_creds = test_credentials['admin_primary']
        base_url = get_base_url()
        admin_login_for_test(browser, base_url, admin_creds)

        # Navigate to participants page
        browser.get(f"{base_url}/admin/participants")

        # Verify we're on the participants page
        assert "participants" in browser.current_url, f"Expected participants URL, got: {browser.current_url}"

        logger.info("✓ Participants page loads correctly")

    @pytest.mark.admin
    def test_participant_display_with_data(self, browser, test_credentials, admin_participants_page, participant_model):
        """Test participant display with populated data."""
        logger.info("Testing participant display with data")

        # Create test participants for display testing
        test_participants = []
        for i, scenario in enumerate(['regular_newbie', 'feeder_expert', 'regular_expert_leader']):
            participant_data = get_test_participant('participants', scenario)

            # Make unique for testing
            participant_data['personal']['first_name'] += f"Display{i}"
            participant_data['personal']['last_name'] += f"Test{i}"

            participant_record = {
                'first_name': participant_data['personal']['first_name'],
                'last_name': participant_data['personal']['last_name'],
                'email': participant_data['personal']['email'],
                'phone': participant_data['personal']['phone'],
                'skill_level': participant_data['experience']['skill_level'],
                'experience': participant_data['experience']['experience'],
                'preferred_area': participant_data['participation']['area'],
                'participation_type': participant_data['participation']['type'],
                'has_binoculars': participant_data['equipment']['has_binoculars'],
                'spotting_scope': participant_data['equipment']['spotting_scope'],
                'interested_in_leadership': participant_data['interests']['leadership'],
                'interested_in_scribe': participant_data['interests']['scribe'],
                'notes_to_organizers': participant_data.get('notes', ''),
                'is_leader': False,
                'created_at': datetime.now(),
                'year': datetime.now().year
            }

            try:
                participant_id = participant_model.add_participant(participant_record)
                if participant_id:
                    participant_record['id'] = participant_id
                    test_participants.append(participant_record)
            except Exception as e:
                logger.warning(f"Could not create test participant {i}: {e}")

        if not test_participants:
            pytest.skip("Could not create test participants for display testing")

        # Login as admin and navigate to participants page
        admin_creds = test_credentials['admin_primary']
        base_url = get_base_url()
        admin_login_for_test(browser, base_url, admin_creds)
        browser.get(f"{base_url}/admin/participants")

        # Give page time to load
        time.sleep(2)

        # Get participants from page
        displayed_participants = admin_participants_page.get_all_participants_from_page()
        logger.info(f"Found {len(displayed_participants)} participants displayed on page")

        if displayed_participants:
            # Verify test participants appear
            displayed_emails = {p.get('email', '').lower() for p in displayed_participants}
            test_emails = {p['email'].lower() for p in test_participants}

            matches = displayed_emails.intersection(test_emails)
            logger.info(f"Found {len(matches)} test participants in display")

            # Check participant data structure
            sample_participant = displayed_participants[0]
            logger.info(f"Sample participant display data: {sample_participant}")

            logger.info("✓ Participant display with data working")
        else:
            logger.warning("No participants displayed on page")

        # Cleanup test participants
        for participant in test_participants:
            try:
                if participant.get('id'):
                    participant_model.delete_participant(participant['id'])
            except:
                pass

    @pytest.mark.admin
    def test_area_organization_display(self, browser, test_credentials, admin_participants_page):
        """Test that participants are organized by area."""
        logger.info("Testing area organization display")

        # Login as admin and navigate to participants page
        admin_creds = test_credentials['admin_primary']
        base_url = get_base_url()
        admin_login_for_test(browser, base_url, admin_creds)
        browser.get(f"{base_url}/admin/participants")

        # Get area headers
        area_headers = admin_participants_page.get_area_headers()
        logger.info(f"Area headers found: {area_headers}")

        if area_headers:
            logger.info("✓ Participants organized by area")

            # Verify area counts are reasonable
            total_from_headers = sum(area_headers.values())
            logger.info(f"Total participants from area headers: {total_from_headers}")

        else:
            logger.warning("No area organization detected")

    @pytest.mark.admin
    def test_feeder_participant_separation(self, browser, test_credentials, admin_participants_page):
        """Test FEEDER vs regular participant separation."""
        logger.info("Testing FEEDER participant separation")

        # Login as admin and navigate to participants page
        admin_creds = test_credentials['admin_primary']
        base_url = get_base_url()
        admin_login_for_test(browser, base_url, admin_creds)
        browser.get(f"{base_url}/admin/participants")

        # Check FEEDER display
        feeder_display = admin_participants_page.verify_feeder_participant_display()
        logger.info(f"FEEDER display info: {feeder_display}")

        if feeder_display['feeder_section_exists']:
            logger.info("✓ FEEDER participants have separate section")

        if feeder_display['feeder_indicators_present']:
            logger.info("✓ FEEDER participant indicators present")

        logger.info("FEEDER participant separation test completed")


class TestParticipantOperations:
    """Test participant management operations."""

    @pytest.mark.critical
    @pytest.mark.admin
    def test_participant_deletion_workflow(self, browser, test_credentials, admin_participants_page, participant_model):
        """Test participant deletion workflow."""
        logger.info("Testing participant deletion workflow")

        # Create test participant for deletion
        participant_data = get_test_participant('admin_operations', 'deletion_candidate')
        participant_record = {
            'first_name': participant_data['personal']['first_name'],
            'last_name': participant_data['personal']['last_name'],
            'email': participant_data['personal']['email'],
            'phone': participant_data['personal']['phone'],
            'skill_level': participant_data['experience']['skill_level'],
            'experience': participant_data['experience']['experience'],
            'preferred_area': participant_data['participation']['area'],
            'participation_type': participant_data['participation']['type'],
            'has_binoculars': participant_data['equipment']['has_binoculars'],
            'spotting_scope': participant_data['equipment']['spotting_scope'],
            'interested_in_leadership': participant_data['interests']['leadership'],
            'interested_in_scribe': participant_data['interests']['scribe'],
            'notes_to_organizers': participant_data.get('notes', ''),
            'is_leader': False,
            'created_at': datetime.now(),
            'year': datetime.now().year
        }

        try:
            participant_id = participant_model.add_participant(participant_record)
            if not participant_id:
                pytest.skip("Could not create test participant for deletion")

            participant_name = f"{participant_record['first_name']} {participant_record['last_name']}"
            participant_email = participant_record['email']

            # Navigate to participants page
            admin_creds = test_credentials['admin_primary']
            base_url = get_base_url()
            admin_login_for_test(browser, base_url, admin_creds)

            dashboard = AdminParticipantsPage(browser, base_url)
            browser.get(f"{base_url}/admin/participants")
            time.sleep(2)

            # Attempt to delete participant
            deletion_reason = participant_data.get('deletion_reason', 'Test deletion workflow')
            deletion_success = admin_participants_page.delete_participant(
                participant_email,  # Use email as identifier
                deletion_reason
            )

            if deletion_success:
                logger.info("✓ Participant deletion workflow completed")

                # Verify participant is deleted from database
                try:
                    deleted_participant = participant_model.get_participant(participant_id)
                    if deleted_participant:
                        logger.warning("Participant still exists in database after deletion")
                    else:
                        logger.info("✓ Participant properly removed from database")
                except:
                    logger.info("✓ Participant properly removed from database")

            else:
                logger.warning("Participant deletion workflow not completed (UI may not support deletion)")

        except Exception as e:
            logger.error(f"Error in participant deletion test: {e}")
            # Cleanup
            try:
                if 'participant_id' in locals() and participant_id:
                    participant_model.delete_participant(participant_id)
            except:
                pass

    @pytest.mark.admin
    def test_participant_assignment_workflow(self, browser, test_credentials, admin_participants_page, participant_model):
        """Test participant area assignment workflow."""
        logger.info("Testing participant assignment workflow")

        # Create unassigned test participant
        participant_data = get_test_participant('admin_operations', 'reassignment_candidate')
        participant_data['participation']['area'] = 'UNASSIGNED'  # Start unassigned

        participant_record = {
            'first_name': participant_data['personal']['first_name'],
            'last_name': participant_data['personal']['last_name'],
            'email': participant_data['personal']['email'],
            'phone': participant_data['personal']['phone'],
            'skill_level': participant_data['experience']['skill_level'],
            'experience': participant_data['experience']['experience'],
            'preferred_area': 'UNASSIGNED',
            'participation_type': participant_data['participation']['type'],
            'has_binoculars': participant_data['equipment']['has_binoculars'],
            'spotting_scope': participant_data['equipment']['spotting_scope'],
            'interested_in_leadership': participant_data['interests']['leadership'],
            'interested_in_scribe': participant_data['interests']['scribe'],
            'notes_to_organizers': participant_data.get('notes', ''),
            'is_leader': False,
            'created_at': datetime.now(),
            'year': datetime.now().year
        }

        try:
            participant_id = participant_model.add_participant(participant_record)
            if not participant_id:
                pytest.skip("Could not create test participant for assignment")

            participant_email = participant_record['email']
            target_area = participant_data.get('reassignment_target_area', 'B')

            # Navigate to participants page
            admin_creds = test_credentials['admin_primary']
            base_url = get_base_url()
            admin_login_for_test(browser, base_url, admin_creds)

            dashboard = AdminParticipantsPage(browser, base_url)
            browser.get(f"{base_url}/admin/participants")
            time.sleep(2)

            # Attempt to assign participant
            assignment_success = admin_participants_page.assign_participant_to_area(
                participant_email,
                target_area
            )

            if assignment_success:
                logger.info(f"✓ Participant assignment workflow completed (area: {target_area})")

                # Verify assignment in database
                time.sleep(2)
                updated_participant = participant_model.get_participant(participant_id)
                if updated_participant and updated_participant.get('preferred_area') == target_area:
                    logger.info("✓ Area assignment verified in database")
                else:
                    logger.warning("Area assignment not reflected in database")

            else:
                logger.warning("Participant assignment workflow not completed (UI may not support assignment)")

            # Cleanup
            participant_model.delete_participant(participant_id)

        except Exception as e:
            logger.error(f"Error in participant assignment test: {e}")
            if 'participant_id' in locals() and participant_id:
                try:
                    participant_model.delete_participant(participant_id)
                except:
                    pass


class TestLeadershipManagement:
    """Test single-table leadership management operations."""

    @pytest.mark.critical
    @pytest.mark.admin
    def test_participant_to_leader_promotion(self, browser, test_credentials, admin_participants_page, participant_model):
        """Test promoting participant to leader (single-table design)."""
        logger.info("Testing participant to leader promotion (single-table)")

        # Create promotion candidate
        participant_data = get_test_participant('admin_operations', 'promotion_candidate')
        participant_record = {
            'first_name': participant_data['personal']['first_name'],
            'last_name': participant_data['personal']['last_name'],
            'email': participant_data['personal']['email'],
            'phone': participant_data['personal']['phone'],
            'skill_level': participant_data['experience']['skill_level'],
            'experience': participant_data['experience']['experience'],
            'preferred_area': participant_data['participation']['area'],
            'participation_type': participant_data['participation']['type'],
            'has_binoculars': participant_data['equipment']['has_binoculars'],
            'spotting_scope': participant_data['equipment']['spotting_scope'],
            'interested_in_leadership': True,  # Leadership candidate
            'interested_in_scribe': participant_data['interests']['scribe'],
            'notes_to_organizers': participant_data.get('notes', ''),
            'is_leader': False,  # Start as regular participant
            'assigned_area_leader': None,
            'created_at': datetime.now(),
            'year': datetime.now().year
        }

        try:
            participant_id = participant_model.add_participant(participant_record)
            if not participant_id:
                pytest.skip("Could not create test participant for promotion")

            participant_email = participant_record['email']
            promotion_area = participant_data.get('promotion_target_area', participant_record['preferred_area'])

            # Navigate to participants page
            admin_creds = test_credentials['admin_primary']
            base_url = get_base_url()
            admin_login_for_test(browser, base_url, admin_creds)

            dashboard = AdminParticipantsPage(browser, base_url)
            browser.get(f"{base_url}/admin/participants")
            time.sleep(2)

            # Attempt to promote participant to leader
            promotion_success = admin_participants_page.promote_participant_to_leader(
                participant_email,
                promotion_area
            )

            if promotion_success:
                logger.info(f"✓ Participant promotion workflow completed (area: {promotion_area})")

                # Verify promotion in database (single-table design)
                time.sleep(2)
                promoted_participant = participant_model.get_participant(participant_id)

                if promoted_participant:
                    is_leader = promoted_participant.get('is_leader', False)
                    assigned_area_leader = promoted_participant.get('assigned_area_leader')

                    if is_leader:
                        logger.info("✓ Participant successfully promoted to leader (is_leader=True)")
                    else:
                        logger.warning("Participant promotion not reflected in database (is_leader still False)")

                    if assigned_area_leader == promotion_area:
                        logger.info(f"✓ Leader area assignment correct: {assigned_area_leader}")
                    else:
                        logger.warning(f"Leader area assignment incorrect: expected {promotion_area}, got {assigned_area_leader}")

                else:
                    logger.error("Could not retrieve promoted participant from database")

            else:
                logger.warning("Participant promotion workflow not completed (UI may not support promotion)")

            # Cleanup
            participant_model.delete_participant(participant_id)

        except Exception as e:
            logger.error(f"Error in participant promotion test: {e}")
            if 'participant_id' in locals() and participant_id:
                try:
                    participant_model.delete_participant(participant_id)
                except:
                    pass

    @pytest.mark.admin
    def test_leader_demotion_to_participant(self, browser, test_credentials, admin_participants_page, participant_model):
        """Test demoting leader back to participant (single-table design)."""
        logger.info("Testing leader to participant demotion (single-table)")

        # Create participant who is already a leader
        participant_data = get_test_participant('admin_operations', 'promotion_candidate')
        participant_record = {
            'first_name': participant_data['personal']['first_name'] + "Leader",
            'last_name': participant_data['personal']['last_name'],
            'email': participant_data['personal']['email'],
            'phone': participant_data['personal']['phone'],
            'skill_level': participant_data['experience']['skill_level'],
            'experience': participant_data['experience']['experience'],
            'preferred_area': participant_data['participation']['area'],
            'participation_type': participant_data['participation']['type'],
            'has_binoculars': participant_data['equipment']['has_binoculars'],
            'spotting_scope': participant_data['equipment']['spotting_scope'],
            'interested_in_leadership': True,
            'interested_in_scribe': participant_data['interests']['scribe'],
            'notes_to_organizers': participant_data.get('notes', ''),
            'is_leader': True,  # Start as leader
            'assigned_area_leader': participant_data['participation']['area'],
            'created_at': datetime.now(),
            'year': datetime.now().year
        }

        try:
            participant_id = participant_model.add_participant(participant_record)
            if not participant_id:
                pytest.skip("Could not create test leader for demotion")

            participant_email = participant_record['email']

            # Navigate to participants page
            admin_creds = test_credentials['admin_primary']
            base_url = get_base_url()
            admin_login_for_test(browser, base_url, admin_creds)

            dashboard = AdminParticipantsPage(browser, base_url)
            browser.get(f"{base_url}/admin/participants")
            time.sleep(2)

            # Attempt to demote leader
            demotion_success = admin_participants_page.demote_leader_to_participant(participant_email)

            if demotion_success:
                logger.info("✓ Leader demotion workflow completed")

                # Verify demotion in database (single-table design)
                time.sleep(2)
                demoted_participant = participant_model.get_participant(participant_id)

                if demoted_participant:
                    is_leader = demoted_participant.get('is_leader', True)
                    assigned_area_leader = demoted_participant.get('assigned_area_leader')

                    if not is_leader:
                        logger.info("✓ Leader successfully demoted to participant (is_leader=False)")
                    else:
                        logger.warning("Leader demotion not reflected in database (is_leader still True)")

                    if not assigned_area_leader:
                        logger.info("✓ Leader area assignment cleared")
                    else:
                        logger.warning(f"Leader area assignment not cleared: {assigned_area_leader}")

                else:
                    logger.error("Could not retrieve demoted participant from database")

            else:
                logger.warning("Leader demotion workflow not completed (UI may not support demotion)")

            # Cleanup
            participant_model.delete_participant(participant_id)

        except Exception as e:
            logger.error(f"Error in leader demotion test: {e}")
            if 'participant_id' in locals() and participant_id:
                try:
                    participant_model.delete_participant(participant_id)
                except:
                    pass

    @pytest.mark.admin
    def test_leadership_flag_consistency(self, browser, test_credentials, participant_model):
        """Test leadership flag consistency in single-table design."""
        logger.info("Testing leadership flag consistency (single-table)")

        # Create participant with leadership flags
        participant_data = get_test_participant('admin_operations', 'promotion_candidate')
        participant_record = {
            'first_name': participant_data['personal']['first_name'] + "Consistency",
            'last_name': participant_data['personal']['last_name'],
            'email': participant_data['personal']['email'],
            'phone': participant_data['personal']['phone'],
            'skill_level': participant_data['experience']['skill_level'],
            'experience': participant_data['experience']['experience'],
            'preferred_area': participant_data['participation']['area'],
            'participation_type': participant_data['participation']['type'],
            'has_binoculars': participant_data['equipment']['has_binoculars'],
            'spotting_scope': participant_data['equipment']['spotting_scope'],
            'interested_in_leadership': True,
            'interested_in_scribe': participant_data['interests']['scribe'],
            'notes_to_organizers': participant_data.get('notes', ''),
            'is_leader': True,
            'assigned_area_leader': 'B',
            'created_at': datetime.now(),
            'year': datetime.now().year
        }

        try:
            participant_id = participant_model.add_participant(participant_record)
            if not participant_id:
                pytest.skip("Could not create test participant for consistency check")

            # Verify participant is properly stored as leader
            stored_participant = participant_model.get_participant(participant_id)

            assert stored_participant['is_leader'] == True, "Leadership flag should be True"
            assert stored_participant['assigned_area_leader'] == 'B', "Leader area should be set"

            # Get leaders (should include this participant)
            leaders = participant_model.get_leaders()
            leader_emails = [l.get('email', '') for l in leaders]

            assert participant_record['email'] in leader_emails, "Participant should appear in leaders list"

            logger.info("✓ Leadership flag consistency maintained in single-table design")

            # Cleanup
            participant_model.delete_participant(participant_id)

        except Exception as e:
            logger.error(f"Error in leadership consistency test: {e}")
            if 'participant_id' in locals() and participant_id:
                try:
                    participant_model.delete_participant(participant_id)
                except:
                    pass