# Updated by Claude AI on 2026-10-11
"""
Tests for the TLS renewal job (services/tls_renewal/): the installer's safety guard,
the renew/reuse decision logic, the expiry watchdog, and the reserved circle slug.
Nothing here touches the network, certbot, deSEC or FullHost.
"""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'services' / 'tls_renewal'))

import check_expiry  # noqa: E402
import jelastic_deploy  # noqa: E402
import renew_certificate  # noqa: E402
import tls_common  # noqa: E402

needs_openssl = pytest.mark.skipif(shutil.which('openssl') is None, reason='openssl not installed')


def _self_signed(tmp_path, cn, sans, days=90):
    key, cert = tmp_path / f'{cn}.key', tmp_path / f'{cn}.crt'
    subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-keyout', str(key),
                    '-out', str(cert), '-days', str(days), '-subj', f'/CN={cn}',
                    '-addext', 'subjectAltName=' + ','.join(f'DNS:{s}' for s in sans)],
                   check=True, capture_output=True)
    return cert.read_text()


@needs_openssl
class TestInstallGuard:
    def test_accepts_certificate_covering_all_names(self, tmp_path):
        jelastic_deploy._check_installable(_self_signed(tmp_path, 'ok', jelastic_deploy.REQUIRED_NAMES))

    def test_refuses_missing_name(self, tmp_path):
        cert = _self_signed(tmp_path, 'partial', ['*.birdcount.ca', 'birdcount.ca'])
        with pytest.raises(RuntimeError, match=r'\*\.cbc\.birdcount\.ca'):
            jelastic_deploy._check_installable(cert)

    def test_refuses_staging_issuer(self, tmp_path):
        cert = _self_signed(tmp_path, '(STAGING) Fake CA', jelastic_deploy.REQUIRED_NAMES)
        with pytest.raises(RuntimeError, match='staging'):
            jelastic_deploy._check_installable(cert)


class TestRenewDecision:
    @pytest.fixture
    def calls(self, monkeypatch):
        calls = []
        monkeypatch.setattr(renew_certificate, 'issue', lambda staging: calls.append('issue') or Path('/x'))
        monkeypatch.setattr(renew_certificate, 'install_and_verify', lambda live: calls.append('install'))
        monkeypatch.setattr(renew_certificate, 'reusable_certificate', lambda: None)
        monkeypatch.setattr(renew_certificate.subprocess, 'run', lambda *a, **k: None)
        return calls

    @staticmethod
    def _args(**kw):
        defaults = dict(staging=False, force=False, no_install=False)
        return type('Args', (), {**defaults, **kw})

    def test_nothing_to_do_when_plenty_of_time_left(self, calls, monkeypatch):
        monkeypatch.setattr(renew_certificate, 'live_days_remaining', lambda host: 45)
        renew_certificate.run(self._args())
        assert calls == []

    def test_issues_and_installs_when_close_to_expiry(self, calls, monkeypatch):
        monkeypatch.setattr(renew_certificate, 'live_days_remaining', lambda host: 20)
        renew_certificate.run(self._args())
        assert calls == ['issue', 'install']

    def test_reuses_an_issued_but_uninstalled_certificate(self, calls, monkeypatch):
        monkeypatch.setattr(renew_certificate, 'live_days_remaining', lambda host: 20)
        monkeypatch.setattr(renew_certificate, 'reusable_certificate', lambda: Path('/prev'))
        renew_certificate.run(self._args())
        assert calls == ['install']

    def test_staging_never_installs(self, calls):
        renew_certificate.run(self._args(staging=True))
        assert calls == ['issue']

    def test_no_install_flag(self, calls, monkeypatch):
        monkeypatch.setattr(renew_certificate, 'live_days_remaining', lambda host: 5)
        renew_certificate.run(self._args(no_install=True))
        assert calls == ['issue']

    def test_force_ignores_expiry_check(self, calls, monkeypatch):
        def boom(host):
            raise AssertionError('expiry should not be checked with --force')
        monkeypatch.setattr(renew_certificate, 'live_days_remaining', boom)
        renew_certificate.run(self._args(force=True))
        assert calls == ['issue', 'install']

    def test_failure_sends_alert_and_reraises(self, monkeypatch):
        alerts = []
        monkeypatch.setattr(renew_certificate, 'send_alert', lambda subject, body: alerts.append(subject))
        monkeypatch.setattr(renew_certificate, 'run', lambda args: (_ for _ in ()).throw(RuntimeError('x')))
        monkeypatch.setattr(sys, 'argv', ['renew_certificate.py'])
        with pytest.raises(RuntimeError):
            renew_certificate.main()
        assert alerts == ['TLS certificate renewal FAILED']

    def test_staging_failure_does_not_alert(self, monkeypatch):
        alerts = []
        monkeypatch.setattr(renew_certificate, 'send_alert', lambda subject, body: alerts.append(subject))
        monkeypatch.setattr(renew_certificate, 'run', lambda args: (_ for _ in ()).throw(RuntimeError('x')))
        monkeypatch.setattr(sys, 'argv', ['renew_certificate.py', '--staging'])
        with pytest.raises(RuntimeError):
            renew_certificate.main()
        assert alerts == []


class TestExpiryWatchdog:
    @pytest.fixture
    def alerts(self, monkeypatch):
        sent = []
        monkeypatch.setattr(check_expiry, 'send_alert', lambda subject, body: sent.append(body) or True)
        return sent

    def test_quiet_when_healthy(self, alerts, monkeypatch):
        monkeypatch.setattr(check_expiry, 'live_days_remaining', lambda host: 40)
        assert check_expiry.main([]) == 0
        assert alerts == []

    def test_alerts_when_below_threshold(self, alerts, monkeypatch):
        monkeypatch.setattr(check_expiry, 'live_days_remaining', lambda host: 10)
        assert check_expiry.main([]) == 1
        assert len(alerts) == 1 and 'only 10.0 days' in alerts[0]

    def test_alerts_when_verification_fails(self, alerts, monkeypatch):
        def fail(host):
            raise OSError('handshake failed')
        monkeypatch.setattr(check_expiry, 'live_days_remaining', fail)
        assert check_expiry.main([]) == 1
        assert 'could not verify' in alerts[0]


class TestAlertSender:
    def test_not_sent_without_credentials(self, monkeypatch, capsys):
        for var in ('SMTP2GO_USERNAME', 'SMTP2GO_PASSWORD'):
            monkeypatch.delenv(var, raising=False)
        assert tls_common.send_alert('subject', 'body') is False
        assert 'NOT sent' in capsys.readouterr().err

    def test_goes_to_every_super_admin_from_the_default_sender(self, monkeypatch):
        from config.admins import get_admin_emails
        sent = []

        class FakeSMTP:
            def __init__(self, host, port, timeout=None):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def starttls(self):
                pass

            def login(self, user, password):
                pass

            def send_message(self, msg):
                sent.append(msg)

        monkeypatch.setattr(tls_common.smtplib, 'SMTP', FakeSMTP)
        monkeypatch.setenv('SMTP2GO_USERNAME', 'u')
        monkeypatch.setenv('SMTP2GO_PASSWORD', 'p')
        monkeypatch.delenv('FROM_EMAIL', raising=False)
        assert tls_common.send_alert('subject', 'body') is True
        assert set(a.strip() for a in sent[0]['To'].split(',')) == set(get_admin_emails())
        assert sent[0]['From'] == tls_common._default_sender()

    def test_from_email_env_overrides_default_sender(self, monkeypatch):
        monkeypatch.setenv('FROM_EMAIL', 'birdcount@example.org')
        assert tls_common._default_sender() == 'birdcount@example.org'


def test_acme_slug_is_reserved(super_admin_client):
    """acme.birdcount.ca is the deSEC challenge zone, so no circle may take that slug."""
    from config.database import get_db_session
    from models.circle import CircleModel
    response = super_admin_client.post('/bigbird/circles/new', data={'slug': 'acme', 'circle_name': 'Acme'})
    assert b'reserved' in response.data
    assert CircleModel(get_db_session()).get_by_slug('acme') is None
