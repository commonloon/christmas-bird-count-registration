# Updated by Claude AI on 2026-10-08
"""certbot --manual auth/cleanup hook: publish and remove DNS-01 challenge TXT
records through the deSEC API.

The real birdcount.ca zone stays at Squarespace. Two static CNAMEs there send
Let's Encrypt's lookups into the deSEC-hosted zone acme.birdcount.ca:

    _acme-challenge.birdcount.ca     CNAME  apex.acme.birdcount.ca
    _acme-challenge.cbc.birdcount.ca CNAME  cbc.acme.birdcount.ca

so this hook only ever writes TXT records inside acme.birdcount.ca. The deSEC
token (DESEC_TOKEN, from the environment - never a file) is policy-scoped to
TXT records in that one zone.

Usage (certbot supplies CERTBOT_DOMAIN / CERTBOT_VALIDATION):
    desec_hook.py auth | cleanup
    desec_hook.py selftest    # round-trip a throwaway record, no certbot needed
"""
import json
import os
import secrets
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request

API = 'https://desec.io/api/v1'
ZONE = 'acme.birdcount.ca'
# Base domain certbot validates (wildcard '*.' already stripped) -> subname in ZONE
CHALLENGE_SUBNAMES = {
    'birdcount.ca': 'apex',      # covers birdcount.ca and *.birdcount.ca
    'cbc.birdcount.ca': 'cbc',   # covers *.cbc.birdcount.ca
}
TTL = 3600
AUTHORITATIVE_NS = ('ns1.desec.io', 'ns2.desec.org')
PROPAGATION_TIMEOUT = 180
PROPAGATION_GRACE = 60


def _request(method, path, body=None):
    """Returns (status, parsed JSON or None). 404 is returned, not raised."""
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        f'{API}{path}', data=data, method=method,
        headers={'Authorization': f"Token {os.environ['DESEC_TOKEN']}",
                 'Content-Type': 'application/json'})
    # deSEC's front end occasionally answers 502/503; these calls are all safe to repeat.
    attempts = 6
    for attempt in range(attempts):
        last = attempt == attempts - 1
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read()
                return resp.status, (json.loads(raw) if raw else None)
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return 404, None
            if exc.code == 429 and not last:
                time.sleep(int(exc.headers.get('Retry-After', '2')) + 1)
                continue
            if exc.code >= 500 and not last:
                time.sleep(5 * 2 ** attempt)
                continue
            raise RuntimeError(
                f'deSEC {method} {path} failed: HTTP {exc.code} {exc.read()[:300]!r}')
        except (urllib.error.URLError, TimeoutError) as exc:
            if last:
                raise RuntimeError(f'deSEC {method} {path} failed: {exc}')
            time.sleep(5 * 2 ** attempt)


def _quote(value):
    return f'"{value}"'


def _get_records(subname):
    status, body = _request('GET', f'/domains/{ZONE}/rrsets/{subname}/TXT/')
    return [] if status == 404 else list(body['records'])


def _set_records(subname, records):
    path = f'/domains/{ZONE}/rrsets/{subname}/TXT/'
    if not records:
        _request('DELETE', path)
        return
    body = {'subname': subname, 'type': 'TXT', 'ttl': TTL, 'records': records}
    status, _ = _request('PUT', path, body)
    if status == 404:
        _request('POST', f'/domains/{ZONE}/rrsets/', body)


def _wait_for_propagation(subname, quoted_value):
    """Poll deSEC's own nameserver until the value is visible (or give up)."""
    name = f'{subname}.{ZONE}'
    if not shutil.which('dig'):
        time.sleep(30)
        return
    deadline = time.time() + PROPAGATION_TIMEOUT
    while time.time() < deadline:
        if all(quoted_value in subprocess.run(['dig', f'@{ns}', 'TXT', name, '+short'],
                                              capture_output=True, text=True,
                                              timeout=30).stdout.split('\n')
               for ns in AUTHORITATIVE_NS):
            return
        time.sleep(5)
    # Don't abort: raising makes certbot clean up the record, which guarantees a
    # failed validation. Let's Encrypt may still see it, and a failure there is
    # reported by certbot itself.
    print(f'WARNING: {name} TXT not visible on all deSEC nameservers after '
          f'{PROPAGATION_TIMEOUT}s; continuing', file=sys.stderr)


def _log(message):
    """Append to a hook log next to certbot's own (values are public TXT contents)."""
    path = os.path.join(os.environ.get('TLS_WORK_DIR', '/tmp/cbc-certbot'), 'logs', 'hook.log')
    try:
        with open(path, 'a') as handle:
            handle.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}\n")
    except OSError:
        pass


def publish(subname, value):
    records = _get_records(subname)
    _log(f'publish {subname}: existing={records} adding={_quote(value)}')
    if _quote(value) not in records:
        records.append(_quote(value))
    _set_records(subname, records)
    _wait_for_propagation(subname, _quote(value))
    # The nameservers are anycast: our check can see the record before the instance
    # Let's Encrypt's other vantage points reach does.
    time.sleep(PROPAGATION_GRACE)
    _log(f'publish {subname}: done')


def cleanup(subname, value):
    records = [r for r in _get_records(subname) if r != _quote(value)]
    _log(f'cleanup {subname}: removing={_quote(value)} remaining={records}')
    _set_records(subname, records)


def _subname_for_certbot_domain():
    domain = os.environ['CERTBOT_DOMAIN'].lower().lstrip('*.')
    if domain not in CHALLENGE_SUBNAMES:
        raise RuntimeError(f'no challenge CNAME target configured for {domain!r}')
    return CHALLENGE_SUBNAMES[domain]


def main(argv):
    mode = argv[1] if len(argv) > 1 else ''
    if mode == 'auth':
        publish(_subname_for_certbot_domain(), os.environ['CERTBOT_VALIDATION'])
    elif mode == 'cleanup':
        cleanup(_subname_for_certbot_domain(), os.environ['CERTBOT_VALIDATION'])
    elif mode == 'selftest':
        value = secrets.token_urlsafe(32)
        publish('selftest', value)
        print(f'OK: selftest.{ZONE} TXT published (see any WARNING above)')
        cleanup('selftest', value)
        print('OK: removed')
    else:
        sys.exit(__doc__)


if __name__ == '__main__':
    main(sys.argv)
