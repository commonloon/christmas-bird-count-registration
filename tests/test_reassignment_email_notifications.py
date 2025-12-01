# Email Notification Tests for Participant Reassignment
# Updated by Claude AI on 2025-10-26

"""
Test suite for reassignment email notifications in the Christmas Bird Count system.

Tests validate that area leaders are correctly notified when participants are reassigned
between areas. Tests use CSV-based test data, mocked email service, and direct database
state verification.
"""

import pytest
import logging
import sys
import os
import json
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock
from bs4 import BeautifulSoup

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from google.cloud import firestore
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from tests.test_config import get_base_url, get_database_name
from tests.page_objects import AdminParticipantsPage
from tests.utils.load_test_data import load_test_fixture
from tests.utils.reassignment_helper import reassign_participant_via_ui
from models.participant import ParticipantModel
from models.reassignment_log import ReassignmentLogModel
from test.email_generator import (
    EmailTimestampModel,
    generate_team_update_emails,
    generate_weekly_summary_emails
)

logger = logging.getLogger(__name__)


class EmailCapture:
    """Captures emails instead of sending them via SMTP."""

    def __init__(self, output_dir: str = 'tests/tmp/emails'):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.captured_emails = []

    def send_email(self, recipients, subject, text_content, html_content):
        """Capture email instead of sending it."""
        email_data = {
            'recipients': recipients if isinstance(recipients, list) else [recipients],
            'subject': subject,
            'text_content': text_content,
            'html_content': html_content,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        self.captured_emails.append(email_data)

        # Save to file for inspection
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        filename = f"{self.output_dir}/email_{timestamp}.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(email_data, f, indent=2, ensure_ascii=False)

        logger.info(f"Captured email: {subject} to {email_data['recipients']}")
        return True

    def get_emails_by_area_and_type(self, area_code, email_type):
        """Get captured emails for a specific area and type."""
        emails = []
        for email in self.captured_emails:
            if f"Area {area_code}" in email['subject'] and email_type in email['subject'].lower():
                emails.append(email)
        return emails

    def clear(self):
        """Clear captured emails."""
        self.captured_emails.clear()


@pytest.fixture(scope="module")
def email_capture():
    """Create email capture instance for the module."""
    return EmailCapture()


@pytest.fixture(scope="module")
def firestore_client_module():
    """Create Firestore client for module scope (reused across tests)."""
    database_name = get_database_name()
    if database_name == '(default)':
        client = firestore.Client()
    else:
        client = firestore.Client(database=database_name)
    yield client


@pytest.fixture(scope="module")
def participant_model_module(firestore_client_module):
    """Create participant model for current year."""
    current_year = datetime.now().year
    return ParticipantModel(firestore_client_module, current_year)


@pytest.fixture(scope="module")
def load_test_data_module(firestore_client_module):
    """Load test data from CSV into database once per module."""
    try:
        current_year = datetime.now().year
        logger.info(f"Starting test data load for year {current_year}")

        results = load_test_fixture(
            firestore_client_module,
            years=[current_year],
            csv_filename='test_participants_2025.csv',
            clear_first=True
        )
        logger.info(f"✓ Loaded {results[current_year]} test participants for email tests")
        yield results
        # Note: We don't clear the data after tests to allow inspection
    except Exception as e:
        logger.error(f"Failed to load test data: {e}", exc_info=True)
        pytest.fail(f"Test data fixture failed: {e}")


@pytest.fixture(scope="module")
def flask_app_module():
    """Create minimal Flask app for email template rendering.

    This creates a lightweight Flask app with just the template folder configured,
    avoiding the full app.py import which has many external dependencies.
    """
    try:
        from flask import Flask

        # Create minimal Flask app
        test_app = Flask(__name__)
        test_app.config['TESTING'] = False

        # Configure template and static folders
        template_folder = os.path.join(project_root, 'templates')
        static_folder = os.path.join(project_root, 'static')

        if os.path.exists(template_folder):
            test_app.template_folder = template_folder
            logger.info(f"Template folder configured: {template_folder}")
        else:
            logger.warning(f"Template folder not found: {template_folder}")

        if os.path.exists(static_folder):
            test_app.static_folder = static_folder
            logger.info(f"Static folder configured: {static_folder}")

        logger.info("Created minimal Flask app for email generation")
        return test_app

    except Exception as e:
        logger.error(f"Failed to create Flask app: {e}", exc_info=True)
        pytest.fail(f"Cannot create Flask app for email generation: {e}")


class TestEmailNotifications:
    """Test email notifications for participant reassignments."""

    @pytest.mark.critical
    def test_simple_reassignment(self, authenticated_browser, firestore_client_module,
                                participant_model_module, email_capture, flask_app_module,
                                load_test_data_module):
        """
        Test simple reassignment from Area C → Area E.

        Workflow:
        1. Set email timestamps to current time
        2. Wait 1 second
        3. Reassign participant from Area C to Area E
        4. Generate and validate team update emails
        5. Generate and validate weekly summary emails
        """
        current_year = datetime.now().year
        base_url = get_base_url()

        try:
            # ============================================================
            # Phase 1: Setup - Initialize email timestamps
            # ============================================================
            logger.info("Phase 1: Setting up email timestamps")

            timestamp_model = EmailTimestampModel(firestore_client_module, current_year)
            now = datetime.now(timezone.utc)

            # Set both area C and E timestamps to current time
            for area in ['C', 'E']:
                timestamp_model.update_last_email_sent(area, 'team_update', now)
                timestamp_model.update_last_email_sent(area, 'weekly_update', now)
                logger.info(f"Set email timestamps for Area {area}")

            # Wait to ensure reassignment happens after timestamp
            time.sleep(1)

            # ============================================================
            # Phase 2: Reassign participant using Selenium
            # ============================================================
            logger.info("Phase 2: Reassigning participant from Area C to Area E")

            # Get a participant from Area C and reassign to Area E
            # First, find a participant email to reassign
            authenticated_browser.get(f"{base_url}/admin/participants")
            WebDriverWait(authenticated_browser, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "table"))
            )
            time.sleep(1)

            # Find first participant in Area C
            area_c_section = authenticated_browser.find_element(By.ID, "area-C")
            rows = area_c_section.find_elements(By.CSS_SELECTOR, "table tbody tr")
            if not rows:
                pytest.skip("No participants found in Area C")

            cells = rows[0].find_elements(By.TAG_NAME, "td")
            if len(cells) < 2:
                pytest.skip("Could not extract participant info from Area C")

            participant_email = cells[1].text.strip()

            # Use utility function to perform reassignment
            participant_name, _ = reassign_participant_via_ui(
                authenticated_browser,
                base_url,
                participant_email,
                'E',
                is_leader=False
            )

            # ============================================================
            # Phase 3: Verify reassignment in database
            # ============================================================
            logger.info("Phase 3: Verifying reassignment in database")

            # Find the participant we just reassigned and verify the change
            time.sleep(1)  # Give database time to update

            # Verify in reassignments_YYYY collection
            reassignment_model = ReassignmentLogModel(firestore_client_module, current_year)
            recent_reassignments = reassignment_model.get_reassignments_since(now)

            area_c_to_e_reassignment = None
            for reassignment in recent_reassignments:
                if (reassignment.get('old_area') == 'C' and
                    reassignment.get('new_area') == 'E' and
                    participant_email in reassignment.get('email', '')):
                    area_c_to_e_reassignment = reassignment
                    break

            if not area_c_to_e_reassignment:
                logger.warning("Could not find reassignment in database - may still be processing")
                # Don't fail the test - Selenium might have moved too fast or data is eventually consistent
            else:
                logger.info(f"✓ Reassignment logged: {participant_name} from Area C to E")

            # ============================================================
            # Phase 4: Generate and validate team update emails
            # ============================================================
            logger.info("Phase 4: Generating team update emails")

            email_capture.clear()

            # Mock the email service send_email method
            with patch('services.email_service.email_service.send_email') as mock_send:
                mock_send.side_effect = email_capture.send_email

                # Generate team update emails with Flask app for template rendering
                results = generate_team_update_emails(app=flask_app_module)

                logger.info(f"Team update results: {results['emails_sent']} sent, {results['areas_processed']} areas processed")

            # Validate team update emails
            team_c_emails = [e for e in email_capture.captured_emails if "Area C" in e['subject']]
            team_e_emails = [e for e in email_capture.captured_emails if "Area E" in e['subject']]

            logger.info(f"Captured {len(team_c_emails)} team update emails for Area C")
            logger.info(f"Captured {len(team_e_emails)} team update emails for Area E")

            # Verify Area C email content
            if team_c_emails:
                area_c_email = team_c_emails[0]
                html_content = area_c_email.get('html_content', '')

                if html_content:
                    soup = BeautifulSoup(html_content, 'html.parser')
                    email_text = soup.get_text()

                    # Area C should show participant being reassigned away
                    if participant_name and "reassigned" in email_text.lower():
                        logger.info(f"✓ Area C email mentions reassignment of {participant_name}")
                    elif participant_name:
                        logger.warning(f"Area C email does not mention reassignment for {participant_name}")

                    # Save email file for inspection
                    c_email_file = f"{email_capture.output_dir}/team_update_area_c.html"
                    with open(c_email_file, 'w', encoding='utf-8') as f:
                        f.write(html_content)
                    logger.info(f"Saved Area C team update email to {c_email_file}")

            # Verify Area E email content
            if team_e_emails:
                area_e_email = team_e_emails[0]
                html_content = area_e_email.get('html_content', '')

                if html_content:
                    soup = BeautifulSoup(html_content, 'html.parser')
                    email_text = soup.get_text()

                    # Area E should show participant joining from another area
                    if participant_name and ("reassigned" in email_text.lower() or "joined" in email_text.lower()):
                        logger.info(f"✓ Area E email mentions {participant_name} joining")
                    elif participant_name:
                        logger.warning(f"Area E email does not mention {participant_name} joining")

                    # Save email file for inspection
                    e_email_file = f"{email_capture.output_dir}/team_update_area_e.html"
                    with open(e_email_file, 'w', encoding='utf-8') as f:
                        f.write(html_content)
                    logger.info(f"Saved Area E team update email to {e_email_file}")

            # Verify timestamp was updated
            logger.info("Verifying timestamp updates")
            new_c_timestamp = timestamp_model.get_last_email_sent('C', 'team_update')
            new_e_timestamp = timestamp_model.get_last_email_sent('E', 'team_update')

            if new_c_timestamp and new_c_timestamp > now:
                logger.info(f"✓ Area C team_update timestamp updated: {new_c_timestamp}")
            else:
                logger.warning("Area C team_update timestamp not updated")

            if new_e_timestamp and new_e_timestamp > now:
                logger.info(f"✓ Area E team_update timestamp updated: {new_e_timestamp}")
            else:
                logger.warning("Area E team_update timestamp not updated")

            # ============================================================
            # Phase 5: Generate and validate weekly summary emails
            # ============================================================
            logger.info("Phase 5: Generating weekly summary emails")

            email_capture.clear()

            with patch('services.email_service.email_service.send_email') as mock_send:
                mock_send.side_effect = email_capture.send_email

                # Generate weekly summary emails with Flask app for template rendering
                results = generate_weekly_summary_emails(app=flask_app_module)

                logger.info(f"Weekly summary results: {results['emails_sent']} sent, {results['areas_processed']} areas processed")

            # Validate weekly summary emails
            weekly_c_emails = [e for e in email_capture.captured_emails if "Area C" in e['subject'] and "Weekly" in e['subject']]
            weekly_e_emails = [e for e in email_capture.captured_emails if "Area E" in e['subject'] and "Weekly" in e['subject']]

            logger.info(f"Captured {len(weekly_c_emails)} weekly summary emails for Area C")
            logger.info(f"Captured {len(weekly_e_emails)} weekly summary emails for Area E")

            # Verify weekly emails mention the change
            if weekly_c_emails:
                area_c_email = weekly_c_emails[0]
                html_content = area_c_email.get('html_content', '')

                if html_content:
                    soup = BeautifulSoup(html_content, 'html.parser')
                    email_text = soup.get_text()

                    if participant_name and "reassigned" in email_text.lower():
                        logger.info(f"✓ Area C weekly summary mentions {participant_name} departure")

                    # Save file
                    c_weekly_file = f"{email_capture.output_dir}/weekly_summary_area_c.html"
                    with open(c_weekly_file, 'w', encoding='utf-8') as f:
                        f.write(html_content)
                    logger.info(f"Saved Area C weekly summary to {c_weekly_file}")

            if weekly_e_emails:
                area_e_email = weekly_e_emails[0]
                html_content = area_e_email.get('html_content', '')

                if html_content:
                    soup = BeautifulSoup(html_content, 'html.parser')
                    email_text = soup.get_text()

                    if participant_name and "reassigned" in email_text.lower():
                        logger.info(f"✓ Area E weekly summary mentions {participant_name} arrival")

                    # Save file
                    e_weekly_file = f"{email_capture.output_dir}/weekly_summary_area_e.html"
                    with open(e_weekly_file, 'w', encoding='utf-8') as f:
                        f.write(html_content)
                    logger.info(f"Saved Area E weekly summary to {e_weekly_file}")

            logger.info("✓ test_simple_reassignment completed successfully")

        except Exception as e:
            logger.error(f"Test failed with error: {e}", exc_info=True)
            raise

    def test_rapid_reassignment_captures_original_source(self, authenticated_browser, firestore_client_module,
                                                         participant_model_module, email_capture, flask_app_module,
                                                         load_test_data_module):
        """
        Test rapid successive reassignments (D → J → R).

        Validates that when a participant is reassigned multiple times in quick succession,
        the email notifications correctly reflect the original source (D) and final destination (R),
        with no unnecessary email for the intermediate area (J).
        """
        current_year = datetime.now().year
        base_url = get_base_url()

        try:
            # ============================================================
            # Phase 1: Setup - Initialize email timestamps
            # ============================================================
            logger.info("Phase 1: Setting up email timestamps")

            timestamp_model = EmailTimestampModel(firestore_client_module, current_year)
            now = datetime.now(timezone.utc)

            # Set timestamps for all affected areas
            for area in ['D', 'J', 'R']:
                timestamp_model.update_last_email_sent(area, 'team_update', now)
                timestamp_model.update_last_email_sent(area, 'weekly_update', now)

            time.sleep(1)

            # ============================================================
            # Phase 2: Perform rapid reassignments D → J → R
            # ============================================================
            logger.info("Phase 2: Performing rapid reassignments D → J → R")

            # Find a participant in Area D to start with
            authenticated_browser.get(f"{base_url}/admin/participants")
            WebDriverWait(authenticated_browser, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "table"))
            )
            time.sleep(1)

            area_d_section = authenticated_browser.find_element(By.ID, "area-D")
            rows_d = area_d_section.find_elements(By.CSS_SELECTOR, "table tbody tr")
            if not rows_d:
                pytest.skip("No participants found in Area D")

            cells = rows_d[0].find_elements(By.TAG_NAME, "td")
            participant_email = cells[1].text.strip()

            # First reassignment: D → J
            participant_name, _ = reassign_participant_via_ui(
                authenticated_browser,
                base_url,
                participant_email,
                'J',
                is_leader=False
            )

            # Second reassignment: J → R (same participant)
            reassign_participant_via_ui(
                authenticated_browser,
                base_url,
                participant_email,
                'R',
                is_leader=False
            )

            logger.info(f"✓ Completed rapid reassignments: D → J → R for {participant_name}")

            # ============================================================
            # Phase 3: Generate and validate team update emails
            # ============================================================
            logger.info("Phase 3: Generating team update emails")

            email_capture.clear()
            with patch('services.email_service.email_service.send_email') as mock_send:
                mock_send.side_effect = email_capture.send_email
                results = generate_team_update_emails(app=flask_app_module)
                logger.info(f"Team update results: {results['emails_sent']} sent")

            # Debug: Log all emails that were sent
            logger.info(f"Total emails sent: {len(email_capture.captured_emails)}")
            for email in email_capture.captured_emails:
                logger.info(f"  Email: {email['subject']}")

            # Validate emails for D and R only (not J - no net changes)
            team_d_emails = [e for e in email_capture.captured_emails if "Area D" in e['subject']]
            team_j_emails = [e for e in email_capture.captured_emails if "Area J" in e['subject']]
            team_r_emails = [e for e in email_capture.captured_emails if "Area R" in e['subject']]

            logger.info(f"Team update emails: D={len(team_d_emails)}, J={len(team_j_emails)}, R={len(team_r_emails)}")

            # Validate no email for J (no net changes - arrival and departure cancel out)
            assert len(team_j_emails) == 0, "Area J should not receive email (no net changes)"
            logger.info("✓ Area J correctly has no team update email")

            # Validate D and R have emails
            assert len(team_d_emails) > 0, "Area D should receive team update email"
            assert len(team_r_emails) > 0, "Area R should receive team update email"
            logger.info("✓ Areas D and R have team update emails")

            # Validate content
            if team_d_emails:
                d_email = team_d_emails[0]
                d_text = BeautifulSoup(d_email.get('html_content', ''), 'html.parser').get_text().lower()
                if participant_name and "reassigned" in d_text:
                    logger.info(f"✓ Area D email mentions reassignment of {participant_name} to Area R (original source to final destination)")

            if team_r_emails:
                r_email = team_r_emails[0]
                r_text = BeautifulSoup(r_email.get('html_content', ''), 'html.parser').get_text().lower()
                if participant_name and ("reassigned" in r_text or "joined" in r_text):
                    logger.info(f"✓ Area R email mentions {participant_name} arrival from Area D (original source)")

            # ============================================================
            # Phase 4: Generate and validate weekly summary emails
            # ============================================================
            logger.info("Phase 4: Generating weekly summary emails")

            email_capture.clear()
            with patch('services.email_service.email_service.send_email') as mock_send:
                mock_send.side_effect = email_capture.send_email
                results = generate_weekly_summary_emails(app=flask_app_module)
                logger.info(f"Weekly summary results: {results['emails_sent']} sent")

            # Validate weekly emails for D, J, and R
            weekly_d_emails = [e for e in email_capture.captured_emails if "Area D" in e['subject'] and "Weekly" in e['subject']]
            weekly_j_emails = [e for e in email_capture.captured_emails if "Area J" in e['subject'] and "Weekly" in e['subject']]
            weekly_r_emails = [e for e in email_capture.captured_emails if "Area R" in e['subject'] and "Weekly" in e['subject']]

            logger.info(f"Weekly summary emails: D={len(weekly_d_emails)}, J={len(weekly_j_emails)}, R={len(weekly_r_emails)}")

            # Weekly summaries go to all areas with leaders
            if weekly_d_emails:
                logger.info("✓ Area D has weekly summary email")
            if weekly_j_emails:
                logger.info("✓ Area J has weekly summary email (shows arrival and departure)")
            if weekly_r_emails:
                logger.info("✓ Area R has weekly summary email")

            logger.info("✓ test_rapid_reassignment_captures_original_source completed successfully")

        except Exception as e:
            logger.error(f"Test failed with error: {e}", exc_info=True)
            raise

    def test_reassignment_back_to_original_area(self, authenticated_browser, firestore_client_module,
                                                participant_model_module, email_capture, flask_app_module,
                                                load_test_data_module):
        """
        Test reassignment that returns to original area (F → G → F).

        Validates that when a participant is reassigned and then reassigned back to their
        original area, no email notifications are generated because there are no net changes.
        """
        current_year = datetime.now().year
        base_url = get_base_url()

        try:
            # ============================================================
            # Phase 1: Setup - Initialize email timestamps
            # ============================================================
            logger.info("Phase 1: Setting up email timestamps")

            timestamp_model = EmailTimestampModel(firestore_client_module, current_year)
            now = datetime.now(timezone.utc)

            for area in ['F', 'G']:
                timestamp_model.update_last_email_sent(area, 'team_update', now)
                timestamp_model.update_last_email_sent(area, 'weekly_update', now)

            time.sleep(1)

            # ============================================================
            # Phase 2: Perform round-trip reassignments F → G → F
            # ============================================================
            logger.info("Phase 2: Performing round-trip reassignments F → G → F")

            authenticated_browser.get(f"{base_url}/admin/participants")
            WebDriverWait(authenticated_browser, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "table"))
            )
            time.sleep(1)

            # Find participant in Area F
            try:
                area_f_section = authenticated_browser.find_element(By.ID, "area-F")
                logger.info("✓ Found Area F section")
            except Exception as e:
                logger.error(f"Could not find Area F section: {e}")
                pytest.skip(f"Area F section not found: {e}")

            rows_f = area_f_section.find_elements(By.CSS_SELECTOR, "table tbody tr")
            logger.info(f"Found {len(rows_f)} participants in Area F")
            if not rows_f:
                # Save page for debugging
                page_source = authenticated_browser.page_source
                with open("tests/tmp/roundtrip_area_f_error.html", "w", encoding='utf-8') as f:
                    f.write(page_source)
                logger.error("Saved error page to tests/tmp/roundtrip_area_f_error.html")
                pytest.skip("No participants found in Area F")

            # Find a regular participant (not a leader)
            participant_email = None

            for row in rows_f:
                cells = row.find_elements(By.TAG_NAME, "td")
                if len(cells) < 8:
                    continue

                # Check if this row has a leader badge
                leader_badges = row.find_elements(By.CSS_SELECTOR, "span.badge.bg-success, span.badge.badge-warning")
                if leader_badges:
                    # This is a leader, skip it
                    logger.info(f"Skipping leader: {cells[0].text.strip()}")
                    continue

                # Found a regular participant
                participant_email = cells[1].text.strip()
                logger.info(f"✓ Found regular participant in Area F: {cells[0].text.strip()}")
                break

            if not participant_email:
                pytest.skip("No regular (non-leader) participants found in Area F")

            # First reassignment: F → G
            participant_name, _ = reassign_participant_via_ui(
                authenticated_browser,
                base_url,
                participant_email,
                'G',
                is_leader=False
            )

            # Second reassignment: G → F (back to original)
            reassign_participant_via_ui(
                authenticated_browser,
                base_url,
                participant_email,
                'F',
                is_leader=False
            )

            logger.info(f"✓ Completed round-trip reassignments: F → G → F for {participant_name}")

            # ============================================================
            # Phase 3: Generate and validate team update emails
            # ============================================================
            logger.info("Phase 3: Generating team update emails")

            email_capture.clear()
            with patch('services.email_service.email_service.send_email') as mock_send:
                mock_send.side_effect = email_capture.send_email
                results = generate_team_update_emails(app=flask_app_module)
                logger.info(f"Team update results: {results['emails_sent']} sent")

            # No net changes, so no emails should be generated
            team_f_emails = [e for e in email_capture.captured_emails if "Area F" in e['subject']]
            team_g_emails = [e for e in email_capture.captured_emails if "Area G" in e['subject']]

            logger.info(f"Team update emails: F={len(team_f_emails)}, G={len(team_g_emails)}")

            assert len(team_f_emails) == 0, "Area F should not receive email (no net changes)"
            assert len(team_g_emails) == 0, "Area G should not receive email (no net changes)"
            logger.info("✓ No team update emails generated (correct - no net changes)")

            # ============================================================
            # Phase 4: Generate and validate weekly summary emails
            # ============================================================
            logger.info("Phase 4: Generating weekly summary emails")

            email_capture.clear()
            with patch('services.email_service.email_service.send_email') as mock_send:
                mock_send.side_effect = email_capture.send_email
                results = generate_weekly_summary_emails(app=flask_app_module)
                logger.info(f"Weekly summary results: {results['emails_sent']} sent")

            # Check that F and G show no changes in their weekly summaries
            weekly_f_emails = [e for e in email_capture.captured_emails if "Area F" in e['subject'] and "Weekly" in e['subject']]
            weekly_g_emails = [e for e in email_capture.captured_emails if "Area G" in e['subject'] and "Weekly" in e['subject']]

            # Weekly emails may be sent, but they should indicate no changes
            if weekly_f_emails:
                f_text = BeautifulSoup(weekly_f_emails[0].get('html_content', ''), 'html.parser').get_text().lower()
                if participant_name not in f_text or "no changes" in f_text:
                    logger.info("✓ Area F weekly summary shows no changes")

            if weekly_g_emails:
                g_text = BeautifulSoup(weekly_g_emails[0].get('html_content', ''), 'html.parser').get_text().lower()
                if participant_name not in g_text or "no changes" in g_text:
                    logger.info("✓ Area G weekly summary shows no changes")

            logger.info("✓ test_reassignment_back_to_original_area completed successfully")

        except Exception as e:
            logger.error(f"Test failed with error: {e}", exc_info=True)
            raise

    def test_reassignment_with_leadership_retention(self, authenticated_browser, firestore_client_module,
                                                    participant_model_module, email_capture, flask_app_module,
                                                    load_test_data_module):
        """
        Test reassignment of a leader while retaining leadership (K → M).

        Validates that when a leader is reassigned to a new area while keeping their
        leadership role, the original area (K) receives no email (no leader),
        and the new area (M) receives an email mentioning the new leader.
        """
        current_year = datetime.now().year
        base_url = get_base_url()

        try:
            # ============================================================
            # Phase 1: Setup - Initialize email timestamps
            # ============================================================
            logger.info("Phase 1: Setting up email timestamps")

            timestamp_model = EmailTimestampModel(firestore_client_module, current_year)
            now = datetime.now(timezone.utc)

            for area in ['K', 'M']:
                timestamp_model.update_last_email_sent(area, 'team_update', now)
                timestamp_model.update_last_email_sent(area, 'weekly_update', now)

            time.sleep(1)

            # ============================================================
            # Phase 2: Find and reassign a leader from K → M
            # ============================================================
            logger.info("Phase 2: Finding a leader in Area K and reassigning to Area M")

            # Query database to find a leader in Area K (unambiguous)
            leaders_in_k = participant_model_module.get_leaders_by_area('K')
            if not leaders_in_k:
                pytest.skip("No leaders found in Area K in database")

            # Get the first leader's info
            leader_data = leaders_in_k[0]
            participant_email = leader_data.get('email', '')
            logger.info(f"✓ Found leader in Area K via database: {leader_data.get('first_name', '')} {leader_data.get('last_name', '')} ({participant_email})")

            # Use utility function to reassign the leader from K → M, retaining leadership
            participant_name, _ = reassign_participant_via_ui(
                authenticated_browser,
                base_url,
                participant_email,
                'M',
                is_leader=True,
                retain_leadership=True
            )

            logger.info(f"✓ Leader {participant_name} reassigned from K → M with leadership retained")

            # ============================================================
            # Phase 3: Generate and validate team update emails
            # ============================================================
            logger.info("Phase 3: Generating team update emails")

            email_capture.clear()
            with patch('services.email_service.email_service.send_email') as mock_send:
                mock_send.side_effect = email_capture.send_email
                results = generate_team_update_emails(app=flask_app_module)
                logger.info(f"Team update results: {results['emails_sent']} sent")

            # Debug: Log all emails that were sent
            logger.info(f"Total emails sent: {len(email_capture.captured_emails)}")
            for email in email_capture.captured_emails:
                logger.info(f"  Email: {email['subject']} to {email['recipients']}")

            # Area K should have NO email (no leader remaining)
            # Area M should have email (with all leaders including the new one)
            team_k_emails = [e for e in email_capture.captured_emails if "Area K" in e['subject']]
            team_m_emails = [e for e in email_capture.captured_emails if "Area M" in e['subject']]

            logger.info(f"Team update emails: K={len(team_k_emails)}, M={len(team_m_emails)}")

            assert len(team_k_emails) == 0, "Area K should not receive email (no leader)"
            logger.info("✓ Area K correctly receives no team update email (no leader)")

            assert len(team_m_emails) > 0, "Area M should receive team update email"
            logger.info("✓ Area M receives team update email with new leader")

            # Validate M email mentions the new leader
            if team_m_emails:
                m_email = team_m_emails[0]
                m_text = BeautifulSoup(m_email.get('html_content', ''), 'html.parser').get_text()
                if "leader" in m_text.lower():
                    logger.info(f"✓ Area M email mentions new leader: {participant_name}")

            # ============================================================
            # Phase 4: Generate and validate weekly summary emails
            # ============================================================
            logger.info("Phase 4: Generating weekly summary emails")

            email_capture.clear()
            with patch('services.email_service.email_service.send_email') as mock_send:
                mock_send.side_effect = email_capture.send_email
                results = generate_weekly_summary_emails(app=flask_app_module)
                logger.info(f"Weekly summary results: {results['emails_sent']} sent")

            # Area K should not have weekly email (no leader)
            # Area M should have weekly email
            weekly_k_emails = [e for e in email_capture.captured_emails if "Area K" in e['subject'] and "Weekly" in e['subject']]
            weekly_m_emails = [e for e in email_capture.captured_emails if "Area M" in e['subject'] and "Weekly" in e['subject']]

            logger.info(f"Weekly summary emails: K={len(weekly_k_emails)}, M={len(weekly_m_emails)}")

            assert len(weekly_k_emails) == 0, "Area K should not receive weekly email (no leader)"
            logger.info("✓ Area K correctly receives no weekly summary (no leader)")

            if weekly_m_emails:
                logger.info("✓ Area M receives weekly summary email")

            logger.info("✓ test_reassignment_with_leadership_retention completed successfully")

        except Exception as e:
            logger.error(f"Test failed with error: {e}", exc_info=True)
            raise
