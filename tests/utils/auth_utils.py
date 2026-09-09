# Authentication Utilities for Test Suite
# Updated by Claude AI on 2026-09-07

"""
Utilities for authenticating as a test user in Selenium tests.

This app authenticates via a magic-link email (see routes/auth.py) rather than
Google OAuth - there is no login form/password to automate anymore. Instead of
driving the real magic-link email flow (which would require intercepting a
sent email), these helpers construct a real, validly-signed Flask session
cookie directly and inject it into the browser - the same "session" cookie
the app itself would set after a real magic-link click, built with Flask's
own signing serializer so it verifies identically. Session data holds only
user_email/user_name; user_role is deliberately not baked in, since
app.py's load_user() re-derives it from the database on every request
regardless of what's in the cookie.
"""

import logging

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

logger = logging.getLogger(__name__)


class AuthenticationError(Exception):
    """Raised when authentication fails."""
    pass


def build_session_cookie_value(user_email, user_name=None):
    """Build a signed Flask session cookie value for a test user.

    Uses the real Flask app's own signing serializer (Flask's default
    SecureCookieSessionInterface, since Flask-Session isn't installed here -
    see routes/auth.py's init_auth() comment) so the result is indistinguishable
    from a cookie the app set itself. Requires the app process and this test
    process to share the same SECRET_KEY, which they do locally since both
    load it from the same .env via config/database.py's load_dotenv() call.
    """
    from flask.sessions import SecureCookieSessionInterface
    from app import app as flask_app

    serializer = SecureCookieSessionInterface().get_signing_serializer(flask_app)
    session_data = {
        'user_email': user_email,
        'user_name': user_name or user_email,
        '_permanent': True,
    }
    return serializer.dumps(session_data)


def login_as_test_user(driver, base_url, user_email, user_name=None):
    """Authenticate a Selenium session as user_email without the real magic-link
    email - injects a validly-signed session cookie directly.

    user_email must be a real admin/leader per config/admins.py or
    CircleAdminModel for any role-gated page to actually grant access -
    load_user() re-derives the role from the database on every request.
    """
    try:
        # Must load a page on the target domain first - browsers won't accept
        # a cookie for a domain they haven't navigated to yet. This first load also
        # gets Flask-WTF to set its own initial 'session' cookie (carrying just a
        # CSRF token) - deleted below before we inject ours.
        driver.get(base_url)

        # Without this, the browser ends up holding two 'session' cookies: the one
        # Flask-WTF just set (host-only, no Domain attribute) and the one we're
        # about to inject. Both would match subsequent requests, so the browser
        # sends both in the Cookie header - which one Flask/Werkzeug ends up using
        # is unpredictable, and picking the wrong one silently authenticates as no
        # one at all (no user_email in that session), with every gated page just
        # redirecting to /auth/login instead of failing loudly.
        driver.delete_cookie('session')

        cookie_value = build_session_cookie_value(user_email, user_name)
        # Deliberately no explicit 'domain' here, for any host: passing one (even
        # exactly matching the current host) makes geckodriver/chromedriver store it
        # as a leading-dot domain cookie ('.test.cbc.test'), a *different* cookie-jar
        # entry from the host-only one Flask itself always sets (no Domain attribute)
        # - recreating the exact two-cookie ambiguity above on the very next request,
        # once the server refreshes the session (e.g. to mint a CSRF token). Omitting
        # 'domain' makes Selenium scope the cookie to the current page's host as a
        # plain host-only cookie, matching Flask's own cookie exactly.
        cookie = {'name': 'session', 'value': cookie_value, 'path': '/'}
        driver.add_cookie(cookie)

        driver.get(f"{base_url}/bigbird/")
        logger.info(f"Injected session cookie for {user_email}")
        return True
    except WebDriverException as e:
        logger.error(f"Failed to inject session cookie for {user_email}: {e}")
        raise AuthenticationError(f"Failed to log in {user_email}: {e}")


def admin_login_for_test(browser, base_url, credentials):
    """Login helper for test automation.

    Args:
        browser: Selenium WebDriver instance
        base_url: Base URL of the application
        credentials: Dict with an 'email' key (see tests.test_config.TEST_ACCOUNTS)

    Raises:
        pytest.skip: If authentication fails
    """
    try:
        login_as_test_user(browser, base_url, credentials['email'])
    except AuthenticationError as e:
        import pytest
        pytest.skip(f"Authentication failed for {credentials['email']}: {e}")


def logout(driver, base_url):
    """Log out the current user.

    Returns:
        bool: True if logout successful
    """
    try:
        logger.info("Attempting logout")
        wait = WebDriverWait(driver, 10)
        logout_link = wait.until(
            EC.element_to_be_clickable((By.XPATH, "//a[contains(@href, '/auth/logout') or contains(text(), 'Logout')]"))
        )
        logout_link.click()

        wait.until(EC.presence_of_element_located(
            (By.XPATH, "//input[@name='email' or @type='email']")
        ))

        logger.info("Successfully logged out")
        return True
    except (TimeoutException, WebDriverException) as e:
        logger.error(f"Logout failed: {e}")
        return False


def get_user_role(driver):
    """Determine the current user's role based on page elements/URL.

    Returns:
        str: 'admin', 'leader', 'public', or 'unknown'
    """
    try:
        current_url = driver.current_url

        if '/bigbird' in current_url:
            return 'admin'
        elif '/leader' in current_url:
            return 'leader'

        admin_indicators = [
            "//a[contains(@href, '/bigbird')]",
            "//*[contains(text(), 'Admin Dashboard')]",
        ]
        for indicator in admin_indicators:
            try:
                if driver.find_element(By.XPATH, indicator).is_displayed():
                    return 'admin'
            except Exception:
                continue

        leader_indicators = [
            "//a[contains(@href, '/leader')]",
            "//*[contains(text(), 'Leader Dashboard')]",
        ]
        for indicator in leader_indicators:
            try:
                if driver.find_element(By.XPATH, indicator).is_displayed():
                    return 'leader'
            except Exception:
                continue

        logout_elements = driver.find_elements(By.XPATH, "//a[contains(@href, '/auth/logout')]")
        if logout_elements:
            return 'public'  # Logged in but no special role

        return 'public'  # Not logged in
    except Exception as e:
        logger.warning(f"Could not determine user role: {e}")
        return 'unknown'


def ensure_logged_out(driver, base_url):
    """Ensure the user is logged out before starting a test."""
    try:
        driver.get(base_url)
        driver.delete_all_cookies()
        driver.get(base_url)
        logger.info("Ensured logged out state")
    except Exception as e:
        logger.warning(f"Error ensuring logged out: {e}")


def wait_for_page_load(driver, timeout=30):
    """Wait for page to fully load."""
    try:
        wait = WebDriverWait(driver, timeout)
        wait.until(lambda d: d.execute_script("return document.readyState") == "complete")
        logger.debug("Page load complete")
    except TimeoutException:
        logger.warning("Page load timeout - proceeding anyway")
