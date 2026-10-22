# Updated by Claude AI on 2026-10-22
"""
The client IP used for rate limiting, IP blocking and bot-attempt records is the connection's
peer address; a client-supplied X-Forwarded-For header must not influence it.
"""

import pytest
from flask import request

from config.rate_limits import get_rate_limit_key
from services.ip_blocker import IPBlockerService, get_client_ip, is_blockable_ip

SPOOFED = {'X-Forwarded-For': '203.0.113.99, 198.51.100.1'}


def test_spoofed_forwarded_header_is_ignored(app):
    with app.test_request_context('/', headers=SPOOFED, environ_base={'REMOTE_ADDR': '192.0.2.10'}):
        assert get_client_ip(request) == '192.0.2.10'
        assert get_rate_limit_key() == '192.0.2.10'


def test_rate_limit_key_and_client_ip_agree_without_header(app):
    with app.test_request_context('/', environ_base={'REMOTE_ADDR': '192.0.2.11'}):
        assert get_client_ip(request) == get_rate_limit_key() == '192.0.2.11'


@pytest.mark.parametrize('ip, expected', [
    ('185.220.101.108', True),
    ('2001:4860:4860::8888', True),
    ('127.0.0.1', False), ('::1', False),
    ('10.1.2.3', False), ('192.168.0.5', False), ('172.16.4.4', False),
    ('169.254.1.1', False),
    ('unknown', False), ('', False),
])
def test_is_blockable_ip(ip, expected):
    assert is_blockable_ip(ip) is expected


def test_add_block_refuses_non_public_addresses():
    class ExplodingSession:
        def __getattr__(self, name):
            raise AssertionError('database must not be touched for a non-public address')

    assert IPBlockerService(ExplodingSession()).add_block('127.0.0.1', 'honeypot_trap') == '127.0.0.1'
