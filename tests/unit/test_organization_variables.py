# Updated by Claude AI on 2026-09-10
"""
Tests for config/organization.py's get_organization_variables()/_circle_value()
per-circle resolution and its no-fallback behavior. See PROMPT.md's
"Plan: Multi-Circle Test Coverage" item 4.
"""

import pytest

# Must import app before anything that imports routes.auth/routes.admin - see
# tests/unit/test_multi_circle_isolation.py's comment for the circular-import
# gotcha this avoids.
import app  # noqa: F401

from config.organization import get_organization_variables, ORGANIZATION_NAME, COUNT_EVENT_NAME, COUNT_CONTACT
from tests.test_config import TEST_CIRCLE_SLUG_2

# app fixture comes from tests/unit/conftest.py (shared).


class TestOrganizationVariablesResolveToTheActiveCircle:
    def test_resolves_to_test2_circles_own_values_not_vancouver_or_test(self, app, second_test_circle):
        with app.test_request_context('/', headers={'Host': f'{TEST_CIRCLE_SLUG_2}.cbc.test'}):
            app.preprocess_request()
            org_vars = get_organization_variables()

        # test2's own values (see tests/conftest.py's second_test_circle fixture)
        assert org_vars['organization_name'] == 'Test Organization Two'
        assert org_vars['count_event_name'] == 'Second Test Circle for Isolation Testing'
        assert org_vars['count_contact'] == 'test2-count-contact@example.com'
        assert org_vars['is_cbc'] is False
        assert org_vars['display_timezone'] == 'America/Toronto'

        # Not Vancouver's module constants
        assert org_vars['organization_name'] != ORGANIZATION_NAME
        assert org_vars['count_event_name'] != COUNT_EVENT_NAME
        assert org_vars['count_contact'] != COUNT_CONTACT

        # Not TEST_CIRCLE_SLUG's own values either (the isolation property,
        # not just "differs from Vancouver")
        assert org_vars['count_event_name'] != 'Test Circle used for automated testing of the website code'


class TestOrganizationVariablesHaveNoFallback:
    """There is no default/fallback circle on this platform (see app.py's
    resolve_circle()) - get_organization_variables() must raise rather than
    silently substitute Vancouver's module constants when no circle is resolved,
    otherwise another circle's admins/participants could see or be emailed
    Vancouver's identity. This used to be documented as deliberate fallback
    behavior and was the exact mechanism behind a real cross-circle
    magic-link-subject bug (services/email_service.py) - fixed alongside this."""

    def test_outside_any_request_context_raises(self):
        with pytest.raises(RuntimeError):
            get_organization_variables()

    def test_landing_host_raises(self, app):
        """g.circle is None on the landing host (no single circle makes sense
        there) - same no-fallback behavior as no request context at all."""
        with app.test_request_context('/', headers={'Host': 'cbc.birdcount.ca'}):
            app.preprocess_request()
            with pytest.raises(RuntimeError):
                get_organization_variables()
