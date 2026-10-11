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


def _status(days_remaining, lifetime=90, fingerprint='aa'):
    return tls_common.CertStatus(days_remaining, lifetime, fingerprint)


LIFETIMES = (90, 64, 47)


class TestThresholds:
    """Thresholds are fractions of the certificate's own lifetime, so they keep working as
    Let's Encrypt shortens lifetimes (90 -> 64 days in 2027, 45 in 2028, 47-day public maximum)."""

    @pytest.mark.parametrize('lifetime', LIFETIMES)
    def test_renew_at_a_third_and_alert_at_a_sixth(self, lifetime):
        assert tls_common.renew_threshold_days(lifetime) == pytest.approx(lifetime / 3)
        assert tls_common.alert_threshold_days(lifetime) == pytest.approx(lifetime / 6)

    @pytest.mark.parametrize('lifetime', LIFETIMES)
    def test_alert_threshold_is_below_renew_threshold(self, lifetime):
        # otherwise the watchdog would alert before renewal had even been attempted
        assert tls_common.alert_threshold_days(lifetime) < tls_common.renew_threshold_days(lifetime)


class TestRenewDecision:
    @pytest.fixture
    def calls(self, monkeypatch):
        calls = []
        monkeypatch.setattr(renew_certificate, 'issue', lambda staging: calls.append('issue') or Path('/x'))
        monkeypatch.setattr(renew_certificate, 'install_and_verify', lambda live: calls.append('install'))
        monkeypatch.setattr(renew_certificate, 'reusable_certificate', lambda fp: None)
        monkeypatch.setattr(renew_certificate.subprocess, 'run', lambda *a, **k: None)
        return calls

    @staticmethod
    def _args(**kw):
        defaults = dict(staging=False, force=False, no_install=False)
        return type('Args', (), {**defaults, **kw})

    @staticmethod
    def _live(monkeypatch, status):
        monkeypatch.setattr(renew_certificate, 'live_cert_status', lambda host: status)

    @pytest.mark.parametrize('lifetime', LIFETIMES)
    def test_nothing_to_do_just_above_the_renewal_point(self, calls, monkeypatch, lifetime):
        self._live(monkeypatch, _status(lifetime / 3 + 1, lifetime))
        renew_certificate.run(self._args())
        assert calls == []

    @pytest.mark.parametrize('lifetime', LIFETIMES)
    def test_issues_and_installs_just_below_the_renewal_point(self, calls, monkeypatch, lifetime):
        self._live(monkeypatch, _status(lifetime / 3 - 1, lifetime))
        renew_certificate.run(self._args())
        assert calls == ['issue', 'install']

    def test_reuses_an_issued_but_uninstalled_certificate(self, calls, monkeypatch):
        self._live(monkeypatch, _status(20))
        monkeypatch.setattr(renew_certificate, 'reusable_certificate', lambda fp: Path('/prev'))
        renew_certificate.run(self._args())
        assert calls == ['install']

    def test_staging_never_installs(self, calls):
        renew_certificate.run(self._args(staging=True))
        assert calls == ['issue']

    def test_no_install_flag(self, calls, monkeypatch):
        self._live(monkeypatch, _status(5))
        renew_certificate.run(self._args(no_install=True))
        assert calls == ['issue']

    def test_force_renews_despite_plenty_of_time(self, calls, monkeypatch):
        self._live(monkeypatch, _status(80))
        renew_certificate.run(self._args(force=True))
        assert calls == ['issue', 'install']

    def test_an_expired_or_unreadable_live_certificate_triggers_renewal(self, calls, monkeypatch):
        def fail(host):
            raise OSError('certificate has expired')
        monkeypatch.setattr(renew_certificate, 'live_cert_status', fail)
        renew_certificate.run(self._args())
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


@needs_openssl
class TestReusableCertificate:
    @pytest.fixture
    def lineage(self, tmp_path, monkeypatch):
        monkeypatch.setattr(renew_certificate, 'WORK_DIR', tmp_path)
        live = tmp_path / 'config' / 'live' / renew_certificate.CERT_NAME
        live.mkdir(parents=True)
        return live

    def test_none_when_nothing_was_issued(self, lineage):
        assert renew_certificate.reusable_certificate('x') is None

    def test_reuses_a_fresh_certificate_that_is_not_the_served_one(self, lineage, tmp_path):
        (lineage / 'cert.pem').write_text(_self_signed(tmp_path, 'fresh', ['birdcount.ca'], days=64))
        assert renew_certificate.reusable_certificate('different-fingerprint') == lineage

    def test_never_reuses_the_certificate_already_served(self, lineage, tmp_path):
        (lineage / 'cert.pem').write_text(_self_signed(tmp_path, 'served', ['birdcount.ca'], days=64))
        served = tls_common.pem_status(lineage / 'cert.pem').fingerprint
        assert renew_certificate.reusable_certificate(served) is None

    def test_does_not_reuse_one_inside_its_renewal_window(self, lineage, tmp_path, monkeypatch):
        (lineage / 'cert.pem').write_text(_self_signed(tmp_path, 'old', ['birdcount.ca']))
        monkeypatch.setattr(renew_certificate, 'pem_status', lambda path: _status(10, 90, 'old'))
        assert renew_certificate.reusable_certificate('other') is None


class TestInstallVerification:
    @pytest.fixture
    def setup(self, tmp_path, monkeypatch):
        for name in ('privkey.pem', 'cert.pem', 'chain.pem'):
            (tmp_path / name).write_text('pem')
        monkeypatch.setattr(jelastic_deploy, 'install', lambda *pems: '2027-01-09')
        monkeypatch.setattr(renew_certificate, 'pem_status', lambda path: _status(64, 64, 'new'))
        monkeypatch.setattr(renew_certificate.time, 'sleep', lambda s: None)
        return tmp_path

    def test_passes_when_every_host_serves_the_new_certificate(self, setup, monkeypatch):
        monkeypatch.setattr(renew_certificate, 'live_cert_status', lambda host: _status(64, 64, 'new'))
        renew_certificate.install_and_verify(setup)

    def test_waits_for_the_web_server_to_pick_up_the_new_certificate(self, setup, monkeypatch):
        answers = iter([OSError('timed out'), _status(5, 90, 'old'), _status(64, 64, 'new')])

        def status(host):
            answer = next(answers, _status(64, 64, 'new'))
            if isinstance(answer, Exception):
                raise answer
            return answer
        monkeypatch.setattr(renew_certificate, 'live_cert_status', status)
        renew_certificate.install_and_verify(setup)

    def test_fails_when_a_host_keeps_serving_the_old_certificate(self, setup, monkeypatch):
        monkeypatch.setattr(renew_certificate, 'live_cert_status', lambda host: _status(5, 90, 'old'))
        with pytest.raises(RuntimeError, match='not serving the new certificate'):
            renew_certificate.install_and_verify(setup)


class TestExpiryWatchdog:
    @pytest.fixture
    def alerts(self, monkeypatch):
        sent = []
        monkeypatch.setattr(check_expiry, 'send_alert', lambda subject, body: sent.append(body) or True)
        return sent

    @pytest.mark.parametrize('lifetime', LIFETIMES)
    def test_quiet_just_above_the_alert_point(self, alerts, monkeypatch, lifetime):
        monkeypatch.setattr(check_expiry, 'live_cert_status',
                            lambda host: _status(lifetime / 6 + 1, lifetime))
        assert check_expiry.main([]) == 0
        assert alerts == []

    @pytest.mark.parametrize('lifetime', LIFETIMES)
    def test_alerts_just_below_the_alert_point(self, alerts, monkeypatch, lifetime):
        monkeypatch.setattr(check_expiry, 'live_cert_status',
                            lambda host: _status(lifetime / 6 - 1, lifetime))
        assert check_expiry.main([]) == 1
        assert len(alerts) == 1 and 'days remaining' in alerts[0]

    def test_alerts_when_verification_fails(self, alerts, monkeypatch):
        def fail(host):
            raise OSError('handshake failed')
        monkeypatch.setattr(check_expiry, 'live_cert_status', fail)
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
