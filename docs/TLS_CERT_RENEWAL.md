# TLS Certificate Renewal (FullHost, wildcards `*.cbc.birdcount.ca` + `*.birdcount.ca`)
{# Updated by Claude AI on 2026-09-02 #}

## Background

CBC (Christmas Bird Count) circles are reachable at `<circle>.cbc.birdcount.ca` (e.g. `vancouver.cbc.birdcount.ca`). Non-CBC counts (KBA surveys, spring counts, etc.) live one subdomain level up, directly at `<circle>.birdcount.ca` (e.g. `comox-spring.birdcount.ca`) — see `app.py`'s `CIRCLE_SUBDOMAIN_PATTERNS`. Both are resolved via wildcard DNS records (`*.cbc.birdcount.ca` and `*.birdcount.ca`) pointing at a **public IP address attached directly to the app node** (`11294` on environment `env-5397859`). This bypasses FullHost's shared load balancer, which doesn't support wildcard custom-domain registration — see `REMINDER.md`/`hosting-migration` memory for the full reasoning.

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
  --config-dir ~/letsencrypt-birdcount/config \
  --work-dir ~/letsencrypt-birdcount/work \
  --logs-dir ~/letsencrypt-birdcount/logs \
  --force-renewal
```

Both wildcard `-d` flags are needed and that's **all** that's needed — do not also add `-d "cbc.birdcount.ca"` (the bare landing-page host). That was necessary back when the cert only covered `*.cbc.birdcount.ca` (a wildcard doesn't cover its own bare parent domain), but `*.birdcount.ca` is a *broader* wildcard that already matches `cbc` as one of its single-label subdomains, making an explicit `cbc.birdcount.ca` SAN redundant. Let's Encrypt rejects the request outright if you include it anyway:

```
Error creating new order :: Domain name "cbc.birdcount.ca" is redundant with a
wildcard domain in the same request. Remove one or the other from the certificate request.
```

Note the asymmetry: `*.birdcount.ca` covers `cbc.birdcount.ca` (one label) but does **not** cover `vancouver.cbc.birdcount.ca` (two labels) — that's still `*.cbc.birdcount.ca`'s job, hence still needing both wildcards. Neither wildcard covers the bare `birdcount.ca` apex itself, but nothing is served there yet, so it's deliberately left off.

(If `~/certbot-venv` doesn't exist yet: `python3 -m venv ~/certbot-venv && ~/certbot-venv/bin/pip install certbot` first.)

**`--key-type rsa` is required.** FullHost's "Custom SSL" form validates the key/cert pairing with what appears to be an RSA-specific check — an ECDSA key (which newer certbot defaults may produce) will cryptographically match its certificate just fine, but FullHost's form will reject it with a misleading "server key does not match domain certificate" error. This cost significant debugging time to track down — don't skip this flag.

**`--force-renewal` is required** once a non-expired cert for this exact name already exists, otherwise certbot refuses to reissue.

### 2. Add the DNS TXT records

Two wildcards means two separate DNS-01 challenges — certbot will pause twice (or print both values together, depending on version), once per domain:

| Challenge for | Host (relative, in Squarespace's DNS panel) | Verify with |
|---|---|---|
| `*.cbc.birdcount.ca` | `_acme-challenge.cbc` | `nslookup -type=TXT _acme-challenge.cbc.birdcount.ca` |
| `*.birdcount.ca` | `_acme-challenge` | `nslookup -type=TXT _acme-challenge.birdcount.ca` |

Add both TXT records (Data = the value certbot printed for that domain, no extra quotes — **not** the full dotted host, which would double up the domain suffix). Confirm both propagate via `nslookup` from a separate terminal before telling certbot to continue — continuing too early wastes an attempt against Let's Encrypt's rate limits.

### 3. Retrieve the three files certbot needs to hand to FullHost

Still in WSL, copy the certbot output to a plain Windows-visible path (avoids any WSL-symlink resolution issues — certbot's `live/` files are symlinks into `archive/`, and don't rely on browsing `\\wsl$\...` paths directly in a file picker):

```bash
mkdir -p /mnt/c/Users/harve/certs
cp -L ~/letsencrypt-birdcount/config/live/cbc.birdcount.ca/privkey.pem /mnt/c/Users/harve/certs/
cp -L ~/letsencrypt-birdcount/config/live/cbc.birdcount.ca/cert.pem /mnt/c/Users/harve/certs/
cp -L ~/letsencrypt-birdcount/config/live/cbc.birdcount.ca/chain.pem /mnt/c/Users/harve/certs/
```

The lineage folder name (`cbc.birdcount.ca`) is derived from the first `-d` passed (`*.cbc.birdcount.ca`, star stripped) and should stay the same across renewals as long as that first `-d` doesn't change. If certbot ever prints a different `live/...` path in its own output (e.g. a `-0001` suffix, which happens if it decides the domain list is different enough to warrant a new lineage), trust what it printed over this doc.

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
```

Check one host from each wildcard level, not just one — the cert now has two SANs covering different subdomain depths, so a working `*.cbc.birdcount.ca` host doesn't confirm `*.birdcount.ca` is also good (or vice versa). Confirm the new expiry date is ~90 days out on both.

## Renewal cadence

There is no automated reminder for this yet — set a calendar reminder for roughly every 80 days (Let's Encrypt allows renewal up to 30 days before expiry, so this leaves margin). FullHost's own default certificate for the platform's shared hostname was found expired and unnoticed during this migration — don't let this one suffer the same fate.
