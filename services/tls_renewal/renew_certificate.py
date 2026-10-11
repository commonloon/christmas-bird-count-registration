# Updated by Claude AI on 2026-10-11
"""Renew the wildcard certificate: certbot + the deSEC DNS-01 hook, then install it.

Stateless by design: each run reads the live certificate and does nothing if more
than a third of its lifetime remains (Let's Encrypt's recommendation; the lifetime
itself is read from the certificate, as it keeps shrinking: 90 -> 64 -> 45 days).
Otherwise it issues a certificate (or reuses one a previous run issued but failed to
install), installs it on the node through the platform API (jelastic_deploy.py), and
verifies every hostname serves it. Any
failure emails an alert and exits non-zero. Installing swaps the node's certificate,
which interrupts HTTPS for roughly 30 seconds - run it in quiet hours.

    renew_certificate.py             # normal daily run (from cron)
    renew_certificate.py --force     # renew even though plenty of time remains
    renew_certificate.py --no-install  # issue only
    renew_certificate.py --staging   # test against Let's Encrypt staging; never installs

Environment: DESEC_TOKEN, JELASTIC_CERT_TOKEN, ACME_EMAIL (not needed for --staging);
for alert email see tls_common.send_alert.
"""
import argparse
import os
import subprocess
import sys
import time
import traceback
from pathlib import Path

from tls_common import CHECK_HOSTS, live_cert_status, pem_status, renew_threshold_days, send_alert

HOOK = Path(__file__).with_name('desec_hook.py')
DOMAINS = ('*.cbc.birdcount.ca', '*.birdcount.ca', 'birdcount.ca')
CHECK_HOST = CHECK_HOSTS[0]
# After installing, each host is polled until it serves the new certificate (the web server
# reloads a moment after the platform reports success).
VERIFY_ATTEMPTS = 12
VERIFY_DELAY = 10
WORK_DIR = Path(os.environ.get('TLS_WORK_DIR', '/tmp/cbc-certbot'))
CERT_NAME = 'birdcount'


def ensure_certbot():
    venv = WORK_DIR / 'venv'
    certbot = venv / 'bin' / 'certbot'
    if not certbot.exists():
        WORK_DIR.mkdir(parents=True, exist_ok=True)
        subprocess.run([sys.executable, '-m', 'venv', str(venv)], check=True)
        subprocess.run([str(venv / 'bin' / 'pip'), 'install', '--quiet', 'certbot'], check=True)
    return certbot


def _config_dir(staging):
    # Separate state so a staging lineage can never collide with the production one.
    return WORK_DIR / ('config-staging' if staging else 'config')


def reusable_certificate(served_fingerprint):
    """Directory of a production certificate issued earlier but not yet installed that still
    has more than a renewal window left, or None. A certificate identical to the one being
    served is never reused: that is already installed, and reinstalling it renews nothing."""
    live = _config_dir(False) / 'live' / CERT_NAME
    cert = live / 'cert.pem'
    if not cert.exists():
        return None
    status = pem_status(cert)
    if status.fingerprint == served_fingerprint:
        return None
    return live if status.days_remaining > renew_threshold_days(status.lifetime_days) else None


def issue(staging):
    certbot = ensure_certbot()
    config_dir = _config_dir(staging)
    cmd = [str(certbot), 'certonly', '--non-interactive', '--agree-tos',
           '--manual', '--preferred-challenges', 'dns',
           '--manual-auth-hook', f'{sys.executable} {HOOK} auth',
           '--manual-cleanup-hook', f'{sys.executable} {HOOK} cleanup',
           '--key-type', 'rsa', '--cert-name', CERT_NAME, '--force-renewal',
           '--config-dir', str(config_dir),
           '--work-dir', str(WORK_DIR / 'work'),
           '--logs-dir', str(WORK_DIR / 'logs')]
    for domain in DOMAINS:
        cmd += ['-d', domain]
    if staging:
        cmd.append('--test-cert')
    email = os.environ.get('ACME_EMAIL')
    if email:
        cmd += ['-m', email]
    elif staging:
        cmd.append('--register-unsafely-without-email')
    else:
        sys.exit('ACME_EMAIL must be set for a production issuance')
    subprocess.run(cmd, check=True)
    return config_dir / 'live' / CERT_NAME


def install_and_verify(live):
    # Imported here so --staging / --no-install runs don't need the Jelastic token.
    from jelastic_deploy import install
    expiry = install(*((live / name).read_text() for name in ('privkey.pem', 'cert.pem', 'chain.pem')))
    print(f'Installed; platform reports expiry {expiry}')
    expected = pem_status(live / 'cert.pem').fingerprint
    stale = []
    for host in CHECK_HOSTS:
        for attempt in range(VERIFY_ATTEMPTS):
            try:
                status = live_cert_status(host)
                if status.fingerprint == expected:
                    print(f'{host}: serving the new certificate ({status.days_remaining:.1f} days remaining)')
                    break
            except Exception as exc:
                print(f'{host}: not yet reachable ({type(exc).__name__}: {exc})')
            time.sleep(VERIFY_DELAY)
        else:
            stale.append(host)
    if stale:
        raise RuntimeError(f'after install these hosts are not serving the new certificate: '
                           f'{", ".join(stale)}')


def run(args):
    status = None
    if not args.staging:
        try:
            status = live_cert_status(CHECK_HOST)
        except Exception as exc:
            # An expired or broken certificate is exactly when renewal is needed.
            print(f'Could not read the live certificate ({type(exc).__name__}: {exc}); '
                  'assuming it needs renewal')
    if status and not args.staging and not args.force:
        threshold = renew_threshold_days(status.lifetime_days)
        print(f'{CHECK_HOST}: {status.days_remaining:.1f} days remaining '
              f'(renews below {threshold:.1f}; lifetime {status.lifetime_days:.0f} days)')
        if status.days_remaining > threshold:
            return
    live = None if args.staging else reusable_certificate(status.fingerprint if status else None)
    if live:
        print(f'Reusing the certificate already issued in {live}')
    else:
        live = issue(args.staging)
        print(f'Issued. Files in {live}')
        subprocess.run(['openssl', 'x509', '-in', str(live / 'cert.pem'), '-noout',
                        '-issuer', '-enddate', '-ext', 'subjectAltName'], check=True)
    if args.staging or args.no_install:
        return
    install_and_verify(live)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--staging', action='store_true',
                        help="use Let's Encrypt staging, skip the expiry check, never install")
    parser.add_argument('--force', action='store_true',
                        help='renew even if the live certificate has plenty of time left')
    parser.add_argument('--no-install', action='store_true', help='issue only, do not install')
    args = parser.parse_args()
    try:
        run(args)
    except BaseException as exc:
        if isinstance(exc, SystemExit) and not exc.code:
            raise
        if isinstance(exc, KeyboardInterrupt) or args.staging:
            raise
        send_alert('TLS certificate renewal FAILED',
                   f'{type(exc).__name__}: {exc}\n\n{traceback.format_exc()[-1500:]}\n'
                   'The current certificate is still being served until it expires. See the '
                   'cron log and /tmp/cbc-certbot/logs/ on the app node, and '
                   'docs/TLS_CERT_RENEWAL.md. The manual procedure there is the fallback.')
        raise


if __name__ == '__main__':
    main()
