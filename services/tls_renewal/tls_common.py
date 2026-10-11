# Updated by Claude AI on 2026-10-11
"""Pieces shared by renew_certificate.py and check_expiry.py.

Standard library only, on purpose: check_expiry.py must keep working (and be
able to email an alert) even if certbot, its venv or the Jelastic code is broken.
"""
import os
import smtplib
import socket
import ssl
import sys
import time
from email.message import EmailMessage
from pathlib import Path

# One host per SAN: the apex (birdcount.ca), a one-label host (covered by *.birdcount.ca)
# and a two-label host (covered by *.cbc.birdcount.ca). The node serves one cert for every
# name, and the wildcard A record resolves them all; only the TLS handshake is made.
CHECK_HOSTS = ('birdcount.ca', 'cbc.birdcount.ca', 'tls-check.cbc.birdcount.ca')

# Same provider settings as config/email_settings.py's 'smtp2go' entry (duplicated here
# so this module has no app imports).
SMTP_SERVER = 'mail.smtp2go.com'
SMTP_PORT = 587


def live_days_remaining(host):
    """Days until the certificate served for `host` expires. Raises if the handshake or
    hostname/chain verification fails - an expired or mismatched cert counts as failure."""
    ctx = ssl.create_default_context()
    with socket.create_connection((host, 443), timeout=15) as sock:
        with ctx.wrap_socket(sock, server_hostname=host) as tls:
            not_after = ssl.cert_time_to_seconds(tls.getpeercert()['notAfter'])
    return (not_after - time.time()) / 86400


def _repo_root_on_path():
    root = str(Path(__file__).resolve().parents[2])
    if root not in sys.path:
        sys.path.insert(0, root)


def _alert_recipients():
    """All super-admins (config/admins.py, the same list scheduler_service.py alerts).
    Falls back to ACME_EMAIL only if that list can't be loaded."""
    try:
        _repo_root_on_path()
        from config.admins import get_admin_emails
        recipients = sorted(set(get_admin_emails()))
    except Exception:
        recipients = []
    if not recipients and os.environ.get('ACME_EMAIL'):
        recipients = [os.environ['ACME_EMAIL']]
    return recipients


def _default_sender():
    """The app's default from address: FROM_EMAIL if set, else config.organization's."""
    if os.environ.get('FROM_EMAIL'):
        return os.environ['FROM_EMAIL']
    try:
        _repo_root_on_path()
        from config.organization import FROM_EMAIL
        return FROM_EMAIL
    except Exception:
        return None


def send_alert(subject, body):
    """Email an alert to all super-admins (also printed to stderr, which cron appends to
    the log). Needs SMTP2GO_USERNAME/SMTP2GO_PASSWORD. Returns True if the message was
    handed to the SMTP server."""
    print(f'ALERT: {subject}' + chr(10) + body, file=sys.stderr)
    recipients = _alert_recipients()
    sender = _default_sender()
    username = os.environ.get('SMTP2GO_USERNAME', '').strip()
    password = os.environ.get('SMTP2GO_PASSWORD', '').strip()
    if not (recipients and sender and username and password):
        print('alert email NOT sent: need SMTP2GO_USERNAME, SMTP2GO_PASSWORD, a sender '
              '(FROM_EMAIL or config.organization) and at least one super-admin address',
              file=sys.stderr)
        return False
    msg = EmailMessage()
    msg['From'] = sender
    msg['To'] = ', '.join(recipients)
    msg['Subject'] = subject
    msg.set_content(body)
    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=30) as server:
            server.starttls()
            server.login(username, password)
            server.send_message(msg)
    except Exception as exc:
        print(f'alert email NOT sent: {type(exc).__name__}: {exc}', file=sys.stderr)
        return False
    return True
