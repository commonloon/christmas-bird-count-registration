# Updated by Claude AI on 2026-10-22
"""
Tests for services/bot_attempts.py: bounded storage of rejected registration attempts,
the daily summary / hourly spike alerts, and pruning. Uses the local dev Postgres; the
bot_* tables and their app_settings state keys are cleared around every test.
"""

from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from models.db import get_engine
from services import bot_attempts
from services.bot_attempts import (
    build_daily_summary, ip_prefix, record_bot_attempt, run_bot_attempt_notifications,
    user_agent_family,
)

# A January (PST, UTC-8) day, so 06:00 Pacific is 14:00 UTC with no DST ambiguity
DAY = date(2026, 1, 14)
YESTERDAY_NOON = datetime(2026, 1, 14, 20, 0, tzinfo=timezone.utc)   # 12:00 Pacific on DAY
SUMMARY_TIME = datetime(2026, 1, 15, 14, 5, tzinfo=timezone.utc)     # 06:05 Pacific on DAY+1
ATTACKER_TEXT = 'Confirm your transaction here httpsEVILPAYLOAD'
UA = f'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/125.0.0.0 Safari/537.36 {ATTACKER_TEXT}'


def _scalar(sql, **params):
    with get_engine().connect() as conn:
        return conn.execute(text(sql), params).scalar()


def _record(now=YESTERDAY_NOON, reason='honeypot', circle='test', ip='203.0.113.7', **kw):
    return record_bot_attempt(reason, circle, ip, kw.get('ua', UA), kw.get('email', 'x@fextemp.com'),
                              kw.get('name', ATTACKER_TEXT), now=now)


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    def wipe():
        with get_engine().begin() as conn:
            for table in ('bot_attempt_hourly', 'bot_attempt_daily', 'bot_attempt_sample'):
                conn.execute(text(f'DELETE FROM {table}'))
            conn.execute(text("DELETE FROM app_settings WHERE key IN (:a, :b)"),
                         {'a': bot_attempts.SUMMARY_STATE_KEY, 'b': bot_attempts.ALERT_STATE_KEY})
    wipe()
    monkeypatch.setattr(bot_attempts, 'MAX_WRITES_PER_MINUTE', 10_000)
    bot_attempts._window.update(minute=None, writes=0, dropped=0)
    yield
    wipe()


@pytest.fixture
def sent():
    calls = []
    def send(to, subject, body):
        calls.append({'to': to, 'subject': subject, 'body': body})
        return True
    send.calls = calls
    return send


def test_user_agent_family_is_fixed_vocabulary():
    assert user_agent_family(UA) == 'Chrome/125 Windows'
    assert user_agent_family('') == 'none'
    assert user_agent_family('Click here to pay now') == 'other'
    assert ATTACKER_TEXT not in user_agent_family(UA)


def test_ip_prefix():
    assert ip_prefix('203.0.113.7') == '203.0.113.0/24'
    assert ip_prefix('2001:db8:1:2::5') == '2001:db8:1::/48'
    assert ip_prefix('not an ip') == ''


def test_record_writes_every_tier():
    assert _record()
    assert _scalar("SELECT sum(count) FROM bot_attempt_hourly") == 1
    daily = {(d, v) for d, v in get_engine().connect().execute(
        text("SELECT dimension, value FROM bot_attempt_daily WHERE day = :d"), {'d': DAY})}
    assert {('total', 'all'), ('circle', 'test'), ('reason', 'honeypot'), ('ip', '203.0.113.7'),
            ('ip_prefix', '203.0.113.0/24'), ('user_agent', 'Chrome/125 Windows'),
            ('email_domain', 'fextemp.com')} <= daily
    assert _scalar("SELECT count(*) FROM bot_attempt_sample") == 1


def test_daily_dimension_is_capped_with_other_bucket(monkeypatch):
    monkeypatch.setattr(bot_attempts, 'MAX_VALUES_PER_DAY_DIMENSION', 3)
    for i in range(8):
        _record(ip=f'198.51.100.{i}')
    assert _scalar("SELECT count(*) FROM bot_attempt_daily WHERE day = :d AND dimension = 'ip'", d=DAY) == 4
    assert _scalar("SELECT count FROM bot_attempt_daily WHERE dimension = 'ip' AND value = '(other)'") == 5
    assert _scalar("SELECT count FROM bot_attempt_daily WHERE dimension = 'total'") == 8


def test_sample_is_a_fixed_size_ring_keeping_the_newest(monkeypatch):
    monkeypatch.setattr(bot_attempts, 'SAMPLE_RING_SIZE', 5)
    for i in range(12):
        _record(ip=f'198.51.100.{i}')
    assert _scalar("SELECT count(*) FROM bot_attempt_sample") == 5
    assert _scalar("SELECT count(*) FROM bot_attempt_sample WHERE ip = '198.51.100.11'") == 1
    assert _scalar("SELECT count(*) FROM bot_attempt_sample WHERE ip = '198.51.100.0'") == 0


def test_write_throttle_counts_what_it_drops(monkeypatch):
    monkeypatch.setattr(bot_attempts, 'MAX_WRITES_PER_MINUTE', 3)
    results = [_record() for _ in range(6)]
    assert results == [True] * 3 + [False] * 3
    # first attempt of the next minute flushes the 3 dropped into the totals
    assert _record(now=YESTERDAY_NOON + timedelta(minutes=1))
    assert _scalar("SELECT count FROM bot_attempt_daily WHERE dimension = 'total'") == 7
    assert _scalar("SELECT count FROM bot_attempt_daily WHERE dimension = 'reason' AND value = 'rate_capped'") == 3
    assert _scalar("SELECT sum(count) FROM bot_attempt_hourly") == 7


def test_record_never_raises(monkeypatch):
    def boom():
        raise RuntimeError('db down')
    monkeypatch.setattr(bot_attempts, 'get_engine', boom)
    assert _record() is False


def test_daily_summary_sent_once_in_window_and_has_no_attacker_text(sent):
    for _ in range(3):
        _record()
    result = run_bot_attempt_notifications(SUMMARY_TIME, sent)
    assert result['summary_sent'] and len(sent.calls) == 1
    body = sent.calls[0]['body']
    assert 'rejected on 2026-01-14 (Pacific): 3' in body
    assert '203.0.113.0/24' in body and 'Chrome/125 Windows' in body and 'fextemp.com' in body
    assert ATTACKER_TEXT not in body and 'EVILPAYLOAD' not in body
    # same window, later tick: not sent again
    run_bot_attempt_notifications(SUMMARY_TIME + timedelta(hours=1), sent)
    assert len(sent.calls) == 1


def test_daily_summary_not_sent_when_nothing_happened_or_outside_window(sent):
    run_bot_attempt_notifications(SUMMARY_TIME, sent)
    assert sent.calls == []
    _record()
    run_bot_attempt_notifications(SUMMARY_TIME - timedelta(hours=2), sent)     # 04:05 Pacific
    run_bot_attempt_notifications(SUMMARY_TIME + timedelta(hours=4), sent)     # 10:05 Pacific
    assert sent.calls == []


def test_daily_summary_retried_after_send_failure():
    _record()
    outcomes = iter([False, True])
    attempts = []
    def flaky(to, subject, body):
        attempts.append(1)
        return next(outcomes)
    assert run_bot_attempt_notifications(SUMMARY_TIME, flaky)['errors'] == 1
    assert run_bot_attempt_notifications(SUMMARY_TIME + timedelta(hours=1), flaky)['summary_sent']
    assert len(attempts) == 2


def test_hourly_alert_needs_more_than_threshold_and_respects_cooldown(sent):
    base = datetime(2026, 1, 15, 9, 30, tzinfo=timezone.utc)
    for _ in range(10):
        _record(now=base)
    run_bot_attempt_notifications(base.replace(hour=10, minute=5), sent)
    assert sent.calls == []                                   # exactly 10 is not "more than 10"
    _record(now=base)
    assert run_bot_attempt_notifications(base.replace(hour=10, minute=5), sent)['alert_sent']
    assert 'Bot registration spike: 11' in sent.calls[0]['subject']
    assert 'EVILPAYLOAD' not in sent.calls[0]['body']
    # a spike in the next hour is suppressed by the 6h cooldown, allowed after it
    next_hour = base.replace(hour=11)
    for _ in range(11):
        _record(now=next_hour)
    run_bot_attempt_notifications(base.replace(hour=12, minute=5), sent)
    assert len(sent.calls) == 1
    later = base.replace(hour=16)
    for _ in range(11):
        _record(now=later)
    assert run_bot_attempt_notifications(base.replace(hour=17, minute=5), sent)['alert_sent']


def test_prune_applies_each_retention_tier():
    now = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)
    old_hour = now - timedelta(days=bot_attempts.HOURLY_RETENTION_DAYS + 1)
    _record(now=old_hour)
    _record(now=now - timedelta(days=100))                     # detail dims expired, long dims kept
    _record(now=now - timedelta(days=bot_attempts.LONG_RETENTION_DAYS + 5))
    _record(now=now)
    with get_engine().begin() as conn:
        bot_attempts.prune(conn, now)
    assert _scalar("SELECT count(*) FROM bot_attempt_hourly WHERE hour < :c",
                   c=now - timedelta(days=bot_attempts.HOURLY_RETENTION_DAYS)) == 0
    assert _scalar("SELECT count(*) FROM bot_attempt_daily WHERE dimension = 'ip'") == 2   # 31d and 0d old; 100d and 405d gone
    assert _scalar("SELECT count(*) FROM bot_attempt_daily WHERE dimension = 'total'") == 3


def test_build_daily_summary_none_for_quiet_day():
    with get_engine().connect() as conn:
        assert build_daily_summary(conn, DAY) is None


def test_tick_command_runs_bot_step_only_without_circle_filter(app, monkeypatch, capsys):
    import click
    from services import scheduler_cli
    calls = []
    monkeypatch.setenv('DATABASE_URL', 'unused-here')
    monkeypatch.setattr(scheduler_cli, 'tick', lambda *a, **kw: {
        'attempted': 0, 'succeeded': 0, 'failed': 0, 'expired': 0, 'notified': False, 'skipped_locked': False})
    monkeypatch.setattr(scheduler_cli, 'run_bot_attempt_notifications', lambda: calls.append(1) or {'ok': True})
    command = scheduler_cli.tick_scheduled_emails_command

    # Invoked through the callback rather than CliRunner, which clashes with the root logging handlers here
    with click.Context(command), app.app_context():
        command.callback(circles=())
    assert calls == [1] and '"bot_attempts"' in capsys.readouterr().out

    with click.Context(command), app.app_context():
        command.callback(circles=('test',))
    assert calls == [1] and '"bot_attempts"' not in capsys.readouterr().out
