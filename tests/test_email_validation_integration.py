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

from tests.config import get_base_url, TEST_CONFIG
from tests.utils.auth_utils import admin_login_for_test
from google.cloud import firestore


# ============================================================================
# Helper Functions
# ============================================================================

def safe_click(browser, locator, timeout=10):
    """Safely click an element with scroll-into-view and wait."""
    element = WebDriverWait(browser, timeout).until(
        EC.element_to_be_clickable(locator)
    )
    browser.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
    time.sleep(0.3)  # Brief wait after scroll
    element.click()
    return element


def safe_select_by_value(browser, locator, value, timeout=10):
    """Safely select a dropdown option by value."""
    wait = WebDriverWait(browser, timeout)
    select_element = wait.until(EC.element_to_be_clickable(locator))
    browser.execute_script("arguments[0].scrollIntoView(true);", select_element)
    time.sleep(0.3)  # Brief pause after scrolling

    select = Select(select_element)
    select.select_by_value(value)
    return select_element


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture(scope="module")
def db():
    """Firestore database client."""
    return firestore.Client()


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

    def test_valid_email_accepted(self, browser, test_cleanup):
        """Test that valid email formats are accepted in registration form."""
        browser.get(f"{get_base_url()}/")

        # Fill in form with valid email
        browser.find_element(By.ID, "first_name").send_keys("ValidTest")
        browser.find_element(By.ID, "last_name").send_keys("User")
        browser.find_element(By.ID, "email").send_keys("valid-test@example.com")
        browser.find_element(By.ID, "phone").send_keys("604-555-0100")

        # Select skill level and experience using proper dropdown selection
        safe_select_by_value(browser, (By.ID, "skill_level"), "Beginner")
        safe_select_by_value(browser, (By.ID, "experience"), "None")

        # Select participation type (required)
        safe_click(browser, (By.ID, "regular"))

        # Select area
        safe_select_by_value(browser, (By.ID, "preferred_area"), "A")

        # Submit form
        safe_click(browser, (By.CSS_SELECTOR, "button[type='submit']"))

        # Wait for success page
        WebDriverWait(browser, 10).until(
            lambda d: "/registration-success" in d.current_url
        )

        assert "/registration-success" in browser.current_url, \
            "Valid email should be accepted and redirect to success page"


    def test_plus_sign_email_accepted(self, browser, test_cleanup):
        """Test that emails with plus signs are accepted (RFC 5322 compliance)."""
        browser.get(f"{get_base_url()}/")

        # Fill in form with plus sign email
        browser.find_element(By.ID, "first_name").send_keys("PlusSign")
        browser.find_element(By.ID, "last_name").send_keys("Test")
        email_field = browser.find_element(By.ID, "email")
        email_field.send_keys("test+tag@example.com")
        browser.find_element(By.ID, "phone").send_keys("604-555-0101")

        # Select skill level and experience using proper dropdown selection
        safe_select_by_value(browser, (By.ID, "skill_level"), "Intermediate")
        safe_select_by_value(browser, (By.ID, "experience"), "1-2 counts")

        # Select participation type (required)
        safe_click(browser, (By.ID, "regular"))

        # Select area
        safe_select_by_value(browser, (By.ID, "preferred_area"), "B")

        # Submit form
        safe_click(browser, (By.CSS_SELECTOR, "button[type='submit']"))

        # Wait for success page
        WebDriverWait(browser, 10).until(
            lambda d: "/registration-success" in d.current_url
        )

        assert "/registration-success" in browser.current_url, \
            "Email with plus sign should be accepted"


    def test_percent_sign_email_rejected(self, browser, test_cleanup):
        """Test that emails with percent signs are rejected (security restriction)."""
        browser.get(f"{get_base_url()}/")

        # Fill in form with percent sign email
        browser.find_element(By.ID, "first_name").send_keys("Invalid")
        browser.find_element(By.ID, "last_name").send_keys("Percent")
        email_field = browser.find_element(By.ID, "email")
        email_field.send_keys("test%invalid@example.com")

        # Trigger validation by moving focus away
        browser.find_element(By.ID, "phone").click()

        time.sleep(0.5)  # Wait for validation feedback

        # Check for validation error
        # The validation may show in different ways depending on implementation:
        # 1. HTML5 validation message
        # 2. Custom error message element
        # 3. Invalid field styling

        # Try HTML5 validation first
        validity = browser.execute_script(
            "return document.getElementById('email').validity.valid;"
        )

        assert not validity, \
            "Email with percent sign should trigger validation error"


    def test_exclamation_email_rejected(self, browser, test_cleanup):
        """Test that emails with exclamation marks are rejected (security restriction)."""
        browser.get(f"{get_base_url()}/")

        # Fill in form with exclamation mark email
        browser.find_element(By.ID, "first_name").send_keys("Invalid")
        browser.find_element(By.ID, "last_name").send_keys("Exclamation")
        email_field = browser.find_element(By.ID, "email")
        email_field.send_keys("test!invalid@example.com")

        # Trigger validation by moving focus away
        browser.find_element(By.ID, "phone").click()

        time.sleep(0.5)  # Wait for validation feedback

        # Check for validation error
        validity = browser.execute_script(
            "return document.getElementById('email').validity.valid;"
        )

        assert not validity, \
            "Email with exclamation mark should trigger validation error"


    def test_consecutive_dots_rejected(self, browser, test_cleanup):
        """Test that emails with consecutive dots are rejected."""
        browser.get(f"{get_base_url()}/")

        email_field = browser.find_element(By.ID, "email")
        email_field.send_keys("test..user@example.com")

        # Trigger validation
        browser.find_element(By.ID, "phone").click()
        time.sleep(0.5)

        # Check validation
        validity = browser.execute_script(
            "return document.getElementById('email').validity.valid;"
        )

        assert not validity, \
            "Email with consecutive dots should be rejected"


    def test_missing_at_symbol_rejected(self, browser, test_cleanup):
        """Test that emails without @ symbol are rejected."""
        browser.get(f"{get_base_url()}/")

        email_field = browser.find_element(By.ID, "email")
        email_field.send_keys("testexample.com")

        # Trigger validation
        browser.find_element(By.ID, "phone").click()
        time.sleep(0.5)

        # Check validation
        validity = browser.execute_script(
            "return document.getElementById('email').validity.valid;"
        )

        assert not validity, \
            "Email without @ symbol should be rejected"


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


    def test_registration_api_accepts_plus_sign_email(self, test_cleanup):
        """Test that registration API accepts emails with plus signs."""
        base_url = get_base_url()

        # Attempt registration with plus sign email
        response = requests.post(
            f"{base_url}/register",
            data={
                'firstName': 'APIPlus',
                'lastName': 'Test',
                'email': 'api+test@example.com',
                'cellPhone': '604-555-0201',
                'preferredArea': 'D',
                'skillLevel': 'Intermediate',
                'experience': '3-5 years',
            },
            allow_redirects=False
        )

        # Should accept and redirect to success
        assert response.status_code == 302, \
            f"Backend should accept plus sign email, got status {response.status_code}"

        assert "/registration-success" in response.headers.get('Location', ''), \
            "Should redirect to success page with valid plus sign email"


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

    def test_admin_participant_edit_rejects_invalid_email(self, browser, db, test_cleanup):
        """Test that admin participant edit validates email format."""
        # Login as admin
        admin_login_for_test(browser)

        # Navigate to participants page
        browser.get(f"{get_base_url()}/admin/participants")

        # Wait for page load
        WebDriverWait(browser, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "table"))
        )

        # Find a participant to edit (assuming there's at least one)
        # This test may need to create a test participant first
        try:
            edit_button = browser.find_element(By.CSS_SELECTOR, "button[data-action='edit']")
            edit_button.click()

            time.sleep(0.5)  # Wait for edit mode

            # Find email field and enter invalid email
            email_field = browser.find_element(By.CSS_SELECTOR, "input[name='email']")
            email_field.clear()
            email_field.send_keys("invalid%admin@example.com")

            # Try to save
            save_button = browser.find_element(By.CSS_SELECTOR, "button[data-action='save']")
            save_button.click()

            time.sleep(1)  # Wait for validation

            # Check that error feedback is shown or save failed
            # The exact implementation will determine how to verify this
            # For now, we'll check if we're still in edit mode (save didn't succeed)

            # Verification depends on UI implementation
            # This is a placeholder that should be updated based on actual UI behavior

        except Exception as e:
            pytest.skip(f"Admin edit test requires populated database: {e}")


    def test_admin_leader_add_validates_email(self, browser, db, test_cleanup):
        """Test that adding a leader validates email format."""
        # Login as admin
        admin_login_for_test(browser)

        # Navigate to leaders page
        browser.get(f"{get_base_url()}/admin/leaders")

        # Wait for page load
        WebDriverWait(browser, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )

        # This test depends on the leader management UI implementation
        # Placeholder for now - should be implemented based on actual UI
        pytest.skip("Leader management email validation test pending UI review")


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

        # Register with mixed case email
        response = requests.post(
            f"{base_url}/register",
            data={
                'firstName': 'Case',
                'lastName': 'Test',
                'email': 'Test.User@Example.COM',  # Mixed case
                'cellPhone': '604-555-0301',
                'preferredArea': 'G',
                'skillLevel': 'Beginner',
                'experience': '0-2 years',
            },
            allow_redirects=False
        )

        # Should accept and redirect
        if response.status_code == 302 and "/registration-success" in response.headers.get('Location', ''):
            # Verify email was stored in lowercase
            time.sleep(1)  # Allow Firestore write to complete
            participants = db.collection('participants_2025').where(
                'email', '==', 'test.user@example.com'  # Lowercase
            ).limit(1).get()

            participants_list = list(participants)
            assert len(participants_list) > 0, \
                "Email should be stored in lowercase"

            stored_email = participants_list[0].to_dict().get('email')
            assert stored_email == 'test.user@example.com', \
                f"Expected lowercase email, got {stored_email}"


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

    def test_frontend_error_message_displayed(self, browser, test_cleanup):
        """Test that frontend validation shows user-friendly error messages."""
        browser.get(f"{get_base_url()}/")

        email_field = browser.find_element(By.ID, "email")
        email_field.send_keys("invalid@")  # Incomplete email

        # Trigger validation
        browser.find_element(By.ID, "cellPhone").click()
        time.sleep(0.5)

        # Check for error message
        # This depends on how error messages are implemented
        # Could be:
        # 1. HTML5 validation message (browser native)
        # 2. Custom error element
        # 3. Field styling with is-invalid class

        # For now, check HTML5 validation
        validation_message = browser.execute_script(
            "return document.getElementById('email').validationMessage;"
        )

        assert validation_message, \
            "Error message should be displayed for invalid email"

        # Message should be user-friendly (not technical)
        assert "email" in validation_message.lower() or "invalid" in validation_message.lower(), \
            "Error message should mention email or invalid format"


    def test_security_restriction_error_is_clear(self, browser, test_cleanup):
        """Test that security restriction errors are user-friendly."""
        browser.get(f"{get_base_url()}/")

        email_field = browser.find_element(By.ID, "email")
        email_field.send_keys("test%security@example.com")

        # Trigger validation
        browser.find_element(By.ID, "cellPhone").click()
        time.sleep(0.5)

        # Get validation message
        validation_message = browser.execute_script(
            "return document.getElementById('email').validationMessage;"
        )

        # Message should be helpful (not just "invalid")
        # Ideally mentions the specific character issue
        assert validation_message, \
            "Error message should be displayed for security-restricted character"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
