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

logger = logging.getLogger(__name__)

class AuthenticationError(Exception):
    """Raised when authentication fails."""
    pass

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

        # Wait for and click Google Sign-In button
        wait = WebDriverWait(driver, TEST_CONFIG['oauth_timeout'])
        google_signin_button = wait.until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(@class, 'google-signin') or contains(text(), 'Sign in with Google')]"))
        )
        google_signin_button.click()

        logger.info("Clicked Google Sign-In button")

        # Handle Google OAuth popup/redirect
        _handle_google_oauth(driver, email, password, wait)

        # Verify successful login by checking for redirect or user indicator
        _verify_login_success(driver, base_url, wait)

        logger.info(f"Successfully logged in as {email}")
        return True

    except (TimeoutException, WebDriverException) as e:
        logger.error(f"Login failed for {email}: {e}")
        raise AuthenticationError(f"Failed to login {email}: {e}")

def _handle_google_oauth(driver, email, password, wait):
    """Handle the Google OAuth flow."""
    try:
        # Switch to Google OAuth window if popup
        if len(driver.window_handles) > 1:
            driver.switch_to.window(driver.window_handles[-1])

        # Enter email
        email_field = wait.until(
            EC.element_to_be_clickable((By.ID, "identifierId"))
        )
        email_field.clear()
        email_field.send_keys(email)

        # Click Next
        next_button = driver.find_element(By.ID, "identifierNext")
        next_button.click()

        logger.info("Entered email and clicked Next")

        # Wait and enter password
        time.sleep(2)  # Allow page transition
        password_field = wait.until(
            EC.element_to_be_clickable((By.NAME, "password"))
        )
        password_field.clear()
        password_field.send_keys(password)

        # Click Sign In
        signin_button = driver.find_element(By.ID, "passwordNext")
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
    """Handle potential additional verification steps."""
    try:
        # Wait briefly to see if additional verification is required
        time.sleep(3)

        # Check for common additional verification screens
        verification_indicators = [
            "Choose an account",
            "Grant permission",
            "Allow access",
            "Continue"
        ]

        for indicator in verification_indicators:
            try:
                element = driver.find_element(By.XPATH, f"//*[contains(text(), '{indicator}')]")
                if element.is_displayed():
                    logger.info(f"Found verification step: {indicator}")

                    # Click appropriate button
                    if indicator == "Choose an account":
                        # Click on the correct account
                        account_element = wait.until(
                            EC.element_to_be_clickable((By.XPATH, "//div[@data-identifier]"))
                        )
                        account_element.click()
                    else:
                        # Click continue/allow button
                        continue_button = wait.until(
                            EC.element_to_be_clickable((By.XPATH, f"//button[contains(text(), '{indicator}') or contains(text(), 'Continue') or contains(text(), 'Allow')]"))
                        )
                        continue_button.click()

                    time.sleep(2)
                    break
            except:
                continue

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