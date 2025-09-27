# Admin Participants Page Object
# Updated by Claude AI on 2025-09-25

"""
Page object for the admin participants management page.
Handles participant viewing, editing, and management operations.
"""

from .base_page import BasePage
from selenium.webdriver.common.by import By
import logging
import time

logger = logging.getLogger(__name__)


class AdminParticipantsPage(BasePage):
    """Page object for the admin participants management page."""

    def navigate_to_participants(self):
        """Navigate to participants management page."""
        return self.navigate_to("/admin/participants")

    def is_participants_page_loaded(self):
        """Check if participants management page is loaded."""
        indicators = [
            'participants-table',
            (By.CSS_SELECTOR, '.participants-table'),
            (By.CSS_SELECTOR, 'h1:contains("Participants")'),
            (By.CSS_SELECTOR, 'table.table')
        ]

        for indicator in indicators:
            if self.is_element_visible(indicator):
                return True

        return False

    def get_all_participants_from_page(self):
        """
        Extract all participant information displayed on the page.

        Returns:
            list: List of participant dictionaries
        """
        participants = []

        # Look for participants table
        table_selectors = [
            'participants-table',
            (By.CSS_SELECTOR, '.participants-table'),
            (By.CSS_SELECTOR, 'table.table'),
            (By.CSS_SELECTOR, '#participants-table')
        ]

        table = None
        for selector in table_selectors:
            table = self.find_element_safely(selector)
            if table:
                break

        if not table:
            logger.warning("Could not find participants table")
            return participants

        try:
            # Extract participant data from table rows
            rows = table.find_elements(By.CSS_SELECTOR, 'tbody tr')

            for row in rows:
                cells = row.find_elements(By.TAG_NAME, 'td')
                if len(cells) < 3:  # Skip if not enough cells
                    continue

                participant = {}

                # Extract fields based on actual table structure:
                # Name | Email | Cell Phone | Skill Level | Experience | Equipment | Notes | Leader | Scribe | Actions
                try:
                    # Column 1: Name (contains FEEDER indicator if applicable)
                    name_cell = cells[0]
                    try:
                        name_element = name_cell.find_element(By.CSS_SELECTOR, '.participant-name')
                        participant['name'] = name_element.text.strip()
                    except:
                        # Fallback to cell text if specific selector fails
                        participant['name'] = name_cell.text.strip()

                    # Check for FEEDER indicator within name cell
                    feeder_indicators = name_cell.find_elements(By.CSS_SELECTOR, 'div.small.text-muted')
                    participant['participation_type'] = 'FEEDER' if any('FEEDER' in indicator.text for indicator in feeder_indicators) else 'regular'

                    # Check for leader badge within name cell
                    leader_badges = name_cell.find_elements(By.CSS_SELECTOR, 'span.badge.bg-success')
                    participant['is_leader'] = len(leader_badges) > 0

                    # Column 2: Email
                    participant['email'] = cells[1].text.strip()

                    # Column 3: Cell Phone
                    if len(cells) > 2:
                        participant['phone'] = cells[2].text.strip()

                    # Column 4: Skill Level
                    if len(cells) > 3:
                        participant['skill_level'] = cells[3].text.strip()

                    # Column 5: Experience
                    if len(cells) > 4:
                        participant['experience'] = cells[4].text.strip()

                    # Check for FEEDER row styling (alternative detection method)
                    row_classes = row.get_attribute('class') or ''
                    if 'table-info' in row_classes:
                        participant['participation_type'] = 'FEEDER'

                    # Look for action buttons (use XPath for text matching)
                    participant['has_edit_button'] = bool(row.find_elements(By.XPATH, './/button[contains(text(), "Edit")]'))
                    participant['has_delete_button'] = bool(row.find_elements(By.XPATH, './/button[contains(text(), "Delete")]'))

                    # Get row ID for actions
                    participant['row_id'] = row.get_attribute('id') or row.get_attribute('data-participant-id')

                    participants.append(participant)

                except Exception as e:
                    logger.warning(f"Could not extract participant data from row: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error extracting participants data: {e}")

        logger.info(f"Extracted {len(participants)} participants from page")
        return participants

    def get_participants_by_area(self):
        """
        Get participants organized by area.

        Returns:
            dict: Areas as keys, participant lists as values
        """
        participants_by_area = {}
        all_participants = self.get_all_participants_from_page()

        for participant in all_participants:
            area = participant.get('area', 'UNASSIGNED')
            if area not in participants_by_area:
                participants_by_area[area] = []
            participants_by_area[area].append(participant)

        return participants_by_area

    def find_participant_row(self, participant_identifier):
        """
        Find a specific participant row by name, email, or ID.

        Args:
            participant_identifier: Name, email, or participant ID

        Returns:
            WebElement or None: The participant row element
        """
        # Try different strategies to find the participant
        search_strategies = [
            # By data attribute
            (By.CSS_SELECTOR, f'tr[data-participant-id="{participant_identifier}"]'),
            # By ID
            (By.CSS_SELECTOR, f'#{participant_identifier}'),
            # By text content (name or email)
            (By.XPATH, f'//tr[td[contains(text(), "{participant_identifier}")]]')
        ]

        for strategy in search_strategies:
            element = self.find_element_safely(strategy)
            if element:
                return element

        return None

    def delete_participant(self, participant_identifier, reason="Test deletion"):
        """
        Delete a participant.

        Args:
            participant_identifier: How to identify the participant
            reason: Reason for deletion

        Returns:
            bool: Success of deletion
        """
        # Find the participant row
        row = self.find_participant_row(participant_identifier)
        if not row:
            logger.error(f"Could not find participant: {participant_identifier}")
            return False

        # Find delete button in the row
        delete_selectors = [
            (By.CSS_SELECTOR, 'button:contains("Delete")'),
            (By.CSS_SELECTOR, '.delete-participant'),
            (By.CSS_SELECTOR, 'a:contains("Delete")'),
            (By.CSS_SELECTOR, 'i.fa-trash')  # If using font awesome icons
        ]

        delete_button = None
        for selector in delete_selectors:
            try:
                delete_button = row.find_element(*selector)
                break
            except:
                continue

        if not delete_button:
            logger.error(f"Could not find delete button for participant: {participant_identifier}")
            return False

        # Click delete button
        delete_button.click()
        time.sleep(0.5)

        # Handle confirmation dialog if present
        if not self._handle_delete_confirmation(reason):
            return False

        # Wait for page refresh or update
        time.sleep(2)

        # Verify participant is no longer visible
        return not bool(self.find_participant_row(participant_identifier))

    def _handle_delete_confirmation(self, reason):
        """Handle delete confirmation modal/dialog."""
        try:
            # Look for confirmation modal
            modal_selectors = [
                (By.CSS_SELECTOR, '.modal'),
                (By.CSS_SELECTOR, '.delete-confirmation'),
                (By.CSS_SELECTOR, '#delete-modal')
            ]

            modal = None
            for selector in modal_selectors:
                modal = self.find_element_safely(selector, timeout=3)
                if modal:
                    break

            if modal:
                # Fill reason field if present
                reason_field = modal.find_elements(By.CSS_SELECTOR, 'textarea, input[name="reason"]')
                if reason_field:
                    reason_field[0].clear()
                    reason_field[0].send_keys(reason)

                # Click confirm button
                confirm_selectors = [
                    (By.CSS_SELECTOR, 'button:contains("Delete")'),
                    (By.CSS_SELECTOR, 'button:contains("Confirm")'),
                    (By.CSS_SELECTOR, '.confirm-delete'),
                    (By.CSS_SELECTOR, 'input[type="submit"]')
                ]

                for selector in confirm_selectors:
                    confirm_button = modal.find_elements(*selector)
                    if confirm_button:
                        confirm_button[0].click()
                        return True

            else:
                # Handle browser confirmation dialog
                try:
                    alert = self.driver.switch_to.alert
                    alert.accept()
                    return True
                except:
                    # No confirmation dialog, deletion might have proceeded
                    return True

        except Exception as e:
            logger.error(f"Error handling delete confirmation: {e}")

        return False

    def assign_participant_to_area(self, participant_identifier, area_code):
        """
        Assign a participant to a specific area.

        Args:
            participant_identifier: How to identify the participant
            area_code: Target area code

        Returns:
            bool: Success of assignment
        """
        row = self.find_participant_row(participant_identifier)
        if not row:
            return False

        # Look for area assignment dropdown or button
        assignment_selectors = [
            (By.CSS_SELECTOR, 'select[name="area"]'),
            (By.CSS_SELECTOR, '.area-assignment select'),
            (By.CSS_SELECTOR, 'button:contains("Assign")')
        ]

        for selector in assignment_selectors:
            try:
                element = row.find_element(*selector)
                if element.tag_name == 'select':
                    # Dropdown assignment
                    from selenium.webdriver.support.ui import Select
                    select = Select(element)
                    select.select_by_value(area_code)
                    return True
                else:
                    # Button-based assignment (might open modal)
                    element.click()
                    time.sleep(1)
                    # Handle assignment modal if present
                    return self._handle_area_assignment_modal(area_code)
            except:
                continue

        return False

    def _handle_area_assignment_modal(self, area_code):
        """Handle area assignment modal."""
        try:
            # Look for area dropdown in modal
            area_dropdown = self.find_element_safely((By.CSS_SELECTOR, '.modal select[name="area"]'), timeout=3)
            if area_dropdown:
                from selenium.webdriver.support.ui import Select
                select = Select(area_dropdown)
                select.select_by_value(area_code)

                # Click save/assign button
                save_button = self.find_element_safely((By.CSS_SELECTOR, '.modal button:contains("Assign")'))
                if save_button:
                    save_button.click()
                    return True

        except Exception as e:
            logger.error(f"Error handling area assignment modal: {e}")

        return False

    def promote_participant_to_leader(self, participant_identifier, area_code):
        """
        Promote a participant to area leader.

        Args:
            participant_identifier: How to identify the participant
            area_code: Area they should lead

        Returns:
            bool: Success of promotion
        """
        row = self.find_participant_row(participant_identifier)
        if not row:
            return False

        # Look for promotion button or link
        promotion_selectors = [
            (By.CSS_SELECTOR, 'button:contains("Promote")'),
            (By.CSS_SELECTOR, 'a:contains("Make Leader")'),
            (By.CSS_SELECTOR, '.promote-leader')
        ]

        for selector in promotion_selectors:
            try:
                promote_button = row.find_element(*selector)
                promote_button.click()
                time.sleep(1)

                # Handle promotion modal if present
                return self._handle_leader_promotion_modal(area_code)
            except:
                continue

        logger.error(f"Could not find promotion button for participant: {participant_identifier}")
        return False

    def _handle_leader_promotion_modal(self, area_code):
        """Handle leader promotion modal."""
        try:
            # Look for area selection in modal
            area_dropdown = self.find_element_safely((By.CSS_SELECTOR, '.modal select[name="area"]'), timeout=3)
            if area_dropdown:
                from selenium.webdriver.support.ui import Select
                select = Select(area_dropdown)
                select.select_by_value(area_code)

                # Click promote/save button
                promote_button = self.find_element_safely((By.CSS_SELECTOR, '.modal button:contains("Promote")'))
                if promote_button:
                    promote_button.click()
                    time.sleep(2)  # Wait for promotion to complete
                    return True

        except Exception as e:
            logger.error(f"Error handling leader promotion modal: {e}")

        return False

    def demote_leader_to_participant(self, participant_identifier):
        """
        Demote a leader back to regular participant.

        Args:
            participant_identifier: How to identify the leader

        Returns:
            bool: Success of demotion
        """
        row = self.find_participant_row(participant_identifier)
        if not row:
            return False

        # Look for demotion button
        demotion_selectors = [
            (By.CSS_SELECTOR, 'button:contains("Demote")'),
            (By.CSS_SELECTOR, 'a:contains("Remove Leadership")'),
            (By.CSS_SELECTOR, '.demote-leader')
        ]

        for selector in demotion_selectors:
            try:
                demote_button = row.find_element(*selector)
                demote_button.click()
                time.sleep(1)

                # Handle confirmation if present
                self._handle_delete_confirmation("Leader demotion")
                time.sleep(2)
                return True
            except:
                continue

        return False

    def get_area_headers(self):
        """
        Get all area section headers with participant counts.

        Returns:
            dict: Area codes and their participant counts
        """
        area_counts = {}

        # Look for area headers
        header_selectors = [
            (By.CSS_SELECTOR, '.area-header'),
            (By.CSS_SELECTOR, 'h3:contains("Area")'),
            (By.CSS_SELECTOR, '.participant-area')
        ]

        for selector in header_selectors:
            try:
                headers = self.driver.find_elements(*selector)
                for header in headers:
                    text = header.text
                    # Extract area code and count from text like "Area A (5 participants)"
                    import re
                    match = re.search(r'Area (\w+).*?(\d+)', text)
                    if match:
                        area_code = match.group(1)
                        count = int(match.group(2))
                        area_counts[area_code] = count
            except:
                continue

        return area_counts

    def verify_feeder_participant_display(self):
        """
        Verify FEEDER participants are properly displayed and separated.

        Returns:
            dict: FEEDER participant display information
        """
        feeder_info = {
            'feeder_participants_found': False,
            'feeder_section_exists': False,
            'feeder_indicators_present': False
        }

        # Look for FEEDER rows (have class="table-info")
        feeder_rows = self.driver.find_elements(By.CSS_SELECTOR, 'tr.table-info')
        if feeder_rows:
            feeder_info['feeder_participants_found'] = True
            logger.info(f"Found {len(feeder_rows)} FEEDER participant rows")

        # Look for FEEDER text indicators within name cells
        feeder_text_indicators = self.driver.find_elements(By.XPATH, '//div[@class="small text-muted"][contains(text(), "FEEDER")]')
        if feeder_text_indicators:
            feeder_info['feeder_indicators_present'] = True
            logger.info(f"Found {len(feeder_text_indicators)} FEEDER text indicators")

        # Note: There are no separate FEEDER sections in the current HTML structure
        # FEEDER participants are mixed with regular participants, sorted by type then name

        return feeder_info

    def click_export_csv(self):
        """Click the export CSV button on participants page."""
        export_selectors = [
            'export-csv',
            (By.PARTIAL_LINK_TEXT, 'Export'),
            (By.CSS_SELECTOR, 'a[href*="export"]'),
            (By.CSS_SELECTOR, 'button:contains("Export")')
        ]

        for selector in export_selectors:
            if self.safe_click(selector):
                time.sleep(2)  # Wait for download
                return True

        return False

    def delete_participant_by_email_and_name(self, email, first_name, last_name):
        """
        Delete a participant by identity (email + name) for family email support.

        Args:
            email: Participant email
            first_name: Participant first name
            last_name: Participant last name

        Returns:
            bool: Success of deletion
        """
        # Find participant by identity
        participant_row = self._find_participant_by_identity(email, first_name, last_name)
        if not participant_row:
            logger.error(f"Could not find participant: {first_name} {last_name} ({email})")
            return False

        # Find delete button in the row
        delete_selectors = [
            (By.CSS_SELECTOR, 'button[data-action="delete"]'),
            (By.CSS_SELECTOR, '.delete-participant'),
            (By.CSS_SELECTOR, 'a:contains("Delete")'),
            (By.CSS_SELECTOR, 'i.bi-trash, i.fa-trash')  # Bootstrap or Font Awesome icons
        ]

        delete_button = None
        for selector in delete_selectors:
            try:
                delete_button = participant_row.find_element(*selector)
                break
            except:
                continue

        if not delete_button:
            logger.error(f"Could not find delete button for participant: {first_name} {last_name}")
            return False

        # Click delete button
        delete_button.click()
        time.sleep(0.5)

        # Handle confirmation dialog
        if not self._handle_delete_confirmation(f"Test deletion of {first_name} {last_name}"):
            return False

        # Wait for page update
        time.sleep(2)

        # Verify participant is no longer visible
        return not bool(self._find_participant_by_identity(email, first_name, last_name))

    def demote_leader_by_email_and_name(self, email, first_name, last_name):
        """
        Demote a leader by identity (email + name) for family email support.

        Args:
            email: Leader email
            first_name: Leader first name
            last_name: Leader last name

        Returns:
            bool: Success of demotion
        """
        participant_row = self._find_participant_by_identity(email, first_name, last_name)
        if not participant_row:
            logger.error(f"Could not find leader: {first_name} {last_name} ({email})")
            return False

        # Look for demotion button
        demotion_selectors = [
            (By.CSS_SELECTOR, 'button[data-action="demote"]'),
            (By.CSS_SELECTOR, 'button:contains("Demote")'),
            (By.CSS_SELECTOR, '.demote-leader'),
            (By.CSS_SELECTOR, 'a:contains("Remove Leadership")')
        ]

        for selector in demotion_selectors:
            try:
                demote_button = participant_row.find_element(*selector)
                demote_button.click()
                time.sleep(1)

                # Handle confirmation
                self._handle_delete_confirmation(f"Leader demotion: {first_name} {last_name}")
                time.sleep(2)
                return True
            except:
                continue

        logger.error(f"Could not find demotion button for leader: {first_name} {last_name}")
        return False

    def _find_participant_by_identity(self, email, first_name, last_name):
        """
        Find a participant row by full identity for family email support.

        Args:
            email: Participant email
            first_name: Participant first name
            last_name: Participant last name

        Returns:
            WebElement or None: The participant row element
        """
        try:
            # Try to find by data attributes first (most reliable)
            identity_selectors = [
                f'tr[data-participant-email="{email}"][data-participant-first="{first_name}"][data-participant-last="{last_name}"]',
                f'tr[data-email="{email}"][data-first-name="{first_name}"][data-last-name="{last_name}"]'
            ]

            for selector in identity_selectors:
                element = self.find_element_safely((By.CSS_SELECTOR, selector))
                if element:
                    return element

            # Fall back to text-based search
            rows = self.driver.find_elements(By.CSS_SELECTOR, 'table tr')
            for row in rows:
                try:
                    cells = row.find_elements(By.TAG_NAME, 'td')
                    if len(cells) >= 3:  # At least first name, last name, email
                        row_text = row.text.lower()
                        if (first_name.lower() in row_text and
                            last_name.lower() in row_text and
                            email.lower() in row_text):
                            return row
                except:
                    continue

            return None

        except Exception as e:
            logger.error(f"Error finding participant by identity: {e}")
            return None