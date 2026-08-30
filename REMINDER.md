# Session Reminder - Hosting Migration (Cloud Run → FullHost PaaS)
Updated by Claude AI on 2026-08-29

## What We Were Working On

Planning a migration of this Flask app from Google Cloud Run + Firestore to **FullHost's PaaS product** (FullHost.Cloud DevOps PaaS — Jelastic/Virtuozzo-based, Canadian-owned, Toronto/Vancouver data centers). This is planning/analysis only so far — **no migration code has been written yet.**

Note: an earlier version of this plan targeted a bare Ubuntu VPS at Canadian Cloud Hosting, with FullHost used only for off-site backup object storage. As of 2026-08-28 the target changed: FullHost's own PaaS is now the hosting platform itself, not just a backup destination.

## Decisions Already Made (do not re-litigate these)

- **Database**: PostgreSQL, as a managed/containerized node inside the FullHost PaaS environment (chosen over MariaDB)
- **Auth**: Email magic-link, replacing Google OAuth entirely (chosen over username/password, another OAuth provider, or keeping Google Sign-In) — platform-independent, unaffected by the VPS→PaaS target change
- **Backups**: FullHost object storage, via a scheduled `pg_dump` — see the "backup independence" caveat in the plan (same vendor as hosting now, so this isn't a fully independent off-site copy)
- **Deployment**: Docker container, using the existing `Dockerfile` (already gunicorn + `$PORT` + non-root user) — deployed via FullHost's git/Docker deploy mechanism, not systemd/nginx (that was the old VPS plan)
- **ORM recommendation** (not yet confirmed with user, just recommended in the plan): SQLAlchemy, so Postgres/MariaDB stays swappable and Alembic handles schema migrations

## Not Yet Confirmed — Phase 0 spike required

FullHost's `/cloud-paas/` and `/paas-hosting/` pages returned HTTP 403 to automated fetches during planning, so these are **unconfirmed assumptions**, not verified facts:
- Docker container deployment from the existing `Dockerfile`
- A persistent/backed-up PostgreSQL container option
- Environment-variable/config-var secrets mechanism
- A Task Scheduler (cron-equivalent) that can run arbitrary commands
- Custom domain + automatic TLS
- SSH/console access for troubleshooting
- Git-based push-to-deploy
- Realistic cloudlet/cost estimate for 2 environments × (app container + Postgres container)

Confirm these against a real FullHost account/trial before trusting Phases 1–6 of the plan as written.

**Update 2026-08-29 — Phase 0 spike results:** Environment created on FullHost CA West (Jelastic-based, `env-8450249.ca-west.oncoregrid.ca`): one **Python Engine** app node (Python 3.14.7, reserved cloudlets bumped to platform-enforced minimum of 4, vertical scaling headroom up to 4→7 total cloudlets across both nodes) + one **PostgreSQL 18.6** node (fixed at 3 cloudlets, no min/max range — that's the platform floor for Postgres). Horizontal scaling left at 1 instance/Stateful (deliberate — see "single-instance" note below). Public IPv4 left OFF (no functional need; traffic routes via the built-in SLB/load balancer). SSH/console access, Task Scheduler, git/Docker deploy mechanism, env-var secrets, and custom domain+TLS have NOT yet been individually verified inside the created environment — that's the next concrete Phase 0 step.

**Cost finding (2026-08-29):** Reserved cloudlets are a guaranteed 24/7-billed floor, not a soft ceiling. With Python Engine's reserved forced to its stated minimum (4) plus Postgres's fixed 3, the combined reserved floor lands around the environment's previously-shown "ceiling" estimate of **~CAD 13.70/month (~$164 CAD/year)** for hosting alone — over the user's stated <$150/year hosting target, before adding an expected ~$60/year for SMTP mail service. Public IPv4 would add ~$3.60/month more (kept OFF to avoid this). Two unexplored cost levers: (1) set Python's scaling limit down to match its reserved minimum (4) to at least flatten the price rather than allow further ceiling growth — this app doesn't need elastic autoscaling given its scale (~10 concurrent users); (2) check whether "Apache Python" or "Docker Engine CE" node types (an already-considered fallback if Python Engine's native start-command support didn't pan out) have a lower reserved-cloudlet minimum than Python Engine's stated 4 — untested as of 2026-08-29.

**Open question raised by user (2026-08-29):** given this cost finding, reconsidered whether a bare self-managed VPS (cheaper, but user manages backups/TLS/OS patching directly) would be preferable to FullHost's PaaS. Recommendation given: stay on the just-created PaaS environment for this migration cycle given the hard Sept 2026 deadline — switching now would mean rebuilding the nginx/certbot/systemd/backup-cron plumbing that PaaS was chosen specifically to avoid. Treat bare-VPS as a post-launch re-evaluation once the migration is stable and there's no deadline pressure, not a pre-launch decision to reopen. Note: the `pg_dump`-to-object-storage backup approach was already the plan regardless of host, so it isn't a major *new* burden specific to VPS — the genuinely VPS-specific overhead is OS patching, firewall, and TLS renewal (mitigated somewhat by tools like Caddy vs. raw certbot).

**SSH/SCP finding (2026-08-29):** FullHost's SSH access is a menu-gated bastion (`ssh <account>@gate.vap.fullhost.cloud -p 3022`, e.g. account `687` for harvey.dueck@gmail.com) that prompts interactively for environment then container (node `11291` = Python Engine, node `11292` = PostgreSQL) before dropping into a shell — there is no config step needed beyond adding an SSH public key. This breaks non-interactive tools: `scp`/`sftp` open a subsystem channel expecting immediate protocol bytes, not a menu conversation. Tried using the node ID alone as the SSH username (a common bypass convention on other Jelastic-based gateways) — that failed with `Permission denied (publickey,gssapi-keyex,gssapi-with-mic)`, since publickey authorization is tied to the account identifier, not a bare node ID.

**Resolved (2026-08-29):** the correct direct-connect syntax combines both: `<nodeid>-<account>@gate.vap.fullhost.cloud`, e.g. `ssh -p 3022 11292-687@gate.vap.fullhost.cloud` (11292 = PostgreSQL, 11291 = Python Engine, 687 = harvey.dueck@gmail.com's account). This bypasses the interactive menu entirely and should make scp/sftp usable the same way, e.g. `scp -P 3022 file.txt 11292-687@gate.vap.fullhost.cloud:~` (untested as of this note — confirm scp specifically still works with this form). Still untested: whether the dashboard also has a per-node file manager as an alternative.

## Python Engine node type: ruled out (2026-08-29)

Confirmed conclusively by reading `/usr/local/sbin/process-manager` (the actual launcher script on node 11291) that **Python Engine nodes on FullHost are ASGI-only** — both its `gunicorn` and `uvicorn` code paths hardcode `-k uvicorn.workers.UvicornWorker`. `PROCESS_MANAGER=gunicorn` only swaps which process supervises the workers; it does not provide a WSGI/sync path, and no env var does. This isn't a config gap to solve — Flask (WSGI) cannot run correctly on this node type without an ASGI adapter shim (e.g. `asgiref.wsgi.WsgiToAsgi`).

**Decision:** rather than carry a permanent WSGI→ASGI shim purely to fit this template's default, pivot the app node to **Apache Python** (Apache + mod_wsgi, WSGI-native) instead of Python Engine. Still to verify on the new node type (same spirit as the Python Engine spike above): whether process count is configurable to `processes=1` (the rate limiter in `config/rate_limits.py` still uses `LIMITER_STORAGE_URL = 'memory://'`, which assumes a single process — Apache's default MPM spawns multiple, which would reintroduce the same cross-instance bug already fixed once for Firestore in `services/ip_blocker.py`/commit `b505a14`), request-timeout equivalent to the Dockerfile's `--timeout 0` (used for long admin operations like CSV export), dependency-install convention (venv vs system pip3), and git-based push-to-deploy availability. **Docker Engine CE remains the fallback** if Apache Python introduces its own blockers on any of these.

**Environment recreated 2026-08-29 (Apache Python, not just a node swap):** the user deleted the old environment (`env-8450249`) entirely and created a fresh one — `env-5397859`, node `11294` = Apache Python 2.4.68 / mod_wsgi 4.9.4 / Python 3.14.7, node `11293` = PostgreSQL (fresh instance, new credentials — old `.pgpass` from node 11292 is void). Consequences: the `cbc-test.birdcount.ca` CNAME (pointed at the old env's hostname) and the FullHost-dashboard custom-domain/TLS registration both need to be redone against the new environment. SSH gateway syntax is unaffected (`<nodeid>-<account>@gate.vap.fullhost.cloud -p 3022`, account stays `687`).

**Apache Python deployment convention (confirmed via node inspection):** `WSGI_SCRIPT=/var/www/webroot/ROOT/wsgi.py`, `WEBROOT=/var/www/webroot`. The placeholder `wsgi.py` uses the classic `def application(environ, start_response):` signature — Flask's `app` object already satisfies this directly (`Flask.__call__` matches the WSGI interface), so no adapter/shim is needed, unlike the Python Engine dead end. Deployment plan: replace `wsgi.py` with `from app import app as application` (after appending `/var/www/webroot/ROOT` to `sys.path`), with the full app codebase deployed alongside it under `/var/www/webroot/ROOT/`. Also present in this container image: `OWASP_MODSECURITY_CRS_VERSION=3.3.2` — a WAF (ModSecurity Core Rule Set) is active in front of Apache, which could produce false-positive 403s on legitimate requests (e.g. admin POST bodies, CSV export params) unrelated to the app's own `IPBlockerService` — worth ruling out if unexplained 403s show up during testing.

## Apache Python config fixed + future multi-circle goal (2026-08-29)

`/etc/httpd/conf.d/wsgi.conf` on node 11294 originally had `WSGIDaemonProcess ... processes=2` — fixed to `processes=1` (file is `apache:apache`-owned and directly editable via SSH) to preserve the single-process assumption the `memory://` rate limiter needs. **Rate limiting still needs a real fix later** (shared backend, not `memory://`) — the user wants a fix that also supports the new goal below, not just a single-instance patch.

**New future goal (deferred, not started):** the user wants this app to eventually support **multiple different bird count circles sharing one PostgreSQL database**, not just Nature Vancouver — see the `multi-circle-architecture` memory (auto-memory system, project-type) for full detail. Explicitly deferred, but it should influence the Phase 1 schema design happening now: include a tenant/circle identifier on relevant tables from the start rather than a purely single-org schema, even though the full multi-tenant behavior (routing, per-circle config, admin scoping) isn't being built yet.

**Sequencing decision (2026-08-29, final):** user chose to skip the smoke-test deploy and go straight into the Postgres/SQLAlchemy rewrite (Phase 1) — "we'll smoke test once we have something that might run in the new environment." Phase 1 is now in progress.

## Domain change (2026-08-29)

The app will be hosted on **birdcount.ca**, not `naturevancouver.ca` as CLAUDE.md's "Testing" section currently states — user created a CNAME `cbc-test.birdcount.ca` pointing at the FullHost test environment. `config/organization.py`'s `ORGANIZATION_WEBSITE` (`naturevancouver.ca`, the club's own separate main site) is unaffected — this is purely about which domain the registration app itself is served from. Not yet updated in code (`config/cloud.py`'s `TEST_BASE_URL`/`PRODUCTION_BASE_URL`) since that's Phase 1 work; production domain (bare `birdcount.ca`? another subdomain?) not yet decided — ask when Phase 1 starts if not already told. Still need to confirm the custom domain is also registered in FullHost's dashboard (SSL/Balancer settings) for routing + TLS — a DNS CNAME alone is typically not sufficient on Jelastic-family platforms.

## Critical Constraint: Timing (revised 2026-08-28)

The 2026 count date is **2026-12-19**, and `REGISTRATION_OPENS = 4` months in `config/organization.py` means the current registration season opened **~2026-08-19** — as of today (2026-08-28) the season is only ~9 days old. **The user now wants to cut over before end of September 2026**, not wait until after count day, specifically because it's early in the season and there's minimal live data to migrate yet. This trades lower initial-migration risk for higher rollback risk (see `docs/HOSTING_MIGRATION_PLAN.md`'s timing section) — once cut over, new registrations land on Postgres for the rest of the season with no bidirectional sync back to Firestore, so a rollback has to happen fast (hours/same-day), not weeks later. Re-check `config/organization.py`'s `YEARLY_COUNT_DATES` and `REGISTRATION_OPENS` if resuming after 2026 — the season dates shift every year.

## Branch strategy

The user created `gcloud-2026-working` as a snapshot/anchor branch (currently identical to `main`) to preserve the current Google Cloud state as a fallback. Recommended approach for the migration itself: a long-lived feature branch (e.g. `fullhost-paas-migration`), checked out in a separate `git worktree` directory alongside the main checkout — not a full second clone — so both the old (Firestore) and new (Postgres) app can run side-by-side locally during development without repeated stash/checkout. `main`/`gcloud-2026-working` stays the only thing ever deployed to Cloud Run production during the migration.

## Full Plan

**Read `docs/HOSTING_MIGRATION_PLAN.md` first — it has the full phased plan (0–6), a component replacement map, and a list of expected problems.** Phase 0 is now a feasibility spike against FullHost's actual PaaS product, not a confirmed starting point. Don't redo the Phase 1/2 analysis; it reflects direct inspection of `config/database.py`, `config/cloud.py`, `routes/auth.py`, `routes/scheduler.py`, `services/ip_blocker.py`, `services/limiter.py`, `services/email_service.py`, `models/*.py`, `deploy.sh`, `Dockerfile`, and `requirements.txt`.

## Current Status

- `docs/HOSTING_MIGRATION_PLAN.md` rewritten 2026-08-28 for the FullHost PaaS target and a September 2026 cutover, and is the source of truth for the plan.
- `fullhost-paas-migration` branch created off `main`, checked out in a separate worktree at `../christmas-bird-count-fullhost`. This is now the active workspace for migration work; `main`/`gcloud-2026-working` in the original directory stays the only thing deployed to Cloud Run.
- **FullHost environment provisioned 2026-08-29** — see "Phase 0 spike results" above for the node config and unresolved cost question. Remaining Phase 0 items (SSH access, Task Scheduler, git/Docker deploy, env-var secrets, custom domain+TLS) still need to be verified against the live environment.
- No application code changes made yet. Next steps: finish verifying the remaining Phase 0 items above, then decide on the Postgres/SQLAlchemy schema work (Phase 1).
- Note: `CLAUDE.md` references `models/area_leader.py`, but that file does not exist in the current codebase — leadership fields live directly on participant records. Trust the actual `models/` directory contents over `CLAUDE.md`'s description here.

---

## Prompt for New Session

**Context:** This is the Christmas Bird Count registration system (Flask + Firestore, currently deployed on Google Cloud Run) for Nature Vancouver. The user is migrating it to FullHost's PaaS product (FullHost.Cloud DevOps PaaS, Canadian-owned) because they want off Google Cloud entirely.

**Task:** Read `docs/HOSTING_MIGRATION_PLAN.md` in full before doing anything else — it contains the complete phased migration plan, already-made technology decisions, and a list of expected problems. Do not re-ask the user about database choice, auth method, backup destination, or deployment container strategy — those are settled (see "Decisions Already Made" above). Phase 0's FullHost-specific technical assumptions ARE still open — confirm them with the user/against a real FullHost account before proceeding past Phase 0.

**Before writing any code**, check with the user:
1. Has a FullHost account/PaaS environment been provisioned yet, and have the Phase 0 feasibility items been checked?
2. What's today's date relative to `YEARLY_COUNT_DATES` in `config/organization.py`? Confirm we're still outside an active registration window before doing anything that touches production, per the timing constraint above.
3. Confirm they still want to proceed with Phase 0 (FullHost feasibility spike) as the next step, or if priorities have shifted.
4. Confirm whether a `fullhost-paas-migration` branch/worktree has been created yet, or if this session should set one up.

**Key files:**
- `docs/HOSTING_MIGRATION_PLAN.md` — the full plan, read this first
- `config/organization.py` — count dates and registration window logic, check before touching production
- `config/database.py`, `config/cloud.py` — current Firestore config, to be replaced
- `models/*.py`, `services/ip_blocker.py` — Firestore-coupled code to be rewritten
- `routes/auth.py`, `routes/scheduler.py` — Google OAuth/OIDC code to be replaced
- `Dockerfile` — already PaaS-friendly (gunicorn, `$PORT`, non-root user), likely reusable as-is for FullHost
