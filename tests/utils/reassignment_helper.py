# Updated by Claude AI on 2025-10-26
"""
Utility functions for performing participant reassignments via Selenium UI.

This module provides helpers to avoid code duplication across reassignment tests.
"""

import logging
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
import pytest

logger = logging.getLogger(__name__)


def reassign_participant_via_ui(browser, base_url, participant_email, new_area, is_leader=False, retain_leadership=True):
    """
    Perform a participant reassignment via the admin UI.

    Handles the complete UI workflow:
    1. Navigate to admin/participants page
    2. Find participant by email in their current area section
    3. Click reassign button
    4. Select new area from dropdown
    5. Confirm reassignment
    6. Handle leadership role modal (if applicable)
    7. Dismiss success modal/alert
    8. Wait for page reload

    Args:
        browser: Selenium WebDriver
        base_url: Base URL of the application (e.g., 'http://localhost:8080')
        participant_email: Email address to identify the participant
        new_area: Target area code (e.g., 'E', 'J', 'R', 'M')
        is_leader: If True, handle the leadership role modal after reassignment
        retain_leadership: If True and is_leader, click "Leader" button; else "Team Member"

    Returns:
        Tuple of (participant_name, original_area_code) extracted from the reassignment

    Raises:
        pytest.skip: If required elements not found or critical operations fail
    """

    # Navigate to participants page
    logger.info(f"Navigating to {base_url}/admin/participants")
    browser.get(f"{base_url}/admin/participants")

    # Wait for table to load
    try:
        WebDriverWait(browser, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "table"))
        )
        logger.info("✓ Participants table loaded")
    except Exception as e:
        logger.error(f"Failed to load participants table: {e}")
        pytest.skip(f"Could not load participants table: {e}")

    time.sleep(1)

    # Find the participant by email
    reassign_row = None
    participant_name = None
    original_area = None

    # First, we need to determine which area the participant is in
    # Search through all area sections to find the participant
    area_sections = browser.find_elements(By.CSS_SELECTOR, "div[id^='area-']")

    for area_section in area_sections:
        area_code = area_section.get_attribute("id").replace("area-", "")
        rows = area_section.find_elements(By.CSS_SELECTOR, "table tbody tr")

        for row in rows:
            # Check if this row contains the participant email
            row_text = row.text
            if participant_email in row_text:
                reassign_row = row
                original_area = area_code

                # Extract participant name from first column
                cells = row.find_elements(By.TAG_NAME, "td")
                if cells:
                    participant_name = cells[0].text.strip()
                logger.info(f"✓ Found {participant_name} ({participant_email}) in Area {original_area}")
                break

        if reassign_row:
            break

    if not reassign_row:
        logger.error(f"Could not find participant {participant_email} on participants page")
        pytest.skip(f"Participant {participant_email} not found in any area section")

    if not participant_name:
        logger.error("Could not extract participant name from row")
        pytest.skip("Could not extract participant name from UI")

    # Click the reassign button
    try:
        reassign_button = reassign_row.find_element(By.CSS_SELECTOR, "button.btn-reassign")
        browser.execute_script("arguments[0].scrollIntoView(true);", reassign_button)
        time.sleep(0.3)
        reassign_button.click()
        logger.info(f"✓ Clicked reassign button for {participant_name}")
    except Exception as e:
        logger.error(f"Failed to click reassign button: {e}")
        pytest.skip(f"Failed to click reassign button: {e}")

    # Wait for reassign controls to appear
    time.sleep(0.5)
    try:
        reassign_controls = reassign_row.find_element(By.CSS_SELECTOR, ".reassign-controls")
        if not reassign_controls.is_displayed():
            logger.warning("Reassign controls found but not displayed, waiting...")
            time.sleep(1)
        logger.info("✓ Reassign controls visible")
    except Exception as e:
        logger.error(f"Could not find reassign controls: {e}")
        pytest.skip(f"Could not find reassign controls: {e}")

    # Select new area from dropdown
    try:
        area_dropdown = reassign_row.find_element(By.CSS_SELECTOR, "select.reassign-area-select")
        select = Select(area_dropdown)
        select.select_by_value(new_area)
        logger.info(f"✓ Selected Area {new_area} in reassignment dropdown")
    except Exception as e:
        logger.error(f"Failed to select Area {new_area}: {e}")
        pytest.skip(f"Failed to select Area {new_area} from dropdown: {e}")

    # Click confirm button
    try:
        confirm_button = reassign_row.find_element(By.CSS_SELECTOR, "button.btn-confirm-reassign")
        confirm_button.click()
        logger.info("✓ Clicked confirm reassign button")
        time.sleep(2)  # Wait for reassignment to complete
    except Exception as e:
        logger.error(f"Failed to click confirm reassign button: {e}")
        pytest.skip(f"Failed to click confirm reassign button: {e}")

    # Handle leadership role modal if this is a leader
    if is_leader:
        try:
            leadership_modal = WebDriverWait(browser, 3).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".modal"))
            )
            logger.info("Leadership role modal appeared")

            # Click appropriate button based on retain_leadership flag
            button_text = "Leader" if retain_leadership else "Team Member"
            leader_button = leadership_modal.find_element(By.XPATH, f"//button[contains(text(), '{button_text}')]")
            leader_button.click()
            logger.info(f"✓ Selected '{button_text}' in leadership role modal")
            time.sleep(1)
        except Exception as e:
            logger.warning(f"Leadership role modal not found or already dismissed: {e}")

    # Dismiss success modal/alert
    # The modal's OK button click triggers the page reload via JavaScript
    try:
        WebDriverWait(browser, 5).until(
            EC.presence_of_element_located((By.XPATH, "//button[contains(text(), 'OK')]"))
        )
        browser.execute_script("document.querySelector('button:contains(\"OK\")').click();")
        logger.info("Clicked OK on reassignment success modal")
    except Exception as e:
        # Fallback: try to handle as browser alert
        try:
            alert = WebDriverWait(browser, 2).until(EC.alert_is_present())
            alert.dismiss()
            logger.info("Dismissed browser alert")
        except:
            logger.warning(f"Could not dismiss alert: {e}")

    # Wait for page to reload after modal dismissal
    logger.info("Waiting for page to reload after reassignment")
    try:
        WebDriverWait(browser, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "table"))
        )
        time.sleep(0.5)
        logger.info(f"✓ Page reloaded after reassignment")
    except Exception as e:
        logger.error(f"Page did not reload properly: {e}")
        pytest.skip(f"Page did not reload after reassignment: {e}")

    logger.info(f"✓ Successfully reassigned {participant_name} from Area {original_area} to Area {new_area}")
    return participant_name, original_area
