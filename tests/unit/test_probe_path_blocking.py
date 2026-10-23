# Updated by Claude AI on 2026-10-22
"""
Scanner-only paths (/.env, /wp-login.php, ...) that match no route block the client IP
immediately; ordinary 404s and real routes must not.
"""

import re

import pytest

from config.database import get_db_session
from config.ip_blocking import PROBE_PATH_PATTERN
from models.db import BlockedIP
from services.ip_blocker import IPBlockerService

PROBE_RE = re.compile(PROBE_PATH_PATTERN, re.IGNORECASE)
PUBLIC_IP = '8.8.4.4'   # documentation ranges (192.0.2/24, 198.51.100/24) count as private to is_blockable_ip


@pytest.mark.parametrize('path', [
    '/.env', '/.env.production', '/app/.env', '/.git/config', '/.aws/credentials', '/.claude/settings.json',
    '/wp-login.php', '/wordpress/', '/xmlrpc.php', '/cgi-bin/luci', '/actuator/health', '/phpinfo.php',
    '/backup.sql', '/site.zip', '/config.json', '/appsettings.Production.json', '/vendor/phpunit/x/eval-stdin.php',
])
def test_probe_paths_match(path):
    assert PROBE_RE.search(path)


@pytest.mark.parametrize('path', [
    '/', '/register', '/success', '/map', '/api/areas', '/api/circles/vancouver/logo', '/auth/login',
    '/bigbird/participants', '/static/css/main.css', '/static/vendor/bootstrap-icons/bootstrap-icons.min.css',
    '/static/icons/bird-favicon.svg', '/robots.txt', '/favicon.ico', '/.well-known/acme-challenge/abc',
    '/login', '/forgot-password', '/contact',
])
def test_legitimate_and_merely_missing_paths_do_not_match(path):
    assert not PROBE_RE.search(path)


@pytest.fixture
def clean_block():
    db = get_db_session()
    db.query(BlockedIP).filter_by(ip_address=PUBLIC_IP).delete()
    db.commit()
    yield db
    db.query(BlockedIP).filter_by(ip_address=PUBLIC_IP).delete()
    db.commit()


def test_probe_blocks_immediately_and_records_reason(clean_block):
    blocker = IPBlockerService(clean_block)
    assert blocker.trigger_probe_block(PUBLIC_IP, '/.env', 'curl/8') == PUBLIC_IP
    row = clean_block.query(BlockedIP).filter_by(ip_address=PUBLIC_IP).one()
    assert row.reason == 'probe_path' and row.last_violation_url == '/.env'
    assert blocker.is_blocked(PUBLIC_IP)


def test_ordinary_missing_page_is_not_blocked_by_probe_check(clean_block):
    assert IPBlockerService(clean_block).trigger_probe_block(PUBLIC_IP, '/no-such-page') is None
    assert clean_block.query(BlockedIP).filter_by(ip_address=PUBLIC_IP).first() is None


def test_probe_from_non_public_address_is_not_blocked(clean_block):
    IPBlockerService(clean_block).trigger_probe_block('127.0.0.1', '/.env')
    assert clean_block.query(BlockedIP).filter_by(ip_address='127.0.0.1').first() is None
