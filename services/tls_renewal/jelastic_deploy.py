# Updated by Claude AI on 2026-10-08
"""Install a certificate on the FullHost/Jelastic environment via the legacy
BindSSL call (what the dashboard's Custom SSL form uses for this environment).

BindSSL takes three *download links*, so each PEM is first uploaded to the
platform's upload service. Token: $JELASTIC_CERT_TOKEN (never a file/argv).

    jelastic_deploy.py probe             # upload a tiny throwaway file, nothing else
    jelastic_deploy.py rebind-current    # re-install the CURRENT cert (content unchanged)
    jelastic_deploy.py install DIR       # install DIR/{privkey,cert,chain}.pem
"""
import hashlib
import json
import os
import secrets
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

HOST = 'https://app.vap.fullhost.cloud'
ENV = 'env-5397859'
# The dashboard polls {HOST}/1.0/storage/uploader/rest/progress?fid=..., so the uploader
# service lives there; the legacy /xssu/rest/upload path always answered "invalid param".
UPLOAD_URLS = (f'{HOST}/1.0/storage/uploader/rest/upload', f'{HOST}/xssu/rest/upload')


def _token():
    return os.environ['JELASTIC_CERT_TOKEN']


def _scrub(text):
    return str(text).replace(_token(), '<token>')


def _api(path, **params):
    params.update(envName=ENV, session=_token())
    req = urllib.request.Request(f'{HOST}/1.0/{path}', method='POST',
                                 data=urllib.parse.urlencode(params).encode())
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())


def _multipart(fields, filename, data):
    boundary = '----cbc' + secrets.token_hex(8)
    body = b''
    for name, value in fields.items():
        body += (f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"'
                 f'\r\n\r\n{value}\r\n').encode()
    body += (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; '
             f'filename="{filename}"\r\nContent-Type: application/octet-stream\r\n\r\n'
             ).encode() + data + f'\r\n--{boundary}--\r\n'.encode()
    return body, f'multipart/form-data; boundary={boundary}'


# Extra field sets to try, in order, until the server accepts one. 'fid' is a client-chosen
# id the dashboard later polls via .../uploader/rest/progress. JELASTIC_APPID is optional.
def _upload_variants(filename):
    fid = secrets.token_hex(16)
    base = {'fid': fid}
    appid = os.environ.get('JELASTIC_APPID')
    if appid:
        yield {**base, 'appid': appid}
    yield base
    yield {**base, 'fileName': filename}
    yield {}


def upload(filename, text):
    """Upload text to the platform; returns its download link."""
    last = None
    for url in UPLOAD_URLS:
        for extra in _upload_variants(filename):
            fields = {'session': _token(), **extra}
            body, ctype = _multipart(fields, filename, text.encode())
            req = urllib.request.Request(url, data=body, method='POST',
                                         headers={'Content-Type': ctype})
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    answer = json.loads(resp.read())
            except urllib.error.HTTPError as exc:
                last = f'{url.split("/", 3)[3]} HTTP {exc.code}'
                continue
            if answer.get('result') == 0:
                link = next((v for v in answer.values()
                             if isinstance(v, str) and v.startswith('http')), None)
                if link:
                    return link
            last = (f"{url.split('/', 3)[3]} result={answer.get('result')} "
                    f"{answer.get('error', '')} keys={sorted(answer)} fields={sorted(extra)}")
    raise RuntimeError(f'upload failed with every variant; last: {_scrub(last)}')


def _fetch(value):
    if value.startswith('http'):
        with urllib.request.urlopen(value, timeout=30) as resp:
            return resp.read().decode()
    return value


def _fingerprint(pem):
    return subprocess.run(['openssl', 'x509', '-noout', '-fingerprint', '-sha256'], input=pem,
                          capture_output=True, text=True, check=True).stdout.strip()


REQUIRED_NAMES = ('*.birdcount.ca', '*.cbc.birdcount.ca', 'birdcount.ca')


def _check_installable(cert):
    """Refuse a staging-CA cert or one that doesn't cover every hostname we serve."""
    info = subprocess.run(['openssl', 'x509', '-noout', '-issuer', '-ext', 'subjectAltName'],
                          input=cert, capture_output=True, text=True, check=True).stdout
    if 'STAGING' in info.upper():
        raise RuntimeError('refusing to install a certificate from the staging CA')
    missing = [n for n in REQUIRED_NAMES if f'DNS:{n}' not in info]
    if missing:
        raise RuntimeError(f'certificate does not cover: {", ".join(missing)}')


def install(key, cert, inter):
    """Upload the three PEMs, bind them, and confirm the platform now serves `cert`."""
    _check_installable(cert)
    links = {'cert_key': upload('privkey.pem', key),
             'cert': upload('cert.pem', cert),
             'intermediate': upload('chain.pem', inter)}
    result = _api('environment/binder/rest/bindssl', **links)
    if result.get('result') != 0:
        raise RuntimeError(f"BindSSL failed: {result.get('result')} {result.get('error', '')}")
    now = _api('environment/binder/rest/getssl')['sslCustom']
    if _fingerprint(_fetch(now['cert'])) != _fingerprint(cert):
        raise RuntimeError('BindSSL reported success but the platform cert does not match')
    return now['expiredate']


def main(argv):
    mode = argv[1] if len(argv) > 1 else ''
    if mode == 'probe':
        link = upload('probe.txt', 'cbc tls probe - safe to discard\n')
        print('upload OK; link received:', link.startswith('http'))
    elif mode == 'rebind-current':
        cur = _api('environment/binder/rest/getssl')['sslCustom']
        key, cert, inter = (_fetch(cur[k]) for k in ('cert_key', 'cert', 'intermediate'))
        print('re-installed current cert via upload+BindSSL; expiry', install(key, cert, inter))
    elif mode == 'install' and len(argv) > 2:
        d = Path(argv[2])
        print('installed; expiry', install(*(( d / n).read_text()
                                               for n in ('privkey.pem', 'cert.pem', 'chain.pem'))))
    else:
        sys.exit(__doc__)


if __name__ == '__main__':
    try:
        main(sys.argv)
    except Exception as exc:
        sys.exit(f'ERROR {type(exc).__name__}: {_scrub(exc)[:400]}')
