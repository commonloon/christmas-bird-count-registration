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
        return self.navigate_to("/bigbird")

    def navigate_to_login(self):
        """Navigate to login page."""
        return self.navigate_to("/auth/login")

    def is_dashboard_loaded(self):
        """Check if admin dashboard is loaded."""
        # Look for dashboard-specific elements
        # ORDERED FROM MOST LIKELY TO LEAST LIKELY TO SUCCEED (performance optimization)
        dashboard_indicators = [
            (By.PARTIAL_LINK_TEXT, 'Participants'),  # MOST LIKELY - admin nav link always present
            (By.PARTIAL_LINK_TEXT, 'Leaders'),       # Second most likely - admin nav link
            (By.ID, 'dashboard-title'),               # Less likely - may not exist
            (By.ID, 'admin-dashboard'),              # Less likely - may not exist
            (By.XPATH, '//h1[contains(text(), "Dashboard")]'),  # Slower XPath fallback
            (By.CSS_SELECTOR, '.admin-dashboard'),   # Last resort class-based selector
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
            self.is_element_visible((By.XPATH, "//input[@name='email' or @type='email']"))
        )

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
        import re

        # PERFORMANCE OPTIMIZED: Dashboard template now has IDs on statistics
        # Use direct ID lookup (fast) instead of multiple fallback attempts
        stat_mappings = {
            'total-participants': 'total_participants',
            'total-assigned': 'total_assigned',
            'total-unassigned': 'total_unassigned',
            'areas-without-leaders': 'areas_without_leaders',
            'leadership-interested': 'leadership_interested'
        }

        for selector, key in stat_mappings.items():
            # Try direct ID lookup first (now exists in template)
            element = self.find_element_safely((By.ID, selector), timeout=1)
            if element:
                text = element.text.strip()
                # Extract number from text (handle formats like "25" or "25 participants")
                numbers = re.findall(r'\d+', text)
                if numbers:
                    stats[key] = int(numbers[0])
                else:
                    stats[key] = 0
            else:
                # Element not found - may not be present on all dashboard views
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
            (By.CSS_SELECTOR, 'a[href*="/bigbird/participants"]'),
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
            (By.CSS_SELECTOR, 'a[href*="/bigbird/leaders"]'),
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
            (By.CSS_SELECTOR, 'a[href*="/bigbird/unassigned"]'),
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
        return self.navigate_to("/bigbird/dashboard") or self.navigate_to("/bigbird")

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
                '/bigbird/export_csv',
                '/bigbird/participants/export',
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