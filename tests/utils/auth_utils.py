# Authentication Utilities for Test Suite
# Updated by Claude AI on 2025-09-22

"""
Utilities for handling OAuth authentication in automated tests.
Provides functions for logging in test accounts and managing sessions.
"""

import time
import logging
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from tenacity import retry, stop_after_attempt, wait_exponential

from tests.config import TEST_CONFIG
import requests
import json

logger = logging.getLogger(__name__)

class AuthenticationError(Exception):
    """Raised when authentication fails."""
    pass

def direct_session_login(driver, email, role, base_url):
    """
    Bypass OAuth by directly setting session cookies for test accounts.
    This avoids the Chrome crash issues with Google OAuth automation.

    Args:
        driver: Selenium WebDriver instance
        email: Test account email
        role: User role (admin, leader, public)
        base_url: Base URL of the application

    Returns:
        bool: True if session setup successful
    """
    try:
        logger.info(f"Setting up direct session for {email} with role {role}")

        # Navigate to the main site first to set domain for cookies
        driver.get(base_url)

        # Generate session data that matches what OAuth would create
        session_data = {
            'user_email': email,
            'user_name': email.split('@')[0].replace('-', ' ').title(),
            'user_role': role
        }

        # Set session cookies directly
        # Note: This is a simplified approach - in a real app you'd need the actual session key
        for key, value in session_data.items():
            driver.add_cookie({
                'name': f'session_{key}',
                'value': value,
                'domain': base_url.replace('https://', '').replace('http://', ''),
                'path': '/',
                'secure': True if 'https' in base_url else False
            })

        # Navigate to a protected page to trigger session verification
        test_url = f"{base_url}/admin" if role == 'admin' else f"{base_url}/leader"
        driver.get(test_url)

        # Check if we're redirected to login (session didn't work) or if we see admin/leader content
        current_url = driver.current_url
        if '/auth/login' in current_url:
            logger.warning("Direct session login failed - redirected to login page")
            return False

        logger.info(f"Direct session login successful for {email}")
        return True

    except Exception as e:
        logger.error(f"Direct session login failed for {email}: {e}")
        return False

@retry(
    stop=stop_after_attempt(TEST_CONFIG['retry_attempts']),
    wait=wait_exponential(multiplier=1, min=2, max=10)
)
def login_with_google(driver, email, password, base_url):
    """
    Perform Google OAuth login for test accounts.

    Args:
        driver: Selenium WebDriver instance
        email: Test account email
        password: Test account password
        base_url: Base URL of the application

    Returns:
        bool: True if login successful

    Raises:
        AuthenticationError: If login fails after retries
    """
    try:
        logger.info(f"Attempting login for {email}")

        # Navigate to login page
        login_url = f"{base_url}/auth/login"
        driver.get(login_url)

        # Wait for Google Identity Services to load and create the sign-in button
        wait = WebDriverWait(driver, TEST_CONFIG['oauth_timeout'])

        # Wait for the Google Identity Services library to load and render the button
        time.sleep(3)

        # Look for the Google Sign-In button (created by Google Identity Services)
        google_signin_selectors = [
            "//div[@role='button' and contains(@aria-label, 'Sign in with Google')]",
            "//div[contains(@class, 'g_id_signin')]//div[@role='button']",
            "//iframe[contains(@src, 'accounts.google.com')]",
            "//div[@id='g_id_signin']//div[@role='button']"
        ]

        google_signin_button = None
        for selector in google_signin_selectors:
            try:
                google_signin_button = wait.until(EC.element_to_be_clickable((By.XPATH, selector)))
                logger.info(f"Found Google Sign-In button using selector: {selector}")
                break
            except TimeoutException:
                continue

        if not google_signin_button:
            # Check if it's in an iframe
            iframes = driver.find_elements(By.TAG_NAME, "iframe")
            logger.info(f"Found {len(iframes)} iframes on page")
            for i, iframe in enumerate(iframes):
                src = iframe.get_attribute("src")
                logger.info(f"  Iframe {i+1}: {src}")
                if "accounts.google.com" in src:
                    logger.info("Switching to Google accounts iframe")
                    driver.switch_to.frame(iframe)
                    try:
                        google_signin_button = wait.until(
                            EC.element_to_be_clickable((By.XPATH, "//div[@role='button']"))
                        )
                        logger.info("Found sign-in button in iframe")
                        break
                    except TimeoutException:
                        driver.switch_to.default_content()
                        continue

        if not google_signin_button:
            raise AuthenticationError("Could not find Google Sign-In button")

        google_signin_button.click()
        logger.info("Clicked Google Sign-In button")

        # Handle Google Identity Services OAuth popup/redirect
        _handle_google_identity_services_oauth(driver, email, password, wait)

        # Verify successful login by checking for redirect or user indicator
        _verify_login_success(driver, base_url, wait)

        logger.info(f"Successfully logged in as {email}")
        return True

    except (TimeoutException, WebDriverException) as e:
        logger.error(f"Login failed for {email}: {e}")
        raise AuthenticationError(f"Failed to login {email}: {e}")

def _handle_google_identity_services_oauth(driver, email, password, wait):
    """Handle the Google Identity Services OAuth flow (modern approach)."""
    try:
        # Switch back to main window if iframe was used
        driver.switch_to.default_content()

        # Google Identity Services typically opens in a popup
        # Wait for popup window to appear
        time.sleep(2)

        original_window = driver.current_window_handle
        popup_found = False

        # Check for popup window
        for window_handle in driver.window_handles:
            if window_handle != original_window:
                driver.switch_to.window(window_handle)
                popup_found = True
                logger.info("Switched to Google OAuth popup window")
                break

        if not popup_found:
            logger.info("No popup found, continuing in same window")

        # Now handle the standard Google OAuth flow
        _handle_standard_google_oauth(driver, email, password, wait)

        # Switch back to original window
        if popup_found:
            driver.switch_to.window(original_window)
            logger.info("Switched back to main window")

    except Exception as e:
        logger.error(f"Google Identity Services OAuth error: {e}")
        # Switch back to original window in case of error
        try:
            driver.switch_to.window(original_window)
        except:
            pass
        raise

def _handle_standard_google_oauth(driver, email, password, wait):
    """Handle the Google OAuth flow."""
    try:
        # Switch to Google OAuth window if popup
        if len(driver.window_handles) > 1:
            driver.switch_to.window(driver.window_handles[-1])

        # Try multiple selectors for email field (Google changes these frequently)
        email_field = None
        email_selectors = [
            (By.ID, "identifierId"),
            (By.NAME, "identifier"),
            (By.XPATH, "//input[@type='email']"),
            (By.XPATH, "//input[contains(@placeholder, 'email') or contains(@placeholder, 'Email')]"),
            (By.XPATH, "//input[@autocomplete='username']")
        ]

        for selector_type, selector in email_selectors:
            try:
                email_field = wait.until(EC.element_to_be_clickable((selector_type, selector)))
                logger.info(f"Found email field using selector: {selector_type}={selector}")
                break
            except TimeoutException:
                continue

        if not email_field:
            raise AuthenticationError("Could not find email input field")

        email_field.clear()
        email_field.send_keys(email)

        # Try multiple selectors for Next button
        next_button = None
        next_selectors = [
            (By.ID, "identifierNext"),
            (By.XPATH, "//button[contains(text(), 'Next')]"),
            (By.XPATH, "//input[@type='submit' and @value='Next']"),
            (By.XPATH, "//span[text()='Next']/parent::button"),
            (By.XPATH, "//div[text()='Next']/parent::button")
        ]

        for selector_type, selector in next_selectors:
            try:
                next_button = driver.find_element(selector_type, selector)
                logger.info(f"Found next button using selector: {selector_type}={selector}")
                break
            except:
                continue

        if not next_button:
            raise AuthenticationError("Could not find Next button")

        next_button.click()
        logger.info("Entered email and clicked Next")

        # Wait and enter password
        time.sleep(2)  # Allow page transition

        # Try multiple selectors for password field
        password_field = None
        password_selectors = [
            (By.XPATH, "//input[@type='password']"),  # This works - Google uses type='password' with name='Passwd'
            (By.NAME, "Passwd"),  # Google's actual password field name
            (By.NAME, "password"),  # Standard fallback
            (By.ID, "password"),
            (By.XPATH, "//input[contains(@placeholder, 'password') or contains(@placeholder, 'Password')]"),
            (By.XPATH, "//input[@autocomplete='current-password']")
        ]

        for selector_type, selector in password_selectors:
            try:
                password_field = wait.until(EC.element_to_be_clickable((selector_type, selector)))
                logger.info(f"Found password field using selector: {selector_type}={selector}")
                break
            except TimeoutException:
                continue

        if not password_field:
            raise AuthenticationError("Could not find password input field")

        password_field.clear()
        password_field.send_keys(password)

        # Try multiple selectors for Sign In button
        signin_button = None
        signin_selectors = [
            (By.XPATH, "//button[contains(text(), 'Next')]"),  # This works - Google uses "Next" button for password step
            (By.ID, "passwordNext"),
            (By.XPATH, "//button[contains(text(), 'Sign in')]"),
            (By.XPATH, "//input[@type='submit']"),
            (By.XPATH, "//span[text()='Next']/parent::button"),
            (By.XPATH, "//div[text()='Next']/parent::button")
        ]

        for selector_type, selector in signin_selectors:
            try:
                signin_button = driver.find_element(selector_type, selector)
                logger.info(f"Found sign in button using selector: {selector_type}={selector}")
                break
            except:
                continue

        if not signin_button:
            raise AuthenticationError("Could not find Sign In button")

        signin_button.click()
        logger.info("Entered password and clicked Sign In")

        # Handle potential 2FA or additional verification
        _handle_additional_verification(driver, wait)

        # Switch back to main window if popup was used
        if len(driver.window_handles) > 1:
            driver.switch_to.window(driver.window_handles[0])

    except (TimeoutException, WebDriverException) as e:
        logger.error(f"OAuth flow error: {e}")
        raise

def _handle_additional_verification(driver, wait):
    """Handle potential additional verification steps including OAuth consent."""
    try:
        # Wait briefly to see if additional verification is required
        time.sleep(3)

        # Check for OAuth consent screen first
        consent_selectors = [
            "//button[contains(text(), 'Continue')]",
            "//button[contains(text(), 'Allow')]",
            "//button[contains(text(), 'Accept')]",
            "//input[@type='submit' and contains(@value, 'Continue')]",
            "//input[@type='submit' and contains(@value, 'Allow')]"
        ]

        for selector in consent_selectors:
            try:
                consent_button = driver.find_element(By.XPATH, selector)
                if consent_button.is_displayed() and consent_button.is_enabled():
                    logger.info(f"Found OAuth consent button: {selector}")
                    consent_button.click()
                    logger.info("Clicked OAuth consent button")
                    time.sleep(2)
                    return
            except:
                continue

        # Check for account selection screen
        try:
            account_elements = driver.find_elements(By.XPATH, "//div[@data-identifier]")
            if account_elements:
                logger.info("Found account selection screen")
                # Click the first account (should be our test account)
                account_elements[0].click()
                logger.info("Selected test account")
                time.sleep(2)
                return
        except:
            pass

        # Check for any other verification indicators
        verification_indicators = [
            "Choose an account",
            "Grant permission",
            "Verify it's you"
        ]

        for indicator in verification_indicators:
            try:
                element = driver.find_element(By.XPATH, f"//*[contains(text(), '{indicator}')]")
                if element.is_displayed():
                    logger.info(f"Found verification step: {indicator}")
                    # For now, just log - specific handling can be added as needed
                    return
            except:
                continue

        logger.info("No additional verification steps found")

    except Exception as e:
        logger.warning(f"Additional verification handling warning: {e}")
        # Don't fail here as this step may not always be needed

def _verify_login_success(driver, base_url, wait):
    """Verify that login was successful."""
    try:
        # Wait for redirect away from Google OAuth
        wait.until(lambda d: base_url in d.current_url)

        # Check for indicators of successful login
        success_indicators = [
            (By.XPATH, "//a[contains(@href, '/auth/logout') or contains(text(), 'Logout')]"),
            (By.XPATH, "//div[contains(@class, 'user-info') or contains(@class, 'admin-nav')]"),
            (By.XPATH, "//*[contains(text(), 'Dashboard') or contains(text(), 'Admin')]")
        ]

        for by, selector in success_indicators:
            try:
                element = wait.until(EC.presence_of_element_located((by, selector)))
                if element:
                    logger.info("Login success verified")
                    return True
            except TimeoutException:
                continue

        # If no success indicators found, check URL patterns
        current_url = driver.current_url
        if any(path in current_url for path in ['/admin', '/leader', '/dashboard']):
            logger.info("Login success verified by URL")
            return True

        raise AuthenticationError("Could not verify login success")

    except TimeoutException:
        raise AuthenticationError("Login verification timeout")

def logout(driver, base_url):
    """
    Log out the current user.

    Args:
        driver: Selenium WebDriver instance
        base_url: Base URL of the application

    Returns:
        bool: True if logout successful
    """
    try:
        logger.info("Attempting logout")

        # Look for logout link
        wait = WebDriverWait(driver, 10)
        logout_link = wait.until(
            EC.element_to_be_clickable((By.XPATH, "//a[contains(@href, '/auth/logout') or contains(text(), 'Logout')]"))
        )
        logout_link.click()

        # Verify logout by checking for login elements
        wait.until(
            EC.presence_of_element_located((By.XPATH, "//button[contains(text(), 'Sign in') or contains(@class, 'google-signin')]"))
        )

        logger.info("Successfully logged out")
        return True

    except (TimeoutException, WebDriverException) as e:
        logger.error(f"Logout failed: {e}")
        return False

def get_user_role(driver):
    """
    Determine the current user's role based on page elements.

    Args:
        driver: Selenium WebDriver instance

    Returns:
        str: 'admin', 'leader', 'public', or 'unknown'
    """
    try:
        current_url = driver.current_url

        # Check URL patterns first
        if '/admin' in current_url:
            return 'admin'
        elif '/leader' in current_url:
            return 'leader'

        # Check for role-specific elements
        admin_indicators = [
            "//a[contains(@href, '/admin')]",
            "//nav[contains(@class, 'admin-nav')]",
            "//*[contains(text(), 'Admin Dashboard')]"
        ]

        for indicator in admin_indicators:
            try:
                if driver.find_element(By.XPATH, indicator).is_displayed():
                    return 'admin'
            except:
                continue

        leader_indicators = [
            "//a[contains(@href, '/leader')]",
            "//*[contains(text(), 'Leader Dashboard')]"
        ]

        for indicator in leader_indicators:
            try:
                if driver.find_element(By.XPATH, indicator).is_displayed():
                    return 'leader'
            except:
                continue

        # Check if logged in at all
        logout_elements = driver.find_elements(By.XPATH, "//a[contains(@href, '/auth/logout')]")
        if logout_elements:
            return 'public'  # Logged in but no special role

        return 'public'  # Not logged in

    except Exception as e:
        logger.warning(f"Could not determine user role: {e}")
        return 'unknown'

def ensure_logged_out(driver, base_url):
    """
    Ensure the user is logged out before starting a test.

    Args:
        driver: Selenium WebDriver instance
        base_url: Base URL of the application
    """
    try:
        # Check if already logged out
        driver.get(base_url)
        time.sleep(2)

        logout_elements = driver.find_elements(By.XPATH, "//a[contains(@href, '/auth/logout')]")
        if logout_elements:
            logout(driver, base_url)

        logger.info("Ensured logged out state")

    except Exception as e:
        logger.warning(f"Error ensuring logged out: {e}")

def wait_for_page_load(driver, timeout=30):
    """
    Wait for page to fully load.

    Args:
        driver: Selenium WebDriver instance
        timeout: Maximum time to wait in seconds
    """
    try:
        wait = WebDriverWait(driver, timeout)
        wait.until(lambda d: d.execute_script("return document.readyState") == "complete")
        logger.debug("Page load complete")
    except TimeoutException:
        logger.warning("Page load timeout - proceeding anyway")