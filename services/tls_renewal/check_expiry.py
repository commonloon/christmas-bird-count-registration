# Updated by Claude AI on 2026-10-11
"""Daily watchdog: alert if the certificate served on any hostname is close to expiry
(under a sixth of its lifetime left),
expired, or fails verification. Deliberately independent of the renewal job, so it
still fires if renewal (or cron for renewal) has silently stopped.

    check_expiry.py               # check; email an alert if there is a problem
    check_expiry.py --test-alert  # send a test email to prove the alert path works

Exit status is 1 when there is a problem (or the test alert could not be sent).
"""
import sys

from tls_common import CHECK_HOSTS, alert_threshold_days, live_cert_status, send_alert


def main(argv):
    if '--test-alert' in argv:
        ok = send_alert('TLS renewal: test alert',
                        'This is a test of the certificate alert email path. No action needed.')
        print('test alert sent' if ok else 'test alert NOT sent')
        return 0 if ok else 1

    problems = []
    for host in CHECK_HOSTS:
        try:
            status = live_cert_status(host)
        except Exception as exc:
            problems.append(f'{host}: could not verify certificate ({type(exc).__name__}: {exc})')
            continue
        limit = alert_threshold_days(status.lifetime_days)
        print(f'{host}: {status.days_remaining:.1f} days remaining '
              f'(alerts below {limit:.1f}; lifetime {status.lifetime_days:.0f} days)')
        if status.days_remaining < limit:
            problems.append(f'{host}: only {status.days_remaining:.1f} days remaining')
    if not problems:
        return 0
    send_alert('TLS certificate needs attention',
               'The daily certificate check found:\n\n' + '\n'.join(f'- {p}' for p in problems) +
               '\n\nIf automatic renewal is not working, see docs/TLS_CERT_RENEWAL.md '
               '(the manual procedure is the fallback). An expired certificate makes every '
               'host unreachable because HSTS is enabled.')
    return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
