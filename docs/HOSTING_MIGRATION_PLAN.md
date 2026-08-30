# Hosting Migration Plan: Google Cloud Run → FullHost PaaS
{# Updated by Claude AI on 2026-08-28 #}

## Target changed from VPS to PaaS (2026-08-28)

An earlier version of this plan (see git history) targeted a bare Ubuntu VPS at Canadian Cloud Hosting, with FullHost used only for off-site backup object storage. The user has since decided to target **FullHost's own PaaS product** (FullHost.Cloud DevOps PaaS) as the hosting platform itself, not just a backup destination. FullHost's PaaS is Jelastic/Virtuozzo-based (confirmed by its "Cloudlet" resource-unit terminology — 128 MiB RAM + 400 MHz CPU per cloudlet) and advertises Docker container support, Python runtime support, containerized PostgreSQL/MySQL/MongoDB nodes, Git/SVN deployment, and multi-region Canadian data centers (Toronto, Vancouver/"CA WEST").

This rewrite replaces VPS-specific phases (manual nginx/certbot/systemd/cron) with PaaS-native equivalents. Full technical confirmation of FullHost's specific feature set was not obtainable during planning — their `/cloud-paas/` and `/paas-hosting/` pages returned HTTP 403 to automated fetches — so **Phase 0 is now a feasibility spike**, not a confirmed starting point. Verify every bullet in Phase 0 against the actual FullHost dashboard/docs (or a support conversation) before committing to Phases 1–6 as written.

## Decisions locked in

- **Database**: PostgreSQL, run as a managed/containerized node inside the FullHost PaaS environment (not self-administered `apt install postgresql`).
- **Auth**: Email magic-link (replaces Google OAuth entirely) — unchanged from the VPS plan, this is app-level and platform-independent.
- **Off-site backups**: FullHost object storage (Canadian-owned, Canada-resident, S3-compatible) — now doubly convenient since it's the same vendor as the PaaS hosting, but see the backup-independence concern in "Expected problems" below.
- **Deployment**: Docker container, using the existing `Dockerfile` (already gunicorn + `$PORT` env var + non-root user — this was already PaaS-friendly before this migration was conceived) — deployed via FullHost's Git-based or Docker-based deploy mechanism rather than `gcloud run deploy`.
- **ORM recommendation** (not yet confirmed with user, just recommended in the plan): SQLAlchemy, so Postgres/MariaDB stays swappable and Alembic handles schema migrations.

## ⚠️ Timing — read this first

**Revised 2026-08-28: target cutover is before end of September 2026, not after count day.** `config/organization.py` sets the 2026 count date to **2026-12-19** and `REGISTRATION_OPENS = 4` months, so registration opened **2026-08-19**. As of today the season is only ~9 days old — very few registrations exist yet, which is exactly why the user wants to cut over now rather than waiting until after the 2026-12-19 count day: less live data to migrate/reconcile, and more of the season runs on the new stack (giving it a real workout well before the count itself, rather than right after building it).

This changes the risk shape from the original plan (which assumed waiting until the season was fully closed):

- **Lower initial-migration risk**: a Firestore export taken in late September has far fewer rows than one taken in mid-December, so the freeze/export/import/spot-check step in Phase 6 is smaller and easier to verify completely.
- **Higher rollback risk**: once cut over, new registrations keep arriving *on Postgres* for the rest of the season (Oct–Dec). If a serious problem is found and you need to roll back to Cloud Run/Firestore, every registration made after cutover has to be manually reconciled back into Firestore — there's no bidirectional sync. This risk grows every day you stay cut over before the count. **Mitigation**: do NOT treat "keep Cloud Run idle for weeks as rollback" the way the original plan did — if a rollback is ever needed, do it within hours/same-day of cutover, not weeks later. After the first few days on the new stack look clean, decommissioning Cloud Run sooner (rather than the original 2–4 week buffer) actually reduces confusion about which system is authoritative.
- **Compressed build timeline**: Phases 0–5 (FullHost spike, Postgres/SQLAlchemy rewrite, magic-link auth, secrets, deployment, backups) need to be done in roughly 4–5 weeks (now → end of September) instead of the ~4 months originally available. The core Flask route/template logic doesn't change, which is what makes this feasible — it's the data/auth/infra layers being swapped, not the application.

All build/dev work (Phases 0–5) still happens on a separate FullHost staging environment/subdomain with zero production risk. Phase 6 (cutover) is now targeted for **before 2026-09-30**.

## Target architecture

```
Internet → FullHost load balancer (TLS, Let's Encrypt) → app container (Docker: gunicorn + Flask) → PostgreSQL container (same FullHost environment)
                                                                    ↓
                                                         FullHost Task Scheduler: scheduled emails (replaces Cloud Scheduler)
                                                         FullHost Task Scheduler: pg_dump → FullHost object storage (off-site-ish backup)
```

Two environments (test/prod) mirror the current `cbc-test` / `cbc-register` split as two separate FullHost PaaS environments, each with its own app container + PostgreSQL container.

## Phase 0 — FullHost PaaS feasibility spike (no production impact)

Before trusting the rest of this plan, confirm each of these directly against a FullHost trial/account (their marketing pages didn't yield enough detail during planning):

- [ ] Docker container deployment works as expected using the existing `Dockerfile` as-is (or with minimal changes).
- [ ] A PostgreSQL node/container is available inside the same environment, with a documented backup/snapshot story (does FullHost already dump it for you, or is that entirely on you via Task Scheduler?).
- [ ] Environment variables / config-var mechanism exists for secrets (equivalent to Heroku config vars), settable per environment (test vs. prod) without baking secrets into the image.
- [ ] A **Task Scheduler** (or equivalent cron-like feature) exists that can run an arbitrary command inside the app container on a schedule — this replaces Cloud Scheduler for twice-daily/weekly emails and for the backup job.
- [ ] Custom domain + automatic TLS (Let's Encrypt or equivalent) is supported for both `cbc-test.naturevancouver.ca` and `cbc-registration.naturevancouver.ca`-equivalents.
- [ ] SSH/console access into the running container exists for troubleshooting (Jelastic-based platforms typically offer this; confirm FullHost does too).
- [ ] Git-based deploy (push-to-deploy) is available, or deployment is purely "build and push a Docker image" — this determines what `deploy.sh` becomes in Phase 4.
- [ ] Approximate cloudlet/cost estimate for the expected footprint: one small always-on app container + one small always-on Postgres container, per environment (×2 for test/prod), so there are no pricing surprises before committing further engineering time.

Only once these are confirmed should Phase 1 onward proceed as detailed below — if any assumption fails (e.g., no arbitrary cron, no persistent Postgres container), the corresponding phase needs to be redesigned around whatever FullHost actually offers.

## Phase 1 — Data layer rewrite

Note: `CLAUDE.md` references `models/area_leader.py`, but the current `models/` directory has no such file — leadership fields live directly on participant records (`is_leader`, `assigned_area_leader`, etc.), matching `docs/SPECIFICATION.md`. The schema below follows what's actually in the code.

**Schema** (one table per current model, `year` as a column instead of a Firestore collection-per-year):
- `participants` — indexes on `(year, area_code)`, `(year, email)`, `(year, is_leader)`
- `removal_log`, `reassignment_log`, `withdrawal_log` — one row per event, indexed on `(year, participant identity)`
- `area_signup_type` — admin-configurable per-area settings
- `blocked_ips`, `ip_violations` — replaces the Firestore-backed `services/ip_blocker.py` collections; `ip_violations` needs a cron-based cleanup job since Postgres has no equivalent of Firestore's TTL-policy auto-expiry
- `magic_link_tokens` — new, for Phase 2 (email, token_hash, expires_at, used_at)

**Work**:
- Recommend **SQLAlchemy** over hand-written SQL for the model layer — keeps Postgres/MariaDB swappable later and gives you Alembic for schema migrations.
- Rewrite `config/database.py`, `app.py`, every file in `models/`, and `services/ip_blocker.py` against SQLAlchemy instead of `google.cloud.firestore`.
- Firestore's design avoided compound indexes by filtering in Python (per `docs/SPECIFICATION.md`). Don't port that pattern as-is — Postgres does compound filtering natively and faster with a real index. Take advantage of it rather than replicating the workaround.
- Write a one-time Firestore → Postgres migration script: export each year's collections to JSON (reuse existing export patterns from `utils/backup_firestore.py` as a starting point), transform, bulk-insert.
- Update `tests/conftest.py` and test fixtures to run against a local Postgres instance instead of `cbc-test`. This is a genuine improvement: CLAUDE.md currently notes you can't test locally at all — with Postgres available locally (via Docker Compose for dev, matching the local-dev-parity use of the existing `Dockerfile`), you'll be able to for the first time.

## Phase 2 — Auth rewrite (Google OAuth → email magic-link)

- Remove `google-auth`/`id_token` usage from `routes/auth.py` and `routes/scheduler.py`.
- New flow: a login request generates a single-use token (`secrets.token_urlsafe`), stores a **hash** of it plus a short expiry (~15 min) in `magic_link_tokens`, and emails the link via the existing `EmailService`/SMTP2GO — no new email infrastructure needed.
- The callback route verifies the token, marks it used (single-use), creates the session, and follows the existing role-resolution logic (`config/admins.py` whitelist → admin; `is_leader=True` on a participant record → leader).
- **Rate-limit the "request a link" endpoint hard**, and validate the submitted email against known admin/leader addresses before sending — an open magic-link request endpoint is otherwise an easy way to spam an inbox or probe which emails are valid leaders. Reuse the existing `RATE_LIMITS` pattern in `config/rate_limits.py`.
- Replace `routes/scheduler.py`'s Cloud Scheduler OIDC check with a call from FullHost's Task Scheduler directly into a local management command (or an internal-only route, if Task Scheduler only supports HTTP hits — confirm which in Phase 0) — either way, no OIDC verification needed once it's not an arbitrary public internet caller.
- Update the CSP header in `app.py` to drop `accounts.google.com` once Google Sign-In is gone.
- Update `templates/auth/login.html`.

## Phase 3 — Secrets & config

- Move `SECRET_KEY` and SMTP2GO credentials (Google OAuth secrets go away entirely) into FullHost's environment-variable/config-var mechanism, scoped per environment (test vs. prod) — confirmed to exist in Phase 0.
- Update `config/database.py`/`config/cloud.py` for Postgres connection strings, read from environment variables rather than GCP-specific client libraries.

## Phase 4 — Deployment mechanics

- Deploy via whatever Phase 0 confirms: most likely `git push` to a FullHost-managed remote, or building the existing `Dockerfile` and pushing the image — either way, no manually-managed nginx/certbot/systemd, since the PaaS's load balancer and container orchestration replace all three.
- Replace `deploy.sh`'s `gcloud run deploy` with the FullHost equivalent (CLI or API call), followed by `alembic upgrade head` as a release-phase step (check whether FullHost supports pre/post-deploy hooks, or whether this needs to run manually/via Task Scheduler on first boot after a schema change).
- Keep the existing `Dockerfile` for both local dev parity **and** production deployment — unlike the earlier VPS plan, there's no RAM-overhead reason to avoid Docker here, since the PaaS runs everything in containers regardless.

## Phase 5 — Backups

- Scheduled `pg_dump` via FullHost's Task Scheduler → FullHost object storage. Consider hourly dumps during the active registration window (mirrors the old "hourly when changed" Firestore policy) given how cheap storage is for a database this size.
- **Backup independence concern**: since both the live Postgres container and the backup destination are on the same vendor (FullHost), this is not truly "off-site" in the disaster-recovery sense the old VPS-plus-FullHost-storage design had — a FullHost-wide outage or account issue could affect both simultaneously. Decide whether a second, independent off-site copy (a different provider, or periodic download to a local/personal machine) is worth the extra complexity given the app's low data volume and revenue-none nature. Cheap insurance either way.
- Retention: prune local/staging copies after a confirmed successful upload; keep the last 60 days offsite, always preserving the most recent (same policy as `docs/BACKUPS.md` today).
- **Explicitly test the restore procedure** and put a recurring reminder to redo the drill quarterly — a backup that's never been restored is a hypothesis, not a backup.

## Phase 6 — Parallel run & cutover (target: before 2026-09-30)

- Deploy the finished stack to a FullHost staging environment/subdomain, run the full test suite against it, and manually walk through registration, leader dashboard, admin dashboard, scheduled emails, and CSV export.
- Freeze writes on Cloud Run briefly, take a final Firestore export, import into Postgres, and spot-check row counts and a sample of records. This should be a small, fast, fully-verifiable export given the low registration volume this early in the season.
- Lower DNS TTL a day ahead, then repoint `cbc-test.naturevancouver.ca` and `cbc-registration.naturevancouver.ca` to the FullHost environments.
- Watch closely for the first 24–72 hours — this is the highest-value window for catching problems, since every day past that adds registrations that would need manual reconciliation on a rollback (see the timing note above).
- Keep the Cloud Run services deployed (idle, not deleted) through count day (2026-12-19) as a rollback path, but treat "actually roll back" as a same-day decision, not a weeks-later one.
- After count day and post-count admin wrap-up (~January 2027): delete the Cloud Run services, export and archive the Firestore databases, delete them, revoke the old Secret Manager secrets and OAuth client, and clean up the GCP project.

## Component replacement map

| Concern | Current (GCP) | New (FullHost PaaS) |
|---|---|---|
| App hosting | Cloud Run | FullHost PaaS Docker container |
| Database | Firestore | PostgreSQL (containerized node in same environment) |
| Secrets | Secret Manager | FullHost environment variables / config vars |
| Auth | Google OAuth | Email magic-link |
| Scheduled jobs | Cloud Scheduler (OIDC) | FullHost Task Scheduler |
| Backups | Cloud Function + GCS | Task Scheduler pg_dump → FullHost object storage |
| TLS | Managed by Cloud Run | FullHost load balancer (Let's Encrypt or equivalent) |
| Email | SMTP2GO (unchanged) | SMTP2GO (unchanged) |
| Rate limiting | Flask-Limiter, `memory://` (unchanged) | Flask-Limiter, `memory://` (unchanged — confirm single-container deployment keeps this valid; revisit if FullHost horizontally scales the app container, since `memory://` doesn't share state across instances) |

## Expected problems & platform recommendations

1. **Unconfirmed platform specifics.** This entire plan rests on Phase 0 confirming FullHost's PaaS actually offers Docker deploy, a persistent Postgres container, arbitrary cron, and env-var secrets. Their public pages didn't yield enough detail to be sure. Treat Phases 1–6 as provisional until Phase 0 checks out — budget time for a redesign if something's missing.
2. **Horizontal auto-scaling and `memory://` rate limiting.** FullHost's PaaS advertises "automatic vertical and horizontal scaling." If the app container ever runs as more than one instance, Flask-Limiter's in-memory store (already a known limitation, per the recent `b505a14 Fix 404-violation tracking across Cloud Run instances` commit) breaks the same way it did on Cloud Run. Pin the app to a single instance, or plan a shared store (Postgres-backed or Redis-backed) if scaling is ever turned on.
3. **Vendor/platform lock-in via deployment tooling.** Jelastic-based PaaS platforms typically have their own manifest format and CLI. Keep the Docker image itself portable (works today) even if the deployment glue around it becomes FullHost-specific.
4. **No managed point-in-time recovery.** Firestore's durability is gone; you're relying on periodic `pg_dump`s via Task Scheduler, so your recovery point objective is "since the last dump," not continuous. For this app's write volume, nightly (or hourly in-season) dumps are probably sufficient, but it's a real gap worth naming.
5. **Backup independence** — see Phase 5 note above; same-vendor hosting and backup storage is convenient but not a full disaster-recovery story.
6. **Magic-link abuse surface.** Covered in Phase 2, but worth re-flagging here as a security-relevant behavior change, not just an implementation detail.
7. **Email deliverability is unaffected.** Since email already goes through the SMTP2GO relay rather than being sent directly from the app server, moving hosts doesn't introduce any new IP-reputation risk. Confirm this stays true (i.e., don't switch to sending directly from a FullHost-assigned IP).

## Suggested timeline (revised 2026-08-28 for a September cutover)

- **2026-08-28 – ~2026-09-05**: Phase 0 FullHost feasibility spike (1–2 days), then start Phase 1 (Postgres schema + SQLAlchemy rewrite).
- **~2026-09-05 – ~2026-09-20**: finish Phases 1–5 (data layer, magic-link auth, secrets, deployment mechanics, backups) against a FullHost staging environment.
- **~2026-09-20 – ~2026-09-27**: full test suite + manual QA pass on staging; fix anything found.
- **Before 2026-09-30**: Phase 6 cutover — freeze, export, import, DNS repoint. Watch closely for 24–72 hours.
- **October – 2026-12-19 (count day)**: run live on the new stack through the actual count, monitoring closely; Cloud Run stays idle as a same-day rollback option.
- **January 2027**: after post-count wrap-up, decommission Cloud Run, Firestore, and the GCP project.

If Phase 0 turns up a blocker (e.g., no persistent Postgres container, no arbitrary cron), reassess the September target immediately rather than trying to force the original plan onto a platform that doesn't support it — falling back to the original January cutover window is always available.
