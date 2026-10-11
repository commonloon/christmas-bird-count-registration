# TLS Certificate Renewal (FullHost, `*.cbc.birdcount.ca` + `*.birdcount.ca` + `birdcount.ca`)
{# Updated by Claude AI on 2026-10-11 #}

Renewal is automated by a cron job on the FullHost app node. This is new and still being proven: the first
unattended run has not happened yet, so treat the alerts and the manual fallback below as part of the system.

## Background

CBC (Christmas Bird Count) circles are reachable at `<circle>.cbc.birdcount.ca` (e.g. `vancouver.cbc.birdcount.ca`). Non-CBC counts (KBA surveys, spring counts, etc.) live one subdomain level up, directly at `<circle>.birdcount.ca` (e.g. `comox-spring.birdcount.ca`) - see `app.py`'s `CIRCLE_SUBDOMAIN_PATTERNS`. The bare apex `birdcount.ca` serves a landing page (`APEX_LANDING_HOST` in `app.py`). All of this is resolved via wildcard/apex DNS records pointing at a **public IP address attached directly to the app node** (`11294` on environment `env-5397859`). This bypasses FullHost's shared load balancer, which doesn't support wildcard custom-domain registration.

Apache on that node has a single catch-all `<VirtualHost *:443>` with one certificate, so *every* hostname hitting this IP is served from that one cert. If a host shows the wrong cert, the fault is a missing SAN or a stale cert - never a per-vhost setting.

The certificate has exactly three names (no more, no fewer):

- `*.cbc.birdcount.ca` - CBC circle subdomains.
- `*.birdcount.ca` - non-CBC circle subdomains; also covers `cbc.birdcount.ca` itself, which is why that host is not listed separately (requesting it as well is rejected as redundant).
- `birdcount.ca` - the bare apex. A wildcard never covers its own parent, so this needs its own name.

Let's Encrypt only issues wildcards through the **DNS-01** challenge. Public CAs cap certificate life at 200 days (since 2026-03-15), 100 days from 2027-03-15 and 47 days from 2029, so a long-lived certificate is not an option; automation is the durable fix. Let's Encrypt itself is moving its default from 90 days to 64 days on 2027-02-10 and to 45 days in 2028, and also shortens how long a successful validation can be reused (30 days now, 10 days, then hours); this job does a fresh validation on every run, so that doesn't affect it.

**No threshold in the code is a fixed number of days.** The job reads the live certificate's own lifetime (`notBefore` to `notAfter`) and renews when **a third** of it remains (about 30 days at 90, 21 at 64, 15 at 45), which is Let's Encrypt's recommendation. The watchdog alerts below **a sixth** (about 15, 11 and 8 days). The constants are `RENEW_FRACTION` and `ALERT_FRACTION` in `services/tls_renewal/tls_common.py`. The job does not use ACME Renewal Information (ARI); it relies on this fixed fraction instead.

HSTS with `includeSubDomains` is on, so an **expired certificate makes every host unreachable** with no click-through.

## How the automation works

```
cron (daily, quiet hours)
  └─ services/tls_renewal/renew_certificate.py
       1. more than 1/3 of the live cert's life left? -> exit quietly
       2. certbot --manual, RSA key, DNS-01        -> hooks publish TXT records via the deSEC API
            (a good, different certificate from an earlier run that failed to install is reused instead)
       3. jelastic_deploy.py                       -> upload the 3 PEMs, BindSSL, confirm fingerprint
       4. wait until all three hostnames serve it   -> else alert
  any failure -> alert email, non-zero exit

cron (daily, separate entry)
  └─ services/tls_renewal/check_expiry.py          -> alert if any host has < 1/6 of its life left or fails verification
```

**DNS delegation.** Squarespace serves `birdcount.ca` and has no API, so the challenge names are delegated by CNAME
into a tiny zone hosted at deSEC, which does have one. Records at Squarespace (set once):

| Type | Host | Value |
|---|---|---|
| NS | `acme` | `ns1.desec.io` |
| NS | `acme` | `ns2.desec.org` |
| CNAME | `_acme-challenge` | `apex.acme.birdcount.ca` |
| CNAME | `_acme-challenge.cbc` | `cbc.acme.birdcount.ca` |

deSEC holds the zone `acme.birdcount.ca`. Its API token is limited by policy to TXT records in that zone. Do **not** enable
DNSSEC on `birdcount.ca` (skip deSEC's DS/DNSSEC step). The slug `acme` is reserved in the circle form because
`acme.birdcount.ca` no longer reaches the app.

**Install.** FullHost keeps the certificate in its legacy "Custom SSL" model and root owns the file, so the node cannot swap the
file itself. `jelastic_deploy.py` uses the platform API instead: upload each PEM to the uploader service
(`/1.0/storage/uploader/rest/upload`), then `BindSSL` with the three returned download links. Roles in the form:
`privkey.pem` = Server Key, `chain.pem` = Intermediate Certificate (CA), `cert.pem` = Domain Certificate - never `fullchain.pem`.
The installer refuses a certificate from the staging CA or one missing any of the three names.

**Outage.** The swap makes HTTPS unreachable for roughly 30 seconds (measured once, 2026-10-11). That is why the job runs in quiet hours.

**Statelessness.** certbot's state lives in `/tmp/cbc-certbot` (override with `TLS_WORK_DIR`) and is rebuilt on demand, including its
virtualenv, so a wiped `/tmp` costs only a few minutes at the next renewal. Staging uses a separate directory (`config-staging`).

## One-time setup on the app node

**Environment variables** (FullHost Variables panel - never in the repo):

| Variable | Purpose |
|---|---|
| `DESEC_TOKEN` | deSEC token (TXT records in `acme.birdcount.ca` only) |
| `JELASTIC_CERT_TOKEN` | FullHost API token allowed `BindSSL`, `GetSSL` (and `RemoveSSL`) |
| `ACME_EMAIL` | Let's Encrypt account / expiry-notice address (required for production issuance) |
| `SMTP2GO_USERNAME` / `SMTP2GO_PASSWORD` | already set for the app; used to send alerts |

**Alert emails** go to every super-admin (`config/admins.py`, the same list the scheduler's alerts use) from the app's default from address
(`FROM_EMAIL` if set, otherwise `config/organization.py`'s). Nothing alert-specific needs configuring. Only if the admin list cannot be loaded does it fall back to `ACME_EMAIL`.

**Cron.** Install in the `apache` user's crontab, one line each (see `docs/SCHEDULER.md` for why `bash -lc` and absolute paths are
needed). The node's clock is UTC, so the times below are UTC: the renewal runs at 11:30 UTC (03:30 PST / 04:30 PDT, when traffic is lowest) and the watchdog at 17:00 UTC (09:00 PST / 10:00 PDT, so an alert lands during the working day):

```
30 11 * * * /bin/bash -lc 'cd /var/www/webroot/ROOT/services/tls_renewal && /opt/jelastic-python314/bin/python3 renew_certificate.py >> /var/www/webroot/logs/tls_renewal.log 2>&1'
0 17 * * * /bin/bash -lc 'cd /var/www/webroot/ROOT/services/tls_renewal && /opt/jelastic-python314/bin/python3 check_expiry.py >> /var/www/webroot/logs/tls_check.log 2>&1'
```

Each run appends a line or two to its log, so no rotation is needed in practice. The code runs from the deployed repository (after a
`git pull`), not from a copy in `/tmp`.

**Prove the alert path works** before relying on it:

```
ssh cbc 'bash -lc "cd /var/www/webroot/ROOT/services/tls_renewal && /opt/jelastic-python314/bin/python3 check_expiry.py --test-alert"'
```

## Day-to-day

- **Is it healthy?** `check_expiry.py` prints days remaining per host; run it any time. The renewal log shows `birdcount.ca: NN days remaining (renews below NN; lifetime NN days)` daily.
- **Renew now** (e.g. after changing the domain list): `renew_certificate.py --force`. This swaps the certificate - about 30 s outage. `--no-install` issues
  only; `--staging` tests issuance against Let's Encrypt's staging CA and never installs.
- **Logs on the node:** `/tmp/cbc-certbot/logs/letsencrypt.log` (certbot) and `/tmp/cbc-certbot/logs/hook.log` (which TXT values the hook published/removed, with timestamps).

## When it fails

You get an email "TLS certificate renewal FAILED" (or "TLS certificate needs attention" from the watchdog). The old certificate stays in place until it
expires, so there are weeks to react. Look at the renewal log and certbot's log, then:

| Symptom | Likely cause / action |
|---|---|
| `deSEC ... HTTP 502` | deSEC front-end hiccup; the hook retries for about 2.5 minutes. Rerun later. |
| `Incorrect TXT record ... During secondary validation` | Let's Encrypt's other vantage points saw an older record set (DNS propagation or caching). The hook waits an extra 60 s after confirming propagation. **Wait at least an hour before retrying** - resolvers cache for the 3600 s TTL and failed validations are rate-limited (5 per hour). Compare `hook.log` against the failure. |
| `NXDOMAIN looking up TXT` | Challenge TXT not published, or the CNAME/NS records at Squarespace are missing or changed. |
| `refusing to install a certificate from the staging CA` | A staging run's files were passed to `install`. Reissue for production. |
| `BindSSL failed` / upload errors | FullHost API change or token problem. Fall back to the dashboard upload below using the files in `/tmp/cbc-certbot/config/live/birdcount/`. |
| Let's Encrypt rate limit | Duplicate certificates: 5 per week. The job reuses an already-issued certificate rather than reissuing, but repeated manual `--force` runs can hit it. |

## Manual fallback

Use this if automation is broken and time is short. **First remove the two `_acme-challenge` CNAME records at Squarespace** (a CNAME cannot
coexist with the manual TXT records below); re-add them (and confirm the automated run works) afterwards.

Prerequisites: WSL (**do not run certbot natively on Windows** - it demands Administrator rights even in `--manual` mode), Squarespace DNS access, and the FullHost dashboard
(`env-5397859` → node `11294` → **Custom SSL**).

1. In a WSL shell (not `wsl <command>` from Windows - `~` expansion breaks across that boundary):
   ```bash
   ~/certbot-venv/bin/certbot certonly \
     --manual --preferred-challenges dns \
     --key-type rsa \
     -d "*.cbc.birdcount.ca" -d "*.birdcount.ca" -d "birdcount.ca" \
     --config-dir ~/letsencrypt-birdcount/config \
     --work-dir ~/letsencrypt-birdcount/work \
     --logs-dir ~/letsencrypt-birdcount/logs \
     --force-renewal
   ```
   (If `~/certbot-venv` is missing: `python3 -m venv ~/certbot-venv && ~/certbot-venv/bin/pip install certbot`.)
   `--key-type rsa` is required: FullHost's form rejects an ECDSA key with a misleading "server key does not match domain certificate" error.
   `--force-renewal` is required once a non-expired cert for this exact name exists.
2. Add the TXT records certbot asks for in Squarespace, using the **relative** host (`_acme-challenge` or `_acme-challenge.cbc`, not the full dotted name, which doubles the domain suffix).
   The apex name needs **two** TXT values (one for `*.birdcount.ca`, one for `birdcount.ca`). Confirm with
   `nslookup -type=TXT _acme-challenge.birdcount.ca` before letting certbot continue. Each name's DNS cache lasts for its TTL, so after a failed attempt wait before retrying.
3. **Check certbot's own final output for the actual `live/...` path.** The lineage folder is normally `cbc.birdcount.ca`, but certbot may silently create `cbc.birdcount.ca-0001` etc.;
   copying from the old folder quietly hands FullHost the previous certificate. Then copy the files out of WSL's symlinked `live/` directory:
   ```bash
   mkdir -p /mnt/c/Users/harve/certs
   cp -L ~/letsencrypt-birdcount/config/live/<lineage>/{privkey,cert,chain}.pem /mnt/c/Users/harve/certs/
   openssl x509 -in /mnt/c/Users/harve/certs/cert.pem -noout -ext subjectAltName   # expect all three names
   ```
4. Upload in the dashboard's Custom SSL form: Server Key = `privkey.pem`, Intermediate Certificate (CA) = `chain.pem`, Domain Certificate = `cert.pem`. Click Save (about 20-30 s outage).
5. Verify one host per name:
   ```bash
   curl -Iv https://vancouver.cbc.birdcount.ca/ 2>&1 | grep -i "expire\|subject\|issuer"
   curl -Iv https://comox-spring.birdcount.ca/ 2>&1 | grep -i "expire\|subject\|issuer"
   curl -Iv https://birdcount.ca/ 2>&1 | grep -i "expire\|subject\|issuer"
   ```
   Check each name, not just one - a working `*.cbc.birdcount.ca` host says nothing about the other two.

Delete the copied key files from `C:\Users\harve\certs` when done; they contain the live private key.
