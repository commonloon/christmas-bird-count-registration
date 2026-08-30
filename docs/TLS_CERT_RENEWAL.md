# TLS Certificate Renewal (FullHost, wildcard `*.cbc.birdcount.ca`)
{# Updated by Claude AI on 2026-08-30 #}

## Background

The app is reachable at `<circle>.cbc.birdcount.ca` (e.g. `vancouver.cbc.birdcount.ca`), resolved via a wildcard DNS record (`*.cbc.birdcount.ca`) pointing at a **public IP address attached directly to the app node** (`11294` on environment `env-5397859`). This bypasses FullHost's shared load balancer, which doesn't support wildcard custom-domain registration — see `REMINDER.md`/`hosting-migration` memory for the full reasoning.

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
  -d "cbc.birdcount.ca" \
  --config-dir ~/letsencrypt-birdcount/config \
  --work-dir ~/letsencrypt-birdcount/work \
  --logs-dir ~/letsencrypt-birdcount/logs \
  --force-renewal
```

Both `-d` flags are needed — a wildcard SAN (`*.cbc.birdcount.ca`) does **not** cover the bare parent domain, and `cbc.birdcount.ca` itself serves the cross-circle landing page (and eventually the super-admin console), so it needs its own SAN on the same cert.

(If `~/certbot-venv` doesn't exist yet: `python3 -m venv ~/certbot-venv && ~/certbot-venv/bin/pip install certbot` first.)

**`--key-type rsa` is required.** FullHost's "Custom SSL" form validates the key/cert pairing with what appears to be an RSA-specific check — an ECDSA key (which newer certbot defaults may produce) will cryptographically match its certificate just fine, but FullHost's form will reject it with a misleading "server key does not match domain certificate" error. This cost significant debugging time to track down — don't skip this flag.

**`--force-renewal` is required** once a non-expired cert for this exact name already exists, otherwise certbot refuses to reissue.

### 2. Add the DNS TXT record

Certbot will pause and print a value for `_acme-challenge.cbc.birdcount.ca`. In Squarespace's DNS panel, add:

| Field | Value |
|---|---|
| Type | `TXT` |
| Host | `_acme-challenge.cbc` (relative — **not** the full `_acme-challenge.cbc.birdcount.ca`, which would double up the domain suffix) |
| Data | the value certbot printed (no extra quotes) |

Before telling certbot to continue, confirm propagation from a separate terminal:

```bash
nslookup -type=TXT _acme-challenge.cbc.birdcount.ca
```

Only proceed once this returns the expected value — continuing too early wastes an attempt against Let's Encrypt's rate limits.

### 3. Retrieve the three files certbot needs to hand to FullHost

Still in WSL, copy the certbot output to a plain Windows-visible path (avoids any WSL-symlink resolution issues — certbot's `live/` files are symlinks into `archive/`, and don't rely on browsing `\\wsl$\...` paths directly in a file picker):

```bash
mkdir -p /mnt/c/Users/harve/certs
cp -L ~/letsencrypt-birdcount/config/live/cbc.birdcount.ca/privkey.pem /mnt/c/Users/harve/certs/
cp -L ~/letsencrypt-birdcount/config/live/cbc.birdcount.ca/cert.pem /mnt/c/Users/harve/certs/
cp -L ~/letsencrypt-birdcount/config/live/cbc.birdcount.ca/chain.pem /mnt/c/Users/harve/certs/
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
```

or check the padlock/certificate details in a browser at any `*.cbc.birdcount.ca` address. Confirm the new expiry date is ~90 days out.

## Renewal cadence

There is no automated reminder for this yet — set a calendar reminder for roughly every 80 days (Let's Encrypt allows renewal up to 30 days before expiry, so this leaves margin). FullHost's own default certificate for the platform's shared hostname was found expired and unnoticed during this migration — don't let this one suffer the same fate.
