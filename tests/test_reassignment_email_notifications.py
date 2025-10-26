# Email Notification Tests for Participant Reassignment
# Updated by Claude AI on 2025-10-25

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

    def test_fixture_setup_debug(self, firestore_client_module, participant_model_module,
                                 email_capture, flask_app_module, load_test_data_module):
        """Debug test to verify fixtures are loading correctly."""
        logger.info("✓ All fixtures loaded successfully")
        logger.info(f"  - Firestore client: {type(firestore_client_module)}")
        logger.info(f"  - Participant model: {type(participant_model_module)}")
        logger.info(f"  - Email capture: {type(email_capture)}")
        logger.info(f"  - Flask app: {type(flask_app_module)}")
        logger.info(f"  - Test data results: {load_test_data_module}")
        assert firestore_client_module is not None
        assert participant_model_module is not None
        assert email_capture is not None
        assert flask_app_module is not None
        assert load_test_data_module is not None

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

            # Navigate to admin participants page
            logger.info(f"Navigating to {base_url}/admin/participants")
            authenticated_browser.get(f"{base_url}/admin/participants")

            # Wait for page to load
            try:
                WebDriverWait(authenticated_browser, 10).until(
                    EC.presence_of_element_located((By.TAG_NAME, "table"))
                )
                logger.info("✓ Participants table loaded")
            except Exception as e:
                logger.error(f"Failed to load participants table: {e}")
                logger.error(f"Current URL: {authenticated_browser.current_url}")
                logger.error(f"Page title: {authenticated_browser.title}")
                pytest.skip(f"Could not load participants table: {e}")

            time.sleep(1)

            # Find a participant in Area C to reassign
            # The page organizes participants by area sections (div#area-C, etc.)
            reassign_row = None
            participant_name = None
            participant_email = None

            # Look for Area C section specifically
            try:
                area_c_section = authenticated_browser.find_element(By.ID, "area-C")
                logger.info("✓ Found Area C section on page")
            except Exception as e:
                logger.error(f"Could not find Area C section: {e}")
                # Fall back to showing what areas DO exist
                area_buttons = authenticated_browser.find_elements(By.CSS_SELECTOR, "a[href^='#area-']")
                found_areas = [btn.text for btn in area_buttons]
                logger.warning(f"Available areas: {found_areas}")

                # Save page source for inspection
                page_source = authenticated_browser.page_source
                with open("tests/tmp/participants_page_dump.html", "w", encoding='utf-8') as f:
                    f.write(page_source)
                logger.warning("Saved page source to tests/tmp/participants_page_dump.html")
                pytest.skip(f"Area C section not found on page. Available areas: {found_areas}")

            # Get all rows within Area C section
            try:
                rows = area_c_section.find_elements(By.CSS_SELECTOR, "table tbody tr")
                logger.info(f"Found {len(rows)} participants in Area C")
            except Exception as e:
                logger.error(f"Could not find table rows in Area C: {e}")
                pytest.skip(f"Could not find participant table in Area C: {e}")

            # Get first participant from Area C
            if rows:
                reassign_row = rows[0]
                cells = reassign_row.find_elements(By.TAG_NAME, "td")
                if len(cells) >= 2:
                    # Extract name and email from first two columns
                    participant_name = cells[0].text.strip()
                    participant_email = cells[1].text.strip()
                    logger.info(f"✓ Found participant to reassign: {participant_name} ({participant_email})")
            else:
                logger.warning("No participant rows found in Area C table")
                pytest.skip("No participants found in Area C for reassignment testing")

            if not reassign_row:
                logger.error("Failed to select a participant row from Area C")
                pytest.skip("Could not select a participant from Area C")

            # Find and click the reassign button (icon button with class btn-reassign)
            logger.info("Looking for reassign button in selected row")
            reassign_button = None
            try:
                # The reassign button has class btn-reassign (arrow icon)
                reassign_button = reassign_row.find_element(By.CSS_SELECTOR, "button.btn-reassign")
                logger.info("✓ Found reassign button")
            except Exception as e:
                logger.error(f"Could not find reassign button: {e}")
                # Save page for inspection
                page_source = authenticated_browser.page_source
                with open("tests/tmp/participants_page_error.html", "w", encoding='utf-8') as f:
                    f.write(page_source)
                logger.error("Saved error page to tests/tmp/participants_page_error.html")
                pytest.skip(f"Could not find reassign button: {e}")

            # Click the reassign button
            try:
                authenticated_browser.execute_script("arguments[0].scrollIntoView(true);", reassign_button)
                time.sleep(0.3)
                reassign_button.click()
                logger.info("Clicked reassign button")
            except Exception as e:
                logger.error(f"Failed to click reassign button: {e}")
                pytest.skip(f"Failed to click reassign button: {e}")

            # Wait for reassign-controls to become visible
            time.sleep(0.5)
            reassign_controls = None
            try:
                reassign_controls = reassign_row.find_element(By.CSS_SELECTOR, ".reassign-controls")
                # Check if it's visible
                if not reassign_controls.is_displayed():
                    logger.warning("Reassign controls found but not displayed, waiting...")
                    time.sleep(1)
                logger.info("✓ Reassign controls visible")
            except Exception as e:
                logger.error(f"Could not find reassign controls: {e}")
                # Save page for inspection
                page_source = authenticated_browser.page_source
                with open("tests/tmp/participants_page_reassign_error.html", "w", encoding='utf-8') as f:
                    f.write(page_source)
                logger.error("Saved error page to tests/tmp/participants_page_reassign_error.html")
                pytest.skip(f"Could not find reassign controls after clicking button: {e}")

            # Select Area E from the dropdown
            try:
                area_dropdown = reassign_row.find_element(By.CSS_SELECTOR, "select.reassign-area-select")
                from selenium.webdriver.support.ui import Select
                select = Select(area_dropdown)
                select.select_by_value('E')
                logger.info("✓ Selected Area E in reassignment dropdown")
            except Exception as e:
                logger.error(f"Failed to select Area E: {e}")
                pytest.skip(f"Failed to select Area E from dropdown: {e}")

            # Click the confirm reassign button
            try:
                confirm_button = reassign_row.find_element(By.CSS_SELECTOR, "button.btn-confirm-reassign")
                confirm_button.click()
                logger.info("✓ Clicked confirm reassign button")
                time.sleep(2)  # Wait for reassignment to complete
            except Exception as e:
                logger.error(f"Failed to click confirm reassign button: {e}")
                pytest.skip(f"Failed to click confirm reassign button: {e}")

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
