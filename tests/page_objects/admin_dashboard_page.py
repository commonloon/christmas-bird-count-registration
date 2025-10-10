# Admin Dashboard Page Object
# Updated by Claude AI on 2025-09-25

"""
Page object for the admin dashboard.
Handles admin authentication, navigation, and dashboard functionality.
"""

from .base_page import BasePage
from selenium.webdriver.common.by import By
import logging
import time

logger = logging.getLogger(__name__)


class AdminDashboardPage(BasePage):
    """Page object for the admin dashboard."""

    def navigate_to_admin(self):
        """Navigate to admin dashboard."""
        return self.navigate_to("/admin")

    def navigate_to_login(self):
        """Navigate to login page."""
        return self.navigate_to("/auth/login")

    def is_dashboard_loaded(self):
        """Check if admin dashboard is loaded."""
        # Look for dashboard-specific elements
        # Use tuples to avoid multi-strategy timeouts from string identifiers
        dashboard_indicators = [
            (By.ID, 'dashboard-title'),
            (By.ID, 'admin-dashboard'),
            (By.XPATH, '//h1[contains(text(), "Dashboard")]'),
            (By.CSS_SELECTOR, '.admin-dashboard'),
            (By.PARTIAL_LINK_TEXT, 'Participants'),
            (By.PARTIAL_LINK_TEXT, 'Leaders')
        ]

        # Use short timeout since we're trying multiple selectors
        for indicator in dashboard_indicators:
            element = self.find_element_safely(indicator, timeout=0.5)
            if element and element.is_displayed():
                return True

        return False

    def is_login_page(self):
        """Check if we're on the login page."""
        return (
            'login' in self.get_current_url().lower() or
            self.is_element_visible('google-signin') or
            self.is_element_visible((By.PARTIAL_LINK_TEXT, 'Sign in with Google'))
        )

    def perform_google_oauth_login(self, email, password):
        """
        Perform Google OAuth login flow.

        Args:
            email: Google account email
            password: Google account password

        Returns:
            bool: Success of login process
        """
        logger.info(f"Attempting Google OAuth login for: {email}")

        # Click the Google sign-in button
        signin_selectors = [
            'google-signin',
            (By.PARTIAL_LINK_TEXT, 'Sign in with Google'),
            (By.CSS_SELECTOR, '.google-signin'),
            (By.CSS_SELECTOR, 'button:contains("Google")'),
            (By.ID, 'google-signin-button')
        ]

        clicked = False
        for selector in signin_selectors:
            if self.safe_click(selector):
                clicked = True
                break

        if not clicked:
            logger.error("Could not find Google sign-in button")
            return False

        # Wait for Google OAuth page to load
        time.sleep(2)

        # Handle Google login form
        success = self._handle_google_login_form(email, password)

        if success:
            # Wait for redirect back to admin dashboard
            time.sleep(3)
            return self.is_dashboard_loaded()

        return False

    def _handle_google_login_form(self, email, password):
        """Handle the Google login form (email and password entry)."""
        try:
            # Enter email
            email_selectors = [
                (By.ID, 'identifierId'),
                (By.CSS_SELECTOR, 'input[type="email"]'),
                (By.NAME, 'identifier'),
                (By.CSS_SELECTOR, 'input[autocomplete="username"]')
            ]

            email_entered = False
            for selector in email_selectors:
                element = self.find_element_safely(selector, timeout=5)
                if element:
                    element.clear()
                    element.send_keys(email)
                    email_entered = True
                    break

            if not email_entered:
                logger.error("Could not find email input field")
                return False

            # Click Next button
            next_selectors = [
                (By.ID, 'identifierNext'),
                (By.CSS_SELECTOR, 'button:contains("Next")'),
                (By.CSS_SELECTOR, '[data-id="identifierNext"]'),
                (By.CSS_SELECTOR, 'input[value="Next"]')
            ]

            for selector in next_selectors:
                if self.safe_click(selector):
                    break

            # Wait for password field
            time.sleep(2)

            # Enter password
            password_selectors = [
                (By.NAME, 'password'),
                (By.CSS_SELECTOR, 'input[type="password"]'),
                (By.CSS_SELECTOR, 'input[autocomplete="current-password"]')
            ]

            password_entered = False
            for selector in password_selectors:
                element = self.find_element_safely(selector, timeout=5)
                if element:
                    element.clear()
                    element.send_keys(password)
                    password_entered = True
                    break

            if not password_entered:
                logger.error("Could not find password input field")
                return False

            # Click Sign In button
            signin_selectors = [
                (By.ID, 'passwordNext'),
                (By.CSS_SELECTOR, 'button:contains("Sign in")'),
                (By.CSS_SELECTOR, '[data-id="passwordNext"]'),
                (By.CSS_SELECTOR, 'input[value="Sign in"]')
            ]

            for selector in signin_selectors:
                if self.safe_click(selector):
                    break

            # Wait for potential consent screen or redirect
            time.sleep(3)

            # Handle consent screen if present
            self._handle_oauth_consent_screen()

            return True

        except Exception as e:
            logger.error(f"Google OAuth login failed: {e}")
            return False

    def _handle_oauth_consent_screen(self):
        """Handle OAuth consent screen if present."""
        consent_selectors = [
            (By.CSS_SELECTOR, 'button:contains("Allow")'),
            (By.CSS_SELECTOR, 'button:contains("Continue")'),
            (By.ID, 'submit_approve_access'),
            (By.CSS_SELECTOR, 'input[value="Allow"]')
        ]

        for selector in consent_selectors:
            if self.safe_click(selector, timeout=3):
                logger.info("Handled OAuth consent screen")
                time.sleep(2)
                break

    def get_year_selector_years(self):
        """Get available years from year selector dropdown."""
        year_dropdown = self.find_element_safely('year_selector')
        if not year_dropdown:
            year_dropdown = self.find_element_safely((By.NAME, 'year'))

        if year_dropdown:
            from selenium.webdriver.support.ui import Select
            select = Select(year_dropdown)
            return [int(option.get_attribute('value')) for option in select.options if option.get_attribute('value').isdigit()]

        return []

    def select_year(self, year):
        """Select a year from the year selector."""
        return self.safe_select_dropdown('year_selector', str(year)) or \
               self.safe_select_dropdown((By.NAME, 'year'), str(year))

    def get_dashboard_statistics(self):
        """
        Extract dashboard statistics.

        Returns:
            dict: Dashboard statistics
        """
        stats = {}

        # Common statistic selectors and their keys
        stat_mappings = {
            'total-participants': 'total_participants',
            'total-assigned': 'total_assigned',
            'total-unassigned': 'total_unassigned',
            'areas-without-leaders': 'areas_without_leaders',
            'leadership-interested': 'leadership_interested'
        }

        for selector, key in stat_mappings.items():
            element = self.find_element_safely(selector)
            if element:
                text = element.text.strip()
                # Extract number from text (handle formats like "25 participants")
                import re
                numbers = re.findall(r'\d+', text)
                if numbers:
                    stats[key] = int(numbers[0])
                else:
                    stats[key] = 0
            else:
                # Fallback: look for elements containing the statistic
                fallback_selectors = [
                    (By.CSS_SELECTOR, f'.{selector}'),
                    (By.CSS_SELECTOR, f'*[data-stat="{key}"]'),
                    (By.CSS_SELECTOR, f'#{selector.replace("-", "_")}')
                ]

                found = False
                for fallback in fallback_selectors:
                    element = self.find_element_safely(fallback)
                    if element:
                        text = element.text.strip()
                        import re
                        numbers = re.findall(r'\d+', text)
                        if numbers:
                            stats[key] = int(numbers[0])
                            found = True
                            break

                if not found:
                    stats[key] = None

        return stats

    def get_recent_participants(self):
        """
        Get list of recent participants shown on dashboard.

        Returns:
            list: Recent participant information
        """
        participants = []

        # Look for recent participants table or list
        table_selectors = [
            'recent-participants-table',
            (By.CSS_SELECTOR, '.recent-participants table'),
            (By.CSS_SELECTOR, '#recent-participants table'),
            (By.CSS_SELECTOR, 'table.participants')
        ]

        table = None
        for selector in table_selectors:
            table = self.find_element_safely(selector)
            if table:
                break

        if table:
            # Extract participant data from table rows
            try:
                rows = table.find_elements(By.CSS_SELECTOR, 'tbody tr')
                for row in rows:
                    cells = row.find_elements(By.TAG_NAME, 'td')
                    if len(cells) >= 3:  # Assuming at least name, email, area
                        participant = {
                            'name': cells[0].text.strip(),
                            'email': cells[1].text.strip(),
                            'area': cells[2].text.strip() if len(cells) > 2 else '',
                            'registration_time': cells[3].text.strip() if len(cells) > 3 else ''
                        }
                        participants.append(participant)
            except Exception as e:
                logger.warning(f"Could not extract participant data from table: {e}")

        return participants

    def navigate_to_participants(self):
        """Navigate to participants management page."""
        nav_selectors = [
            (By.PARTIAL_LINK_TEXT, 'Participants'),
            (By.LINK_TEXT, 'Manage Participants'),
            (By.CSS_SELECTOR, 'a[href*="/admin/participants"]'),
            'nav-participants'
        ]

        for selector in nav_selectors:
            if self.safe_click(selector):
                return self.wait_for_url_contains('participants')

        return False

    def navigate_to_leaders(self):
        """Navigate to leaders management page."""
        nav_selectors = [
            (By.PARTIAL_LINK_TEXT, 'Leaders'),
            (By.LINK_TEXT, 'Manage Leaders'),
            (By.CSS_SELECTOR, 'a[href*="/admin/leaders"]'),
            'nav-leaders'
        ]

        for selector in nav_selectors:
            if self.safe_click(selector):
                return self.wait_for_url_contains('leaders')

        return False

    def navigate_to_unassigned(self):
        """Navigate to unassigned participants page."""
        nav_selectors = [
            (By.PARTIAL_LINK_TEXT, 'Unassigned'),
            (By.LINK_TEXT, 'Unassigned Participants'),
            (By.CSS_SELECTOR, 'a[href*="/admin/unassigned"]'),
            'nav-unassigned'
        ]

        for selector in nav_selectors:
            if self.safe_click(selector):
                return self.wait_for_url_contains('unassigned')

        return False

    def click_export_participants_csv(self):
        """Click the export participants CSV button/link."""
        export_selectors = [
            (By.CSS_SELECTOR, 'a[href*="export_csv"]'),  # MOST LIKELY - actual link on dashboard
            (By.PARTIAL_LINK_TEXT, 'Export CSV'),  # Fallback with correct button text
            (By.ID, 'export-csv-button'),  # Less common ID variant
            (By.XPATH, '//button[contains(text(), "Export")]')  # Last resort with XPath
        ]

        for selector in export_selectors:
            if self.safe_click(selector):
                time.sleep(2)  # Wait for download to start
                return True

        return False

    def verify_admin_navigation(self):
        """
        Verify admin navigation elements are present.

        Returns:
            dict: Navigation element availability
        """
        nav_elements = {
            'participants_link': False,
            'leaders_link': False,
            'unassigned_link': False,
            'dashboard_link': False
        }

        # Check for participants link
        if (self.find_element_safely((By.PARTIAL_LINK_TEXT, 'Participants')) or
            self.find_element_safely('nav-participants')):
            nav_elements['participants_link'] = True

        # Check for leaders link
        if (self.find_element_safely((By.PARTIAL_LINK_TEXT, 'Leaders')) or
            self.find_element_safely('nav-leaders')):
            nav_elements['leaders_link'] = True

        # Check for unassigned link
        if (self.find_element_safely((By.PARTIAL_LINK_TEXT, 'Unassigned')) or
            self.find_element_safely('nav-unassigned')):
            nav_elements['unassigned_link'] = True

        # Check for dashboard link
        if (self.find_element_safely((By.PARTIAL_LINK_TEXT, 'Dashboard')) or
            self.find_element_safely('nav-dashboard')):
            nav_elements['dashboard_link'] = True

        return nav_elements

    def navigate_to_dashboard(self):
        """Navigate to admin dashboard."""
        return self.navigate_to("/admin/dashboard") or self.navigate_to("/admin")

    def get_csv_export_content(self):
        """
        Get CSV export content by navigating to CSV export endpoint.

        Returns:
            str or None: CSV content
        """
        try:
            # Get the current URL base
            current_url = self.get_current_url()
            base_url = '/'.join(current_url.split('/')[:3])  # http://domain:port

            # Try different CSV export endpoints
            csv_endpoints = [
                '/admin/export_csv',
                '/admin/participants/export',
                '/export_csv'
            ]

            for endpoint in csv_endpoints:
                try:
                    csv_url = base_url + endpoint
                    self.driver.get(csv_url)
                    time.sleep(2)

                    # Check if we got CSV content
                    page_source = self.driver.page_source
                    if ('text/csv' in self.driver.page_source or
                        ',' in page_source and '\n' in page_source):
                        # Looks like CSV content
                        return page_source.strip()

                except Exception as e:
                    logger.debug(f"Failed to get CSV from {endpoint}: {e}")
                    continue

            # Fallback: try clicking export button and capturing response
            self.navigate_to_dashboard()
            if self.click_export_participants_csv():
                time.sleep(3)
                # Check for download or new page with CSV content
                page_source = self.driver.page_source
                if ',' in page_source and '\n' in page_source:
                    return page_source.strip()

            logger.warning("Could not retrieve CSV export content")
            return None

        except Exception as e:
            logger.error(f"Error getting CSV export content: {e}")
            return None