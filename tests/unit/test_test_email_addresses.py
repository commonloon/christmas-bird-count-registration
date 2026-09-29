# Updated by Claude AI on 2026-09-29
"""The test-mailbox helper and the recipient rule the unit-tier guard enforces
(tests/unit/conftest.py's only_birdcount_plus_recipients)."""

import re

import pytest

from config.email_settings import ALLOWED_FROM_EMAIL_DOMAINS
from services.security import sanitize_email, validate_email_format
from tests.utils.email_addresses import TEST_EMAIL_DOMAIN, is_allowed_test_recipient, make_test_email


class TestMakeTestEmail:
    def test_shape_is_birdcount_plus_tag_and_random_suffix(self):
        assert re.fullmatch(r'birdcount\+audit-[0-9a-f]{8}@naturevancouver\.ca', make_test_email('audit'))

    def test_each_call_is_unique(self):
        assert len({make_test_email('x') for _ in range(50)}) == 50

    def test_is_allowed_and_survives_the_apps_own_email_handling(self):
        address = make_test_email('roundtrip')
        assert is_allowed_test_recipient(address)
        assert validate_email_format(address)
        assert sanitize_email(address) == address

    def test_domain_is_an_allowed_sending_domain(self):
        assert TEST_EMAIL_DOMAIN in ALLOWED_FROM_EMAIL_DOMAINS


class TestIsAllowedTestRecipient:
    @pytest.mark.parametrize('address', [
        'birdcount@naturevancouver.ca',
        'birdcount+anything@naturevancouver.ca',
        'BirdCount+Mixed.Case-1@NatureVancouver.CA',
        '  birdcount+padded@naturevancouver.ca ',
    ])
    def test_allowed(self, address):
        assert is_allowed_test_recipient(address)

    @pytest.mark.parametrize('address', [
        'concurrency-audit-61ec6e3e@example.com',
        'admin@test.com',
        'someone@naturevancouver.ca',
        'birdcount-2025-10-01-345615-0232@naturevancouver.ca',
        'birdcount+tag@example.com',
        'birdcount+@naturevancouver.ca',
        'xbirdcount+tag@naturevancouver.ca',
        'birdcount+tag@naturevancouver.ca.evil.example',
        '',
        None,
    ])
    def test_rejected(self, address):
        assert not is_allowed_test_recipient(address)
