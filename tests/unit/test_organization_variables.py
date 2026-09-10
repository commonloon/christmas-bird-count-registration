# Updated by Claude AI on 2026-09-09
"""
Tests for config/organization.py's get_organization_variables()/_circle_value()
per-circle resolution and its documented fallback behavior. See PROMPT.md's
"Plan: Multi-Circle Test Coverage" item 4.
"""

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


class TestOrganizationVariablesFallback:
    """Documented CURRENT behavior, not something to "fix" here - outside any
    request context (a script, or the landing host where g.circle is None),
    values fall back to the Vancouver module constants. This is exactly the
    mechanism behind the known cross-circle magic-link-subject bug
    (services/email_service.py, PROMPT.md open item) - pinning it here gives
    that future fix a regression guard for free, and documents that this
    fallback is deliberate, not an oversight to "just fix" blindly."""

    def test_outside_any_request_context_falls_back_to_vancouver_constants(self):
        org_vars = get_organization_variables()
        assert org_vars['organization_name'] == ORGANIZATION_NAME
        assert org_vars['count_event_name'] == COUNT_EVENT_NAME
        assert org_vars['count_contact'] == COUNT_CONTACT

    def test_landing_host_falls_back_to_vancouver_constants(self, app):
        """g.circle is None on the landing host (no single circle makes sense
        there) - same fallback as no request context at all."""
        with app.test_request_context('/', headers={'Host': 'cbc.birdcount.ca'}):
            app.preprocess_request()
            org_vars = get_organization_variables()

        assert org_vars['organization_name'] == ORGANIZATION_NAME
        assert org_vars['count_event_name'] == COUNT_EVENT_NAME
        assert org_vars['count_contact'] == COUNT_CONTACT
