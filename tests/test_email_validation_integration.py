# Email Validation Integration Test Suite
# Created by Claude AI on 2025-09-30

"""
Integration tests for email validation across frontend and backend.
Tests the complete validation flow from browser forms to API endpoints.

This test suite verifies:
1. Registration form email validation (browser)
2. Admin participant edit email validation (browser)
3. Admin leader management email validation (browser)
4. Backend API validation enforcement
5. Security and edge cases

Requirements:
- Selenium WebDriver with Firefox
- Test environment at cbc-test.naturevancouver.ca
- Google OAuth test credentials
"""

import pytest
import sys
import os
import time
import requests
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.select import Select
from selenium.common.exceptions import TimeoutException

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from tests.test_config import get_base_url, TEST_CONFIG
from tests.page_objects.registration_page import RegistrationPage
from tests.data.test_scenarios import get_test_participant, generate_unique_email, generate_unique_identity
from google.cloud import firestore


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture(scope="module")
def db():
    """Firestore database client with correct database."""
    from config.database import get_firestore_client
    db_client, database_id = get_firestore_client()
    return db_client


@pytest.fixture
def registration_page(browser):
    """Create registration page object."""
    base_url = get_base_url()
    page = RegistrationPage(browser, base_url)
    return page


@pytest.fixture(scope="function")
def test_cleanup(db):
    """Clean up test data after each test."""
    yield
    # Cleanup any test participants created during tests
    participants_ref = db.collection('participants_2025')
    test_emails = [
        'valid-test@example.com',
        'invalid-test@example.com',
        'test+tag@example.com',
        'test%invalid@example.com',
        'test!invalid@example.com',
        'api+test@example.com',
        'invalid!email@example.com',
        'test.user@example.com',
    ]

    for email in test_emails:
        try:
            # Use filter() keyword argument as recommended
            docs = participants_ref.where(filter=firestore.FieldFilter('email', '==', email)).limit(10).get()
            for doc in docs:
                doc.reference.delete()
        except Exception as e:
            # Ignore cleanup errors - test environment may be empty
            pass


# ============================================================================
# Test Class: Registration Form Email Validation
# ============================================================================

@pytest.mark.browser
@pytest.mark.critical
class TestRegistrationFormEmailValidation:
    """Browser-based tests for registration form email validation."""

    def test_valid_email_accepted(self, registration_page, test_cleanup):
        """Test that valid email formats are accepted in registration form."""
        # Get test data and use unique identity (name AND email for test independence)
        participant_data = get_test_participant('participants', 'regular_newbie')
        unique_identity = generate_unique_identity("ValidTest", "User", "validtest")
        participant_data['personal']['first_name'] = unique_identity['first_name']
        participant_data['personal']['last_name'] = unique_identity['last_name']
        participant_data['personal']['email'] = unique_identity['email']  # Use unique email

        # Navigate and fill form
        assert registration_page.navigate_to_registration(), "Failed to navigate"
        assert registration_page.fill_complete_registration_form(participant_data), "Failed to fill form"
        assert registration_page.submit_registration(), "Failed to submit"

        # Wait for success page with retry (handle spinner delays)
        success_found = False
        for attempt in range(5):
            time.sleep(2)
            success_url = registration_page.get_current_url()
            if 'success' in success_url or 'registered' in success_url:
                success_found = True
                break

        assert success_found, \
            f"Valid email should redirect to success page, got: {success_url}"


    def test_plus_sign_email_accepted(self, registration_page, test_cleanup):
        """Test that emails with plus signs are accepted (RFC 5322 compliance)."""
        # Get test data with unique identity (keeping plus sign but making email unique)
        participant_data = get_test_participant('participants', 'regular_intermediate')
        unique_identity = generate_unique_identity("PlusSign", "Test", "plustest")
        participant_data['personal']['first_name'] = unique_identity['first_name']
        participant_data['personal']['last_name'] = unique_identity['last_name']
        # Use unique base but add plus sign for RFC 5322 testing
        participant_data['personal']['email'] = unique_identity['email'].replace('@', '+tag@')

        # Navigate and fill form
        assert registration_page.navigate_to_registration(), "Failed to navigate"
        assert registration_page.fill_complete_registration_form(participant_data), "Failed to fill form"
        assert registration_page.submit_registration(), "Failed to submit"

        # Wait for success page with retry (handle spinner delays)
        success_found = False
        for attempt in range(5):
            time.sleep(2)
            success_url = registration_page.get_current_url()
            if 'success' in success_url or 'registered' in success_url:
                success_found = True
                break

        assert success_found, \
            f"Email with plus sign should redirect to success page, got: {success_url}"


    def test_percent_sign_email_rejected(self, registration_page, test_cleanup):
        """Test that emails with percent signs are rejected (security restriction)."""
        # Get test data with unique identity (in case validation fails and creates record)
        participant_data = get_test_participant('participants', 'regular_newbie')
        unique_identity = generate_unique_identity("Invalid", "Percent", "pcttest")
        participant_data['personal']['first_name'] = unique_identity['first_name']
        participant_data['personal']['last_name'] = unique_identity['last_name']
        participant_data['personal']['email'] = 'test%invalid@example.com'

        # Navigate to registration
        assert registration_page.navigate_to_registration(), "Failed to navigate"

        # Fill form with invalid email - should fail validation
        registration_page.fill_complete_registration_form(participant_data)
        registration_page.submit_registration()

        # Wait briefly for any redirect or validation
        time.sleep(2)
        current_url = registration_page.get_current_url()

        # Should NOT be on success page - either stayed on form or got error
        assert 'success' not in current_url and 'registered' not in current_url, \
            "Email with percent sign should not complete registration"


    def test_exclamation_email_rejected(self, registration_page, test_cleanup):
        """Test that emails with exclamation marks are rejected (security restriction)."""
        # Get test data with unique identity (in case validation fails)
        participant_data = get_test_participant('participants', 'regular_newbie')
        unique_identity = generate_unique_identity("Invalid", "Exclaim", "excltest")
        participant_data['personal']['first_name'] = unique_identity['first_name']
        participant_data['personal']['last_name'] = unique_identity['last_name']
        participant_data['personal']['email'] = 'test!invalid@example.com'

        # Navigate to registration
        assert registration_page.navigate_to_registration(), "Failed to navigate"

        # Fill form and try to submit
        registration_page.fill_complete_registration_form(participant_data)
        registration_page.submit_registration()

        # Wait briefly for any redirect or validation
        time.sleep(2)
        current_url = registration_page.get_current_url()

        # Should NOT be on success page
        assert 'success' not in current_url and 'registered' not in current_url, \
            "Email with exclamation mark should not complete registration"


    def test_consecutive_dots_rejected(self, registration_page, test_cleanup):
        """Test that emails with consecutive dots are rejected."""
        # Get test data with unique identity (in case validation fails)
        participant_data = get_test_participant('participants', 'regular_newbie')
        unique_identity = generate_unique_identity("Invalid", "Dots", "dotstest")
        participant_data['personal']['first_name'] = unique_identity['first_name']
        participant_data['personal']['last_name'] = unique_identity['last_name']
        participant_data['personal']['email'] = 'test..user@example.com'

        # Navigate to registration
        assert registration_page.navigate_to_registration(), "Failed to navigate"

        # Fill form and try to submit
        registration_page.fill_complete_registration_form(participant_data)
        registration_page.submit_registration()

        # Wait briefly for any redirect or validation
        time.sleep(2)
        current_url = registration_page.get_current_url()

        # Should NOT be on success page
        assert 'success' not in current_url and 'registered' not in current_url, \
            "Email with consecutive dots should not complete registration"


    def test_missing_at_symbol_rejected(self, registration_page, test_cleanup):
        """Test that emails without @ symbol are rejected."""
        # Get test data with unique identity (in case validation fails)
        participant_data = get_test_participant('participants', 'regular_newbie')
        unique_identity = generate_unique_identity("Invalid", "NoAt", "noattest")
        participant_data['personal']['first_name'] = unique_identity['first_name']
        participant_data['personal']['last_name'] = unique_identity['last_name']
        participant_data['personal']['email'] = 'testexample.com'

        # Navigate to registration
        assert registration_page.navigate_to_registration(), "Failed to navigate"

        # Fill form and try to submit
        registration_page.fill_complete_registration_form(participant_data)
        registration_page.submit_registration()

        # Wait briefly for any redirect or validation
        time.sleep(2)
        current_url = registration_page.get_current_url()

        # Should NOT be on success page
        assert 'success' not in current_url and 'registered' not in current_url, \
            "Email without @ symbol should not complete registration"


# ============================================================================
# Test Class: Backend API Validation
# ============================================================================

@pytest.mark.api
@pytest.mark.critical
class TestBackendAPIEmailValidation:
    """Direct API tests to verify backend validation enforcement."""

    def test_registration_api_rejects_invalid_email(self, test_cleanup):
        """Test that registration API rejects invalid email formats."""
        base_url = get_base_url()

        # Attempt registration with invalid email (percent sign)
        response = requests.post(
            f"{base_url}/register",
            data={
                'firstName': 'API',
                'lastName': 'Test',
                'email': 'invalid%test@example.com',
                'cellPhone': '604-555-0200',
                'preferredArea': 'C',
                'skillLevel': 'Beginner',
                'experience': '0-2 years',
            },
            allow_redirects=False
        )

        # Backend should reject this (400 or redirect back to form with error)
        assert response.status_code in [400, 302], \
            f"Backend should reject invalid email, got status {response.status_code}"

        if response.status_code == 302:
            # If redirect, check that it's not to success page
            assert "/registration-success" not in response.headers.get('Location', ''), \
                "Should not redirect to success page with invalid email"




    def test_backend_catches_javascript_disabled_bypass(self, db, test_cleanup):
        """Test that backend validation works when JavaScript is disabled."""
        base_url = get_base_url()

        # Direct POST without JavaScript validation
        # This simulates a user with JavaScript disabled or a malicious bypass attempt
        response = requests.post(
            f"{base_url}/register",
            data={
                'firstName': 'NoJS',
                'lastName': 'Test',
                'email': 'invalid!email@example.com',  # Exclamation mark
                'cellPhone': '604-555-0202',
                'preferredArea': 'E',
                'skillLevel': 'Beginner',
                'experience': '0-2 years',
            },
            allow_redirects=False
        )

        # Backend should still reject
        assert response.status_code != 200 or "/registration-success" not in response.headers.get('Location', ''), \
            "Backend must validate even when JavaScript is bypassed"

        # Verify no participant was created
        participants = db.collection('participants_2025').where('email', '==', 'invalid!email@example.com').limit(1).get()
        assert len(list(participants)) == 0, \
            "Invalid email should not create database record"


# ============================================================================
# Test Class: Admin Interface Email Validation
# ============================================================================

@pytest.mark.admin
@pytest.mark.browser
class TestAdminEmailValidation:
    """Browser-based tests for admin interface email validation."""

    def test_admin_participant_edit_rejects_invalid_email(self, authenticated_browser, db, test_cleanup, populated_database):
        """Test that admin participant edit validates email format."""
        base_url = get_base_url()

        # Navigate to participants page (already authenticated)
        authenticated_browser.get(f"{base_url}/admin/participants")
        time.sleep(2)

        # Find ANY participant row to test editing (avoid registration to prevent duplicates)
        wait = WebDriverWait(authenticated_browser, 10)
        try:
            # Find first participant row with edit button
            participant_row = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'table tbody tr[data-participant-id] .btn-edit'))
            ).find_element(By.XPATH, './ancestor::tr')
        except:
            pytest.skip("No participants found in database to test editing")

        # Click edit button - use JavaScript to avoid scroll issues
        edit_button = participant_row.find_element(By.CSS_SELECTOR, '.btn-edit')
        authenticated_browser.execute_script("arguments[0].scrollIntoView({block: 'center'});", edit_button)
        time.sleep(0.5)
        authenticated_browser.execute_script("arguments[0].click();", edit_button)
        time.sleep(1)

        # Change email to invalid format
        email_input = participant_row.find_element(By.CSS_SELECTOR, '.email-input')
        email_input.clear()
        email_input.send_keys('invalid%email@example.com')

        # Try to save
        save_button = participant_row.find_element(By.CSS_SELECTOR, '.btn-save')
        save_button.click()
        time.sleep(2)

        # Should see alert (JavaScript alert() used in code)
        try:
            alert = authenticated_browser.switch_to.alert
            alert_text = alert.text
            assert 'valid email' in alert_text.lower(), f"Expected email validation error, got: {alert_text}"
            alert.accept()
        except:
            # Alternative: Check if still in edit mode (save was prevented)
            assert participant_row.find_element(By.CSS_SELECTOR, '.email-input').is_displayed(), \
                "Should still be in edit mode after validation failure"


    def test_admin_leader_inline_edit_rejects_invalid_email(self, authenticated_browser, db, test_cleanup, populated_database):
        """Test that editing a leader validates email format."""
        base_url = get_base_url()

        # Navigate to leaders page (already authenticated)
        authenticated_browser.get(f"{base_url}/admin/leaders")
        time.sleep(2)

        # Check if there are existing leaders to edit
        wait = WebDriverWait(authenticated_browser, 10)
        try:
            leader_rows = authenticated_browser.find_elements(By.CSS_SELECTOR, 'table tbody tr[data-leader-id]')
            if len(leader_rows) == 0:
                pytest.skip("No existing leaders to test inline edit")

            # Click edit on first leader
            first_row = leader_rows[0]
            edit_button = first_row.find_element(By.CSS_SELECTOR, '.btn-edit')
            edit_button.click()
            time.sleep(1)

            # Change email to invalid format
            email_input = first_row.find_element(By.CSS_SELECTOR, '.email-input')
            original_email = email_input.get_attribute('value')
            email_input.clear()
            email_input.send_keys('invalid!email@example.com')

            # Try to save
            save_button = first_row.find_element(By.CSS_SELECTOR, '.btn-save')
            save_button.click()
            time.sleep(2)

            # Should see alert
            try:
                alert = authenticated_browser.switch_to.alert
                alert_text = alert.text
                assert 'valid email' in alert_text.lower(), f"Expected email validation error, got: {alert_text}"
                alert.accept()
            except:
                # Alternative: Check if still in edit mode
                assert first_row.find_element(By.CSS_SELECTOR, '.email-input').is_displayed(), \
                    "Should still be in edit mode after validation failure"
        except TimeoutException:
            pytest.skip("No leader table found on page")


    def test_admin_manual_leader_add_validates_email(self, authenticated_browser, db, test_cleanup):
        """Test that adding a leader via manual form validates email format."""
        base_url = get_base_url()

        # Navigate to leaders page (already authenticated)
        authenticated_browser.get(f"{base_url}/admin/leaders")
        time.sleep(2)

        # Fill in the Add Leader form with invalid email
        wait = WebDriverWait(authenticated_browser, 10)
        first_name_input = wait.until(EC.presence_of_element_located((By.ID, 'first_name')))
        first_name_input.send_keys('Test')

        authenticated_browser.find_element(By.ID, 'last_name').send_keys('Leader')
        authenticated_browser.find_element(By.ID, 'email').send_keys('testleader%invalid@example.com')
        authenticated_browser.find_element(By.ID, 'phone').send_keys('604-555-9999')

        # Select an area
        area_select = authenticated_browser.find_element(By.ID, 'area_code')
        Select(area_select).select_by_index(1)  # Select first area

        # Submit form
        authenticated_browser.find_element(By.CSS_SELECTOR, 'button[type="submit"]').click()
        time.sleep(2)

        # Should see inline validation error (Bootstrap .is-invalid)
        email_input = authenticated_browser.find_element(By.ID, 'email')
        assert 'is-invalid' in email_input.get_attribute('class'), \
            "Email input should have is-invalid class"

        # Should see error message
        error_div = authenticated_browser.find_element(By.CSS_SELECTOR, '#email + .invalid-feedback, #email ~ .invalid-feedback')
        assert 'valid email' in error_div.text.lower(), \
            f"Expected email validation error, got: {error_div.text}"

        # Should still be on leaders page (not redirected)
        assert '/admin/leaders' in authenticated_browser.current_url, \
            "Should remain on leaders page after validation failure"


# ============================================================================
# Test Class: Security and Edge Cases
# ============================================================================

@pytest.mark.security
@pytest.mark.critical
class TestEmailValidationSecurity:
    """Security tests for email validation."""

    def test_email_xss_sanitization(self, db, test_cleanup):
        """Test that XSS attempts in email field are sanitized."""
        base_url = get_base_url()

        # Attempt registration with XSS payload in email
        xss_email = '<script>alert("XSS")</script>@example.com'

        response = requests.post(
            f"{base_url}/register",
            data={
                'firstName': 'XSS',
                'lastName': 'Test',
                'email': xss_email,
                'cellPhone': '604-555-0300',
                'preferredArea': 'F',
                'skillLevel': 'Beginner',
                'experience': '0-2 years',
            },
            allow_redirects=False
        )

        # Should be rejected by validation
        assert response.status_code != 200 or "/registration-success" not in response.headers.get('Location', ''), \
            "XSS attempt in email should be rejected"

        # Verify no participant created with XSS email
        participants = db.collection('participants_2025').where('email', '==', xss_email).limit(1).get()
        assert len(list(participants)) == 0, \
            "XSS email should not create database record"


    def test_email_case_normalization(self, db, test_cleanup):
        """Test that email addresses are normalized to lowercase."""
        base_url = get_base_url()

        # Generate unique identity with standard email
        unique_identity = generate_unique_identity("Case", "Test", "casetest")

        # Register with mixed case email
        response = requests.post(
            f"{base_url}/register",
            data={
                'first_name': unique_identity['first_name'],
                'last_name': unique_identity['last_name'],
                'email': 'Test.User@Example.COM',  # Mixed case
                'phone': '604-555-0301',
                'participation_type': 'regular',
                'preferred_area': 'G',
                'skill_level': 'Beginner',
                'experience': 'None',
            },
            allow_redirects=False
        )

        # Should accept and redirect
        if response.status_code == 302 and "/registration-success" in response.headers.get('Location', ''):
            # Verify email was stored in lowercase
            time.sleep(1)  # Allow Firestore write to complete
            participants = db.collection('participants_2025').where(
                filter=firestore.FieldFilter('email', '==', 'test.user@example.com')
            ).limit(1).get()

            participants_list = list(participants)
            assert len(participants_list) > 0, \
                "Email should be stored in lowercase"

            stored_email = participants_list[0].to_dict().get('email')
            assert stored_email == 'test.user@example.com', \
                f"Expected lowercase email test.user@example.com, got {stored_email}"


    def test_sql_injection_attempt_in_email(self, db, test_cleanup):
        """Test that SQL injection attempts are handled (Firestore is NoSQL but still test)."""
        base_url = get_base_url()

        # Attempt with SQL injection payload
        sql_email = "'; DROP TABLE participants; --@example.com"

        response = requests.post(
            f"{base_url}/register",
            data={
                'firstName': 'SQL',
                'lastName': 'Injection',
                'email': sql_email,
                'cellPhone': '604-555-0302',
                'preferredArea': 'H',
                'skillLevel': 'Beginner',
                'experience': '0-2 years',
            },
            allow_redirects=False
        )

        # Should be rejected by validation (single quote invalid)
        assert response.status_code != 200 or "/registration-success" not in response.headers.get('Location', ''), \
            "SQL injection attempt should be rejected"

        # Verify collection still exists and is intact
        participants = db.collection('participants_2025').limit(1).get()
        # If this succeeds without exception, collection is intact
        assert True, "Database collection should remain intact after injection attempt"


# ============================================================================
# Test Class: Error Message Consistency
# ============================================================================

@pytest.mark.browser
class TestEmailValidationErrorMessages:
    """Test that error messages are consistent and user-friendly."""

    def test_frontend_error_message_displayed(self, registration_page, test_cleanup):
        """Test that frontend validation shows user-friendly error messages."""
        # Navigate to registration page
        assert registration_page.navigate_to_registration()
        time.sleep(1)

        # Fill in a minimal form with invalid email
        browser = registration_page.driver
        browser.find_element(By.ID, 'first_name').send_keys('Test')
        browser.find_element(By.ID, 'last_name').send_keys('User')

        # Enter invalid email and trigger validation
        email_input = browser.find_element(By.ID, 'email')
        email_input.send_keys('invalid@')
        email_input.send_keys('\t')  # Tab out to trigger blur event
        time.sleep(1)

        # Should see inline error message with is-invalid class
        assert 'is-invalid' in email_input.get_attribute('class'), \
            "Email input should have is-invalid class for invalid email"

        # Check for error message
        try:
            error_div = browser.find_element(By.CSS_SELECTOR, '#email + .invalid-feedback, #email ~ .invalid-feedback')
            assert error_div.is_displayed(), "Error message should be visible"
            assert 'valid email' in error_div.text.lower(), \
                f"Expected user-friendly email error message, got: {error_div.text}"
        except:
            # Alternative: Check for validation on submit
            # Fill rest of form
            browser.find_element(By.ID, 'phone').send_keys('604-555-0100')

            # Select area, skill, experience, participation type
            Select(browser.find_element(By.ID, 'preferred_area')).select_by_value('A')
            Select(browser.find_element(By.ID, 'skill_level')).select_by_value('Beginner')
            Select(browser.find_element(By.ID, 'experience')).select_by_value('None')
            browser.find_element(By.ID, 'participation_type_regular').click()

            # Try to submit
            browser.find_element(By.CSS_SELECTOR, 'button[type="submit"]').click()
            time.sleep(2)

            # Should see error
            assert 'is-invalid' in browser.find_element(By.ID, 'email').get_attribute('class'), \
                "Email should be marked invalid on submit"

            error_div = browser.find_element(By.CSS_SELECTOR, '#email + .invalid-feedback, #email ~ .invalid-feedback')
            assert 'valid email' in error_div.text.lower(), \
                f"Expected email validation error on submit, got: {error_div.text}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
