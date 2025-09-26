# Registration Page Object
# Updated by Claude AI on 2025-09-25

"""
Page object for the main registration form.
Handles all registration form interactions and validation.
"""

from .base_page import BasePage
from selenium.webdriver.common.by import By
import logging
import time

logger = logging.getLogger(__name__)


class RegistrationPage(BasePage):
    """Page object for the registration form."""

    def navigate_to_registration(self):
        """Navigate to the registration page."""
        return self.navigate_to("/")

    def is_registration_form_loaded(self):
        """Check if registration form is loaded."""
        return self.is_element_visible("first_name") or self.is_element_visible("first-name")

    def fill_personal_information(self, participant_data):
        """Fill in personal information fields."""
        personal = participant_data.get('personal', {})

        success = True
        success &= self.safe_send_keys('first_name', personal.get('first_name', ''))
        success &= self.safe_send_keys('last_name', personal.get('last_name', ''))
        success &= self.safe_send_keys('email', personal.get('email', ''))
        success &= self.safe_send_keys('phone', personal.get('phone', ''))

        # Optional secondary phone
        if personal.get('phone2'):
            success &= self.safe_send_keys('phone2', personal.get('phone2', ''))

        return success

    def fill_experience_information(self, participant_data):
        """Fill in experience-related dropdowns."""
        experience = participant_data.get('experience', {})

        success = True

        # Skill level dropdown
        if experience.get('skill_level'):
            success &= self.safe_select_dropdown('skill_level', experience['skill_level'])

        # CBC experience dropdown
        if experience.get('experience'):
            success &= self.safe_select_dropdown('experience', experience['experience'])

        return success

    def select_participation_type(self, participation_type):
        """Select participation type (regular or FEEDER)."""
        if participation_type == 'regular':
            return self.safe_click('regular')
        elif participation_type == 'FEEDER':
            return self.safe_click('feeder')
        else:
            logger.error(f"Unknown participation type: {participation_type}")
            return False

    def select_preferred_area(self, area_code):
        """Select preferred count area."""
        return self.safe_select_dropdown('preferred_area', area_code)

    def set_equipment_preferences(self, participant_data):
        """Set equipment checkboxes."""
        equipment = participant_data.get('equipment', {})

        success = True

        # Binoculars checkbox
        has_binoculars = equipment.get('has_binoculars', False)
        binoculars_element = self.find_element_safely('has_binoculars')
        if binoculars_element and binoculars_element.is_selected() != has_binoculars:
            success &= self.safe_click('has_binoculars')

        # Spotting scope checkbox
        spotting_scope = equipment.get('spotting_scope', False)
        scope_element = self.find_element_safely('spotting_scope')
        if scope_element and scope_element.is_selected() != spotting_scope:
            success &= self.safe_click('spotting_scope')

        return success

    def set_interest_preferences(self, participant_data):
        """Set leadership and scribe interest checkboxes."""
        interests = participant_data.get('interests', {})

        success = True

        # Leadership interest
        interested_in_leadership = interests.get('leadership', False)
        leadership_element = self.find_element_safely('interested_in_leadership')
        if leadership_element and leadership_element.is_selected() != interested_in_leadership:
            success &= self.safe_click('interested_in_leadership')

        # Scribe interest
        interested_in_scribe = interests.get('scribe', False)
        scribe_element = self.find_element_safely('interested_in_scribe')
        if scribe_element and scribe_element.is_selected() != interested_in_scribe:
            success &= self.safe_click('interested_in_scribe')

        return success

    def fill_notes_field(self, notes):
        """Fill the notes to organizers field."""
        if notes:
            return self.safe_send_keys('notes_to_organizers', notes)
        return True

    def fill_complete_registration_form(self, participant_data):
        """
        Fill out the complete registration form.

        Args:
            participant_data: Dictionary with participant information

        Returns:
            bool: True if all fields filled successfully
        """
        logger.info(f"Filling registration form for: {participant_data.get('personal', {}).get('first_name', 'Unknown')}")

        success = True

        # Fill personal information
        success &= self.fill_personal_information(participant_data)

        # Fill experience information
        success &= self.fill_experience_information(participant_data)

        # Select participation type
        participation_type = participant_data.get('participation', {}).get('type', 'regular')
        success &= self.select_participation_type(participation_type)

        # Short delay after participation type selection for any dynamic updates
        time.sleep(0.5)

        # Select preferred area
        area = participant_data.get('participation', {}).get('area', 'UNASSIGNED')
        success &= self.select_preferred_area(area)

        # Set equipment preferences
        success &= self.set_equipment_preferences(participant_data)

        # Set interest preferences (skip for FEEDER participants)
        if participation_type != 'FEEDER':
            success &= self.set_interest_preferences(participant_data)

        # Fill notes field
        notes = participant_data.get('notes', '')
        success &= self.fill_notes_field(notes)

        if success:
            logger.info("Successfully filled all registration form fields")
        else:
            logger.error("Some registration form fields failed to fill")

        return success

    def submit_registration(self):
        """Submit the registration form."""
        # Find submit button with working selectors only
        submit_selectors = [
            (By.CSS_SELECTOR, 'button[type="submit"]'),          # Primary - standard submit button
            (By.CSS_SELECTOR, 'input[type="submit"]'),           # Backup for input buttons
            (By.XPATH, '//button[contains(text(), "Register")]'), # Backup for text-based
            (By.XPATH, '//input[@value="Register"]')             # Backup for input value
        ]

        for selector in submit_selectors:
            if self.safe_click(selector):
                logger.info("Registration form submitted successfully")
                return True

        logger.error("Failed to find and click submit button")
        return False

    def verify_feeder_constraints(self):
        """
        Verify FEEDER participant constraints are enforced.

        Returns:
            dict: Status of constraint checks
        """
        constraints = {
            'unassigned_disabled': False,
            'leadership_disabled': False
        }

        # Check if UNASSIGNED option is disabled/hidden for FEEDER participants
        area_dropdown = self.find_element_safely('preferred_area')
        if area_dropdown:
            from selenium.webdriver.support.ui import Select
            select = Select(area_dropdown)
            options = [option.get_attribute('value') for option in select.options]
            constraints['unassigned_disabled'] = 'UNASSIGNED' not in options

        # Check if leadership checkbox is disabled
        leadership_element = self.find_element_safely('interested_in_leadership')
        if leadership_element:
            constraints['leadership_disabled'] = not leadership_element.is_enabled()

        return constraints

    def navigate_to_area_leader_info(self):
        """Navigate to area leader information page."""
        # Look for area leader info link
        info_selectors = [
            (By.PARTIAL_LINK_TEXT, 'area leader'),
            (By.LINK_TEXT, 'Area Leader Information'),
            (By.CSS_SELECTOR, 'a[href*="area-leader-info"]')
        ]

        for selector in info_selectors:
            try:
                element = self.find_clickable_element(selector)
                if element:
                    element.click()
                    return self.wait_for_url_contains('area-leader-info')
            except:
                continue

        return False

    def navigate_to_scribe_info(self):
        """Navigate to scribe information page."""
        # Look for scribe info link
        info_selectors = [
            (By.PARTIAL_LINK_TEXT, 'Scribe'),
            (By.LINK_TEXT, 'Scribe Information'),
            (By.CSS_SELECTOR, 'a[href*="scribe-info"]')
        ]

        for selector in info_selectors:
            try:
                element = self.find_clickable_element(selector)
                if element:
                    element.click()
                    return self.wait_for_url_contains('scribe-info')
            except:
                continue

        return False

    def get_form_data(self):
        """
        Extract current form data for validation.

        Returns:
            dict: Current form field values
        """
        form_data = {}

        # Text fields
        text_fields = ['first_name', 'last_name', 'email', 'phone', 'phone2', 'notes_to_organizers']
        for field in text_fields:
            element = self.find_element_safely(field)
            if element:
                form_data[field] = element.get_attribute('value') or ''

        # Dropdown fields
        dropdown_fields = ['skill_level', 'experience', 'preferred_area']
        for field in dropdown_fields:
            element = self.find_element_safely(field)
            if element:
                from selenium.webdriver.support.ui import Select
                select = Select(element)
                try:
                    form_data[field] = select.first_selected_option.get_attribute('value')
                except:
                    form_data[field] = ''

        # Radio buttons (participation type)
        regular_radio = self.find_element_safely('regular')
        feeder_radio = self.find_element_safely('feeder')
        if regular_radio and regular_radio.is_selected():
            form_data['participation_type'] = 'regular'
        elif feeder_radio and feeder_radio.is_selected():
            form_data['participation_type'] = 'FEEDER'
        else:
            form_data['participation_type'] = ''

        # Checkboxes
        checkbox_fields = ['has_binoculars', 'spotting_scope', 'interested_in_leadership', 'interested_in_scribe']
        for field in checkbox_fields:
            element = self.find_element_safely(field)
            if element:
                form_data[field] = element.is_selected()
            else:
                form_data[field] = False

        return form_data

    def verify_form_data_preserved(self, original_data):
        """
        Verify that form data is preserved after navigation.

        Args:
            original_data: Form data before navigation

        Returns:
            dict: Comparison results
        """
        current_data = self.get_form_data()

        results = {
            'preserved': True,
            'differences': {},
            'missing_fields': []
        }

        for field, original_value in original_data.items():
            if field not in current_data:
                results['missing_fields'].append(field)
                results['preserved'] = False
            elif current_data[field] != original_value:
                results['differences'][field] = {
                    'original': original_value,
                    'current': current_data[field]
                }
                results['preserved'] = False

        return results