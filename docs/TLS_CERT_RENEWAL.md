# TLS Certificate Renewal (FullHost, `*.cbc.birdcount.ca` + `*.birdcount.ca` + `birdcount.ca`)
{# Updated by Claude AI on 2026-09-02 #}

## Background

CBC (Christmas Bird Count) circles are reachable at `<circle>.cbc.birdcount.ca` (e.g. `vancouver.cbc.birdcount.ca`). Non-CBC counts (KBA surveys, spring counts, etc.) live one subdomain level up, directly at `<circle>.birdcount.ca` (e.g. `comox-spring.birdcount.ca`) — see `app.py`'s `CIRCLE_SUBDOMAIN_PATTERNS`. The bare apex `birdcount.ca` itself serves a third page - a landing page listing non-CBC counts and linking across to `cbc.birdcount.ca`'s CBC listing (`APEX_LANDING_HOST` in `app.py`). All of this is resolved via wildcard/apex DNS records pointing at a **public IP address attached directly to the app node** (`11294` on environment `env-5397859`). This bypasses FullHost's shared load balancer, which doesn't support wildcard custom-domain registration — see `REMINDER.md`/`hosting-migration` memory for the full reasoning.

Apache on that node has a single catch-all `<VirtualHost *:443>` in `ssl.conf` with one `SSLCertificateFile` (`/var/lib/jelastic/SSL/jelastic.crt`) — there's no per-hostname SNI vhost, so *every* hostname hitting this IP gets served from that one cert file. If a host you expect to work shows the wrong cert (e.g. Chrome says "certificate is from `*.cbc.birdcount.ca`" when visiting `birdcount.ca`), the fault is either a missing SAN or a stale file at that exact path (see the lineage-directory trap in step 3) - it is never a per-vhost config issue on this setup.

Let's Encrypt only issues wildcard certificates via the **DNS-01 challenge** (HTTP-01 doesn't support wildcards at all — this is an ACID protocol restriction, not a FullHost or certbot limitation). Our DNS registrar (Squarespace, though the zone is actually served by Google Cloud DNS nameservers under the hood) has no API, so this **cannot be automated** — it's a manual process, needed roughly every 90 days.

## Prerequisites

- WSL installed locally. **Do not run certbot natively on Windows** — it unconditionally refuses to run without Administrator rights, even in `--manual` mode where no elevated privilege is actually needed.
- Access to Squarespace's DNS panel for `birdcount.ca`.
- Access to the FullHost dashboard for `env-5397859`, node `11294` → **Custom SSL** form.

## Procedure

### 1. Request the certificate (in a WSL shell, not `wsl <command>` from Windows — `~` expansion breaks across that boundary)

```bash
wsl
# now inside WSL:
~/certbot-venv/bin/certbot certonly \
  --manual --preferred-challenges dns \
  --key-type rsa \
  -d "*.cbc.birdcount.ca" \
  -d "*.birdcount.ca" \
  -d "birdcount.ca" \
  --config-dir ~/letsencrypt-birdcount/config \
  --work-dir ~/letsencrypt-birdcount/work \
  --logs-dir ~/letsencrypt-birdcount/logs \
  --force-renewal
```

Exactly these three `-d` flags - no more, no fewer:

- `*.cbc.birdcount.ca` - CBC circle subdomains (`vancouver.cbc.birdcount.ca`, etc.)
- `*.birdcount.ca` - non-CBC circle subdomains (`comox-spring.birdcount.ca`, etc.) - this also happens to cover `cbc.birdcount.ca` itself (one label), which is why that host is **not** listed separately here even though it serves real content (the CBC landing page) - including it anyway gets rejected outright:
  ```
  Error creating new order :: Domain name "cbc.birdcount.ca" is redundant with a
  wildcard domain in the same request. Remove one or the other from the certificate request.
  ```
- `birdcount.ca` - the bare apex (zero labels), which serves the non-CBC landing page. **Not** covered by `*.birdcount.ca` or anything else - a wildcard never covers its own bare parent, the same reason `cbc.birdcount.ca` needed its own SAN back when the cert only had `*.cbc.birdcount.ca`. Don't drop this one just because `*.birdcount.ca` is also in the list - they cover different things.

(If `~/certbot-venv` doesn't exist yet: `python3 -m venv ~/certbot-venv && ~/certbot-venv/bin/pip install certbot` first.)

**`--key-type rsa` is required.** FullHost's "Custom SSL" form validates the key/cert pairing with what appears to be an RSA-specific check — an ECDSA key (which newer certbot defaults may produce) will cryptographically match its certificate just fine, but FullHost's form will reject it with a misleading "server key does not match domain certificate" error. This cost significant debugging time to track down — don't skip this flag.

**`--force-renewal` is required** once a non-expired cert for this exact name already exists, otherwise certbot refuses to reissue.

### 2. Add the DNS TXT record(s)

Follow whatever certbot itself prints rather than assuming a fixed number of prompts - in practice, issuing for all three domains above produced only **one** DNS-01 prompt, not the three you might expect from three `-d` flags (certbot appears to deduplicate by challenge name when domains share one, e.g. `*.birdcount.ca` and `birdcount.ca` both validate at `_acme-challenge.birdcount.ca`; don't assume this behavior is stable across certbot versions, just watch what it actually asks for).

The two possible challenge hosts (relative, in Squarespace's DNS panel):

| Challenge for | Host | Verify with |
|---|---|---|
| `*.cbc.birdcount.ca` | `_acme-challenge.cbc` | `nslookup -type=TXT _acme-challenge.cbc.birdcount.ca` |
| `*.birdcount.ca` and/or `birdcount.ca` | `_acme-challenge` | `nslookup -type=TXT _acme-challenge.birdcount.ca` |

**Use the relative host certbot's prompt implies, not the full dotted name** - pasting the full `_acme-challenge.birdcount.ca` into Squarespace's "Host" field doubles up the domain suffix and creates the record at the wrong name (this bit us once already). Confirm propagation via `nslookup`/`dig` from a separate terminal before telling certbot to continue - continuing too early wastes an attempt against Let's Encrypt's rate limits.

### 3. Retrieve the three files certbot needs to hand to FullHost

**⚠️ Before copying anything, check certbot's own final output for the actual `live/...` path it wrote to.** The lineage folder name is normally `cbc.birdcount.ca` (derived from the first `-d`, star stripped), but if certbot decides the domain list is different enough from an existing lineage of that name, it silently creates a *new* one instead - `cbc.birdcount.ca-0001`, `-0002`, etc. - without erroring or asking. Copying from the old path in that case doesn't fail either; it just quietly hands FullHost the **previous, stale cert** (this happened during the 2026-09-02 renewal - the upload "succeeded" and only revealed itself as wrong via a browser cert-mismatch error afterward). Certbot prints a line like `Certificate is saved at: /home/.../live/cbc.birdcount.ca-0001/fullchain.pem` near the end of its output - that path, not this doc, is the source of truth for step 3 and 4's file locations every single time.

Still in WSL, copy the certbot output to a plain Windows-visible path (avoids any WSL-symlink resolution issues — certbot's `live/` files are symlinks into `archive/`, and don't rely on browsing `\\wsl$\...` paths directly in a file picker). Adjust the `live/cbc.birdcount.ca` segment below to match whatever certbot actually printed:

```bash
mkdir -p /mnt/c/Users/harve/certs
cp -L ~/letsencrypt-birdcount/config/live/cbc.birdcount.ca/privkey.pem /mnt/c/Users/harve/certs/
cp -L ~/letsencrypt-birdcount/config/live/cbc.birdcount.ca/cert.pem /mnt/c/Users/harve/certs/
cp -L ~/letsencrypt-birdcount/config/live/cbc.birdcount.ca/chain.pem /mnt/c/Users/harve/certs/
```

Sanity-check what you're about to upload actually has all three SANs before proceeding to step 4:

```bash
openssl x509 -in /mnt/c/Users/harve/certs/cert.pem -noout -ext subjectAltName
# expect: DNS:*.cbc.birdcount.ca, DNS:*.birdcount.ca, DNS:birdcount.ca
```

### 4. Upload to FullHost

FullHost dashboard → environment `env-5397859` → node `11294` → **Custom SSL** form. Upload from `C:\Users\harve\certs\`:

| Form field | File |
|---|---|
| Server Key | `privkey.pem` |
| Intermediate Certificate (CA) | `chain.pem` |
| Domain Certificate | `cert.pem` |

**Do not use `fullchain.pem`** in the Domain Certificate field — it concatenates the leaf and intermediate certs into one file, which this form doesn't expect (it wants them split across the Intermediate/Domain fields separately) and will also produce a "key does not match" error.

Click Save.

### 5. Verify

```bash
curl -Iv https://vancouver.cbc.birdcount.ca/ 2>&1 | grep -i "expire\|subject\|issuer"
curl -Iv https://comox-spring.birdcount.ca/ 2>&1 | grep -i "expire\|subject\|issuer"
curl -Iv https://birdcount.ca/ 2>&1 | grep -i "expire\|subject\|issuer"
```

Check one host per SAN, not just one — a working `*.cbc.birdcount.ca` host doesn't confirm `*.birdcount.ca` or bare `birdcount.ca` are also good. `curl`'s own TLS check is enough (it'll refuse to connect on a mismatch, same as a browser), but if you have SSH access to the app node, checking the cert file directly is more definitive than any single hostname test, since it shows every SAN at once regardless of DNS:

```bash
ssh -p 3022 11294-687@gate.vap.fullhost.cloud \
  "openssl x509 -in /var/lib/jelastic/SSL/jelastic.crt -noout -subject -ext subjectAltName -enddate"
```

Confirm the new expiry date is ~90 days out and all three SANs are present.

## Renewal cadence

There is no automated reminder for this yet — set a calendar reminder for roughly every 80 days (Let's Encrypt allows renewal up to 30 days before expiry, so this leaves margin). FullHost's own default certificate for the platform's shared hostname was found expired and unnoticed during this migration — don't let this one suffer the same fate.
