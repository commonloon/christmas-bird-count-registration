# Updated by Claude AI on 2026-10-22
"""
Tor exit list: parsing, download sanity checks, staleness, and the /register refusal.
"""

from datetime import datetime, timedelta, timezone

import pytest

from config.database import get_db_session
from models.app_settings import AppSettingsModel
from models.db import AppSetting
from services import tor_exit_list
from services.tor_exit_list import is_tor_exit, parse_exit_list, refresh_tor_exit_list
from tests.unit.test_registration_spam_defenses import _form

TOR_IP = '185.220.101.108'
NOW = datetime(2026, 10, 22, 12, 0, tzinfo=timezone.utc)


def _list_text(count=150, extra=''):
    return '\n'.join(f'185.220.{i // 250}.{i % 250 + 1}' for i in range(count)) + '\n' + extra


@pytest.fixture(autouse=True)
def clean_settings():
    def wipe():
        db = get_db_session()
        db.query(AppSetting).filter(AppSetting.key.in_([tor_exit_list.IPS_KEY, tor_exit_list.REFRESHED_AT_KEY])).delete(
            synchronize_session=False)
        db.commit()
        tor_exit_list._cache.update(loaded_at=None, ips=frozenset())
    wipe()
    yield
    wipe()


def _store(ips, refreshed_at=None):
    settings = AppSettingsModel(get_db_session())
    settings.set(tor_exit_list.IPS_KEY, '\n'.join(ips))
    settings.set(tor_exit_list.REFRESHED_AT_KEY, (refreshed_at or datetime.now(timezone.utc)).isoformat())
    tor_exit_list._cache.update(loaded_at=None, ips=frozenset())


def test_parse_keeps_only_public_ip_addresses():
    text = '# comment\n185.220.101.108\n\n  45.66.35.46  \nnot-an-ip\n10.0.0.1\n127.0.0.1\n2a0b:f4c2::1\n999.1.1.1\n'
    assert parse_exit_list(text) == {'185.220.101.108', '45.66.35.46', '2a0b:f4c2::1'}


def test_refresh_stores_a_plausible_list():
    result = refresh_tor_exit_list(now=NOW, fetch=lambda: _list_text(150, TOR_IP))
    assert result == {'status': 'updated', 'entries': 151, 'previous': 0}
    assert TOR_IP in AppSettingsModel(get_db_session()).get(tor_exit_list.IPS_KEY).split()


def test_refresh_is_skipped_while_fresh():
    refresh_tor_exit_list(now=NOW, fetch=lambda: _list_text())
    result = refresh_tor_exit_list(now=NOW + timedelta(hours=1), fetch=lambda: pytest.fail('should not download'))
    assert result['status'] == 'fresh'
    assert refresh_tor_exit_list(now=NOW + timedelta(hours=7), fetch=lambda: _list_text())['status'] == 'updated'


@pytest.mark.parametrize('count', [0, 20, 20001])
def test_implausible_sizes_are_rejected(count):
    result = refresh_tor_exit_list(now=NOW, fetch=lambda: _list_text(count))
    assert result['status'] == 'rejected'
    assert AppSettingsModel(get_db_session()).get(tor_exit_list.IPS_KEY) is None


def test_list_that_shrinks_by_more_than_half_is_rejected_and_old_one_kept():
    refresh_tor_exit_list(now=NOW, fetch=lambda: _list_text(300))
    result = refresh_tor_exit_list(now=NOW + timedelta(hours=7), fetch=lambda: _list_text(120))
    assert result['status'] == 'rejected'
    assert len(AppSettingsModel(get_db_session()).get(tor_exit_list.IPS_KEY).split()) == 300


def test_download_failure_keeps_old_list():
    refresh_tor_exit_list(now=NOW, fetch=lambda: _list_text(150))

    def boom():
        raise OSError('network down')

    result = refresh_tor_exit_list(now=NOW + timedelta(hours=7), fetch=boom)
    assert result['status'] == 'failed'
    assert len(AppSettingsModel(get_db_session()).get(tor_exit_list.IPS_KEY).split()) == 150


def test_is_tor_exit_matches_stored_list():
    _store([TOR_IP])
    assert is_tor_exit(TOR_IP)
    assert not is_tor_exit('8.8.8.8')


def test_stale_list_blocks_nobody():
    _store([TOR_IP], refreshed_at=datetime.now(timezone.utc) - timedelta(hours=tor_exit_list.MAX_LIST_AGE_HOURS + 1))
    assert not is_tor_exit(TOR_IP)


def test_no_list_blocks_nobody():
    assert not is_tor_exit(TOR_IP)


def test_lookup_error_fails_open(monkeypatch):
    monkeypatch.setattr(tor_exit_list, '_load_ips', lambda now: (_ for _ in ()).throw(RuntimeError('db down')))
    assert not is_tor_exit(TOR_IP)


def test_register_from_tor_exit_is_refused_and_recorded(app, client, monkeypatch):
    _store([TOR_IP])
    recorded = []
    monkeypatch.setattr('routes.main.record_bot_attempt', lambda *a, **kw: recorded.append(a[0]))
    response = client.post('/register', data=_form(app), environ_base={'REMOTE_ADDR': TOR_IP})
    assert response.status_code == 302 and '/success' not in response.headers['Location']
    assert recorded == ['tor_exit']


def test_register_from_ordinary_address_is_unaffected(app, client):
    _store([TOR_IP])
    response = client.post('/register', data=_form(app, email='tor-test-ok@example.com'),
                           environ_base={'REMOTE_ADDR': '8.8.8.8'})
    try:
        assert response.status_code == 302 and '/success' in response.headers['Location']
    finally:
        from models.participant import ParticipantModel
        from tests.test_config import TEST_CIRCLE_SLUG
        model = ParticipantModel(get_db_session(), datetime.now().year, TEST_CIRCLE_SLUG)
        for p in model.get_participants_by_email('tor-test-ok@example.com'):
            model.delete_participant(p['id'])
