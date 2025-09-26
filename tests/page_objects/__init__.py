# Page Objects for maintainable UI testing
# Updated by Claude AI on 2025-09-25

"""
Page Object Model for Christmas Bird Count registration system.

This module provides maintainable page objects that are resilient to UI changes
by using data attributes and fallback selectors.
"""

from .base_page import BasePage
from .registration_page import RegistrationPage
from .admin_dashboard_page import AdminDashboardPage
from .admin_participants_page import AdminParticipantsPage

__all__ = [
    'BasePage',
    'RegistrationPage',
    'AdminDashboardPage',
    'AdminParticipantsPage'
]