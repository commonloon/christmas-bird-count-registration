# Updated by Claude AI on 2026-09-29
"""
Addresses tests are allowed to send real email to.

The suite deliberately sends real mail (through SMTP2GO, redirected to the
circle's test recipient when TEST_MODE is on), so every address a test could
email must be birdcount+<uniquifier>@naturevancouver.ca - a plus-addressed
variant of the shared test mailbox. Anything else (example.com, made-up
domains, real people) could bounce, or reach someone if TEST_MODE were ever
off. tests/unit/conftest.py enforces this for the unit tier; the live-server
suites use make_test_email() for anything they register or withdraw.

Not named test_*.py on purpose: pytest would try to collect it.
"""

import re
import secrets

TEST_MAILBOX = 'birdcount'
TEST_EMAIL_DOMAIN = 'naturevancouver.ca'

# birdcount@ itself (the redirect target) or birdcount+<anything sane>@.
_ALLOWED_RECIPIENT = re.compile(r'^birdcount(\+[a-z0-9._+-]+)?@naturevancouver\.ca$')


def make_test_email(tag='test'):
    """A fresh birdcount+<tag>-<random>@naturevancouver.ca address."""
    return f'{TEST_MAILBOX}+{tag}-{secrets.token_hex(4)}@{TEST_EMAIL_DOMAIN}'


def is_allowed_test_recipient(address):
    """True if a test may send real email to this address."""
    return bool(_ALLOWED_RECIPIENT.match((address or '').strip().lower()))
