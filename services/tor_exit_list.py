# Updated by Claude AI on 2026-10-22
"""
Tor exit-node list, used to refuse registration form submissions that arrive through Tor.

Registration spam has come in through Tor exit relays, and people registering for a bird count
have no need for it. Only POST /register consults this list - browsing and login are unaffected.

The list is the Tor Project's own bulk exit list. `refresh_tor_exit_list()` is run from the
hourly `flask tick-scheduled-emails` cron (services/scheduler_cli.py), downloads at most every
REFRESH_INTERVAL_HOURS, and keeps the result in app_settings, so every web worker shares one copy.

Fail-open throughout: a list that is missing, unreadable or older than MAX_LIST_AGE_HOURS blocks
nobody (a stale list would start blocking addresses since reassigned to ordinary users), and a
download that looks wrong - far too small, too large, or much smaller than the previous list -
is discarded rather than stored.
"""

import ipaddress
import logging
import threading
import time
import urllib.request
from datetime import datetime, timedelta, timezone

from config.database import get_db_session
from models.app_settings import AppSettingsModel

logger = logging.getLogger(__name__)

TOR_EXIT_LIST_URL = 'https://check.torproject.org/torbulkexitlist'
FETCH_TIMEOUT_SECONDS = 20
MAX_DOWNLOAD_BYTES = 1_000_000

REFRESH_INTERVAL_HOURS = 6
MAX_LIST_AGE_HOURS = 72

# The live list is on the order of a thousand addresses; anything far outside this is not it.
MIN_PLAUSIBLE_ENTRIES = 100
MAX_PLAUSIBLE_ENTRIES = 20000
# A new list under this fraction of the stored one is treated as a truncated download.
MIN_FRACTION_OF_PREVIOUS = 0.5

IPS_KEY = 'tor_exit_ips'
REFRESHED_AT_KEY = 'tor_exit_ips_refreshed_at'

# In-process cache of the parsed list, so a registration POST costs no query most of the time.
# Per-worker staleness of a few minutes is irrelevant for a list that changes over hours.
CACHE_TTL_SECONDS = 600
_cache = {'loaded_at': None, 'ips': frozenset()}
_cache_lock = threading.Lock()


def parse_exit_list(text):
    """Valid, publicly routable IP addresses from the list text (one per line); anything else is dropped."""
    ips = set()
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        try:
            address = ipaddress.ip_address(line)
        except ValueError:
            continue
        if address.is_global:
            ips.add(str(address))
    return ips


def _download():
    request = urllib.request.Request(TOR_EXIT_LIST_URL, headers={'User-Agent': 'cbc-registration-exit-list-refresh'})
    with urllib.request.urlopen(request, timeout=FETCH_TIMEOUT_SECONDS) as response:
        return response.read(MAX_DOWNLOAD_BYTES + 1).decode('utf-8', errors='replace')


def _stored_count(settings):
    stored = settings.get(IPS_KEY)
    return len(stored.split()) if stored else 0


def refresh_tor_exit_list(now=None, fetch=None, force=False):
    """Download and store the list if it is due. `now` and `fetch` are injectable for tests.
    Returns a JSON-serializable summary: {'status': 'fresh'|'updated'|'rejected'|'failed', ...}."""
    now = now or datetime.now(timezone.utc)
    settings = AppSettingsModel(get_db_session())

    last = settings.get(REFRESHED_AT_KEY)
    if last and not force and now - datetime.fromisoformat(last) < timedelta(hours=REFRESH_INTERVAL_HOURS):
        return {'status': 'fresh', 'entries': _stored_count(settings)}

    try:
        text = (fetch or _download)()
    except Exception as e:
        logger.error(f'Tor exit list download failed: {e}')
        return {'status': 'failed', 'error': type(e).__name__}

    ips = parse_exit_list(text)
    previous = _stored_count(settings)
    if not MIN_PLAUSIBLE_ENTRIES <= len(ips) <= MAX_PLAUSIBLE_ENTRIES:
        reason = f'{len(ips)} entries is outside the plausible range'
    elif previous and len(ips) < previous * MIN_FRACTION_OF_PREVIOUS:
        reason = f'{len(ips)} entries is under half of the stored {previous}'
    else:
        reason = None
    if reason:
        logger.error(f'Tor exit list download discarded: {reason}')
        return {'status': 'rejected', 'reason': reason}

    settings.set(IPS_KEY, '\n'.join(sorted(ips)), updated_by='tor-exit-list-refresh')
    settings.set(REFRESHED_AT_KEY, now.isoformat(), updated_by='tor-exit-list-refresh')
    with _cache_lock:
        _cache['loaded_at'] = None   # next lookup in this process reloads
    logger.info(f'Tor exit list updated: {len(ips)} entries (previously {previous})')
    return {'status': 'updated', 'entries': len(ips), 'previous': previous}


def _load_ips(now):
    settings = AppSettingsModel(get_db_session())
    refreshed = settings.get(REFRESHED_AT_KEY)
    if not refreshed or now - datetime.fromisoformat(refreshed) > timedelta(hours=MAX_LIST_AGE_HOURS):
        return frozenset()
    return frozenset((settings.get(IPS_KEY) or '').split())


def is_tor_exit(ip_address, now=None):
    """True if the address is on the current Tor exit list. False on any problem (fail-open)."""
    try:
        with _cache_lock:
            expired = _cache['loaded_at'] is None or time.monotonic() - _cache['loaded_at'] > CACHE_TTL_SECONDS
        if expired:
            ips = _load_ips(now or datetime.now(timezone.utc))
            with _cache_lock:
                _cache['ips'] = ips
                _cache['loaded_at'] = time.monotonic()
        with _cache_lock:
            return ip_address in _cache['ips']
    except Exception as e:
        logger.error(f'Tor exit list lookup failed: {e}')
        return False
