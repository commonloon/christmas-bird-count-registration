# Updated by Claude AI on 2026-10-11
"""Renew the wildcard certificate: certbot + the deSEC DNS-01 hook, then install it.

Stateless by design: each run checks the live certificate's expiry and does nothing
if more than RENEW_WITHIN_DAYS remain. Otherwise it issues a certificate (or reuses
one a previous run issued but failed to install), installs it on the node through
the platform API (jelastic_deploy.py), and verifies every hostname serves it. Any
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
import traceback
from pathlib import Path

from tls_common import CHECK_HOSTS, live_days_remaining, send_alert

HOOK = Path(__file__).with_name('desec_hook.py')
DOMAINS = ('*.cbc.birdcount.ca', '*.birdcount.ca', 'birdcount.ca')
CHECK_HOST = CHECK_HOSTS[0]
RENEW_WITHIN_DAYS = 30
# A previously issued, not-yet-installed certificate with at least this many days left is
# reused instead of asking Let's Encrypt again (duplicate-certificate limit: 5 per week).
REUSE_IF_DAYS_LEFT = 60
MIN_DAYS_AFTER_INSTALL = 60
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


def reusable_certificate():
    """Directory of a production certificate issued earlier with plenty of life left, or None."""
    live = _config_dir(False) / 'live' / CERT_NAME
    cert = live / 'cert.pem'
    if not cert.exists():
        return None
    still_valid = subprocess.run(
        ['openssl', 'x509', '-in', str(cert), '-noout', '-checkend',
         str(REUSE_IF_DAYS_LEFT * 86400)], capture_output=True).returncode == 0
    return live if still_valid else None


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
    short = []
    for host in CHECK_HOSTS:
        days = live_days_remaining(host)
        print(f'{host}: {days:.1f} days remaining after install')
        if days < MIN_DAYS_AFTER_INSTALL:
            short.append(host)
    if short:
        raise RuntimeError(f'after install these hosts still serve a short-lived certificate: '
                           f'{", ".join(short)}')


def run(args):
    if not args.staging and not args.force:
        days = live_days_remaining(CHECK_HOST)
        print(f'{CHECK_HOST}: {days:.1f} days remaining')
        if days > RENEW_WITHIN_DAYS:
            return
    live = None if args.staging else reusable_certificate()
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
