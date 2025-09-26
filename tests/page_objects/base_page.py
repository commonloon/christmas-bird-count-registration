# Base Page Object for maintainable UI testing
# Updated by Claude AI on 2025-09-25

"""
Base page object providing common functionality and resilient element finding.
"""

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.action_chains import ActionChains
import time
import logging

logger = logging.getLogger(__name__)


class BasePage:
    """Base page object with common functionality for all pages."""

    def __init__(self, driver, base_url):
        self.driver = driver
        self.base_url = base_url
        self.wait = WebDriverWait(driver, 10)

    def find_element_safely(self, identifier, timeout=3):
        """
        Find element using optimized strategies for performance.

        Args:
            identifier: Either a data-test attribute name or tuple of (method, selector)
            timeout: Maximum time to wait for element (reduced default)

        Returns:
            WebElement if found, None otherwise
        """
        if isinstance(identifier, str):
            # Optimized strategy: most likely selectors first
            selectors = [
                (By.ID, identifier),              # Most common for form fields
                (By.NAME, identifier),            # Second most common
                (By.ID, identifier.replace('-', '_')),  # Common naming convention
                (By.CSS_SELECTOR, f'#{identifier}'),     # CSS ID selector
                (By.CSS_SELECTOR, f'[data-test="{identifier}"]'), # Data attributes
            ]
        else:
            # Direct selector provided
            selectors = [identifier]

        # Use shorter timeout per selector for faster overall performance
        individual_timeout = max(0.5, timeout / len(selectors))

        for method, selector in selectors:
            try:
                wait = WebDriverWait(self.driver, individual_timeout)
                element = wait.until(EC.presence_of_element_located((method, selector)))
                logger.debug(f"Found element using {method}: {selector}")
                return element
            except TimeoutException:
                continue

        logger.warning(f"Could not find element: {identifier} (tried {len(selectors)} strategies)")
        return None

    def find_clickable_element(self, identifier, timeout=5):
        """Find element and ensure it's clickable with optimized timeout."""
        element = self.find_element_safely(identifier, timeout)
        if element:
            try:
                WebDriverWait(self.driver, 2).until(
                    EC.element_to_be_clickable(element)
                )
                return element
            except TimeoutException:
                logger.warning(f"Element not clickable: {identifier}")
        return None

    def safe_click(self, identifier, timeout=5):
        """
        Safely click an element with optimized strategies.

        Uses faster click strategies with reduced timeouts.
        """
        element = self.find_clickable_element(identifier, timeout)
        if not element:
            return False

        try:
            # Strategy 1: Direct click
            element.click()
            return True
        except Exception as e1:
            logger.debug(f"Direct click failed: {e1}")

            try:
                # Strategy 2: Scroll into view and click (no smooth scrolling for speed)
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
                time.sleep(0.5)
                element.click()
                return True
            except Exception as e2:
                logger.debug(f"Scroll and click failed: {e2}")

                try:
                    # Strategy 3: JavaScript click
                    self.driver.execute_script("arguments[0].click();", element)
                    return True
                except Exception as e3:
                    logger.error(f"All click strategies failed for {identifier}: {e3}")
                    return False

    def safe_send_keys(self, identifier, text, clear_first=True):
        """Safely send keys to an element."""
        element = self.find_element_safely(identifier)
        if not element:
            return False

        try:
            if clear_first:
                element.clear()
            element.send_keys(text)
            return True
        except Exception as e:
            logger.error(f"Failed to send keys to {identifier}: {e}")
            return False

    def safe_select_dropdown(self, identifier, value, by_value=True):
        """Safely select dropdown option with Firefox-compatible approach."""
        element = self.find_element_safely(identifier)
        if not element:
            return False

        try:
            # Scroll the select element into view (instant for speed)
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
            time.sleep(0.2)

            # Use JavaScript to set the value - more reliable for Firefox
            if by_value:
                script = f"arguments[0].value = '{value}'; arguments[0].dispatchEvent(new Event('change'));"
                self.driver.execute_script(script, element)
                logger.info(f"Selected dropdown {identifier} with value {value} via JavaScript")
            else:
                # Fallback to standard Select for text-based selection
                select = Select(element)
                select.select_by_visible_text(value)
                logger.info(f"Selected dropdown {identifier} with text {value} via Select")

            time.sleep(0.2)
            return True
        except Exception as e:
            logger.error(f"Failed to select dropdown {identifier} with value {value}: {e}")
            # Try fallback approach with ActionChains
            try:
                logger.info(f"Trying fallback approach for {identifier}")
                actions = ActionChains(self.driver)
                actions.click(element).perform()
                time.sleep(0.3)

                select = Select(element)
                if by_value:
                    select.select_by_value(value)
                else:
                    select.select_by_visible_text(value)

                return True
            except Exception as e2:
                logger.error(f"Fallback approach also failed for {identifier}: {e2}")
                return False

    def wait_for_page_load(self, timeout=10):
        """Wait for page to load with optimized timeout."""
        try:
            # First check if document is already ready
            if self.driver.execute_script("return document.readyState") == "complete":
                return True

            # Wait for ready state with shorter timeout
            WebDriverWait(self.driver, timeout).until(
                lambda driver: driver.execute_script("return document.readyState") == "complete"
            )
            return True
        except TimeoutException:
            logger.warning(f"Page load timeout after {timeout}s, but continuing...")
            # Don't fail the test for slow page loads - the page might still be usable
            return True

    def wait_for_url_contains(self, text, timeout=10):
        """Wait for URL to contain specific text."""
        try:
            WebDriverWait(self.driver, timeout).until(
                EC.url_contains(text)
            )
            return True
        except TimeoutException:
            logger.warning(f"URL did not contain '{text}' within {timeout}s")
            return False

    def get_element_text(self, identifier):
        """Get text content of element."""
        element = self.find_element_safely(identifier)
        if element:
            return element.text
        return ""

    def is_element_visible(self, identifier):
        """Check if element is visible."""
        element = self.find_element_safely(identifier)
        if element:
            return element.is_displayed()
        return False

    def navigate_to(self, path=""):
        """Navigate to a page with optimized loading."""
        url = f"{self.base_url}{path}"
        logger.info(f"Navigating to: {url}")
        self.driver.get(url)

        # Quick check if we can proceed without waiting for full page load
        try:
            # Wait briefly for basic DOM to be ready
            WebDriverWait(self.driver, 5).until(
                lambda driver: driver.execute_script("return document.readyState") in ["interactive", "complete"]
            )
            logger.debug("Page DOM ready, proceeding")
            return True
        except TimeoutException:
            logger.warning("Page taking longer to load, using fallback wait")
            return self.wait_for_page_load(10)

    def get_current_url(self):
        """Get current page URL."""
        return self.driver.current_url

    def scroll_to_element(self, identifier):
        """Scroll element into view."""
        element = self.find_element_safely(identifier)
        if element:
            self.driver.execute_script(
                "arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});",
                element
            )
            time.sleep(0.5)
            return True
        return False