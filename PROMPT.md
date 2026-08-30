# Resume Session: FullHost Migration — Phase 1+2 Rewrite Done, Not Yet Deployed
Updated by Claude AI on 2026-08-29 (end of session)

## Context

This is the Christmas Bird Count registration system (Flask) for Nature Vancouver, migrating off **Google Cloud Run + Firestore** onto **FullHost's PaaS** (FullHost.Cloud DevOps PaaS — Jelastic/Virtuozzo-based, Canadian-owned). Reason: user wants off Google entirely (hosting *and* auth), plus a hard data-residency requirement (Canadian/European ownership only). Target cutover: **before 2026-09-30** (count day is 2026-12-19; re-check `config/organization.py`'s `YEARLY_COUNT_DATES`/`REGISTRATION_OPENS` if resuming much later, since the safe non-production-impacting window shifts every year).

Working directory is a **git worktree** at `../christmas-bird-count-fullhost`, branch `fullhost-paas-migration`, sibling to the original repo (which stays on `main`/`gcloud-2026-working`, the only thing deployed to Cloud Run production). Don't `cd` out of this worktree.

**Read `docs/HOSTING_MIGRATION_PLAN.md` and `REMINDER.md` for full historical detail** (FullHost node-type investigation, cost analysis, SSH gateway syntax discovery, the Python-Engine-ruled-out decision, etc.) — this file only summarizes current state and next steps. Auto-memory (`hosting-migration`, `multi-circle-architecture`, `feedback-shell-preference`) should also load automatically in a new session.

## ⚠️ Most important thing to know: today's rewrite is uncommitted

**26 modified/new files from today's Phase 1+2 rewrite are sitting uncommitted in the working tree.** Nothing has been committed since `0a7d0fe` (just the `wsgi.py` addition, already pushed). Before doing anything else — including further testing — decide with the user whether to commit this work (in one or several commits), and push to `origin/fullhost-paas-migration`. Check `git status` and `git diff` first to see everything.

## What's done

**Phase 0 (FullHost feasibility) — complete.** Environment `env-5397859` on FullHost CA West: node `11294` = **Apache Python 2.4.68 / mod_wsgi 4.9.4 / Python 3.14.7** (Python Engine was tried first and ruled out — it's ASGI-only, confirmed by reading its launcher script, no WSGI path exists), node `11293` = **PostgreSQL** (version 18.6 presumably, matching the earlier node). SSH: `ssh -p 3022 <nodeid>-687@gate.vap.fullhost.cloud` (687 = harvey.dueck@gmail.com's account; the account-only or node-only forms both fail — it must be `<nodeid>-<account>` combined). `scp` works the same way. Git deploy is configured in FullHost's Deployment Manager (repo `https://github.com/commonloon/christmas-bird-count-registration.git`, branch `fullhost-paas-migration`) but **the deploy has never actually been triggered** — still purely local-only testing so far.

**Phase 1+2 (Postgres + magic-link auth rewrite) — code complete, tested locally, not deployed.** Full SQLAlchemy/Alembic rewrite replacing Firestore, and Google OAuth replaced with email magic-link auth. Key points:
- New `models/db.py`: all ORM tables, plus a `circle_slug` placeholder column (default `'vancouver'`) on tenant-scoped tables — not a full multi-tenant build-out, just avoiding a costly later retrofit (see `multi-circle-architecture` memory).
- **Design decision that kept the blast radius small**: every model class kept its exact original method names/signatures/return shape (plain dicts with an `'id'` key), so `routes/*.py` and templates needed almost no changes — just renaming the `get_firestore_client` import to `get_db_session` at ~6 call sites. `routes/api.py` was the exception — it built its models once at *module import time*, which breaks with a per-request session; restructured to build them per-request.
- Alembic: `alembic.ini` + `migrations/` with one **hand-written** initial migration (`0001_initial_schema.py`) — no live DB was available to autogenerate against when it was written, so it mirrors `models/db.py` by hand. Keep them in sync if either changes.
- Auth: `routes/auth.py` now does email/magic-link (token via `secrets.token_urlsafe`, SHA-256 hash stored, 15-min expiry, single-use, only sent to known admin/leader emails — same generic "check your email" response either way, to prevent enumeration). `routes/scheduler.py`'s Google OIDC check replaced with a shared-secret bearer token (`SCHEDULER_SECRET` env var) — **this is provisional**, since FullHost's actual Task Scheduler calling convention (HTTP hit vs. in-container command) is still unconfirmed.
- Dependencies: `SQLAlchemy`, `alembic`, `psycopg[binary]` (psycopg **3**, not legacy psycopg2 — chosen because Python 3.14 is too new for psycopg2's binary wheels to be reliable; confirmed working).

**Bugs found and fixed during testing today** (all in the new code unless marked pre-existing):
- FK constraint on `reassignment_log.participant_id`/`withdrawal_log.participant_id` needed `ondelete='SET NULL'` — without it, deleting a participant with any log history threw a `ForeignKeyViolation` (Firestore never had this problem since it had no real referential integrity).
- **Systemic timezone bug**: Firestore always silently normalized timestamps to timezone-aware UTC on read; Postgres doesn't. Every `datetime.now()` that stores/compares against a timestamp column had to become `datetime.now(timezone.utc)`, and every timestamp column had to become `DateTime(timezone=True)` (`TIMESTAMPTZ`). Fixed across `models/db.py`, `participant.py`, `area_signup_type.py`, `routes/auth.py`, `routes/admin.py`, `services/ip_blocker.py`. This was the root cause of a real crash on `/admin/recent-registrations`.
- `routes/leader.py`'s `before_request` had a stray unconditional `flash('Database unavailable.', 'error')` left over from an incomplete edit — fired on every leader page load. Removed.
- `require_admin` (in `routes/auth.py`) now redirects leaders who hit an admin-only URL to `/leader/` instead of showing "Admin access required" and dead-ending at the homepage.
- **Pre-existing, not from this migration**: `/admin/blocked-ips` 500'd — missing `current_user` in its `render_template` call, and its template referenced a nonexistent `admin.index` endpoint (should be `admin.dashboard`). Both fixed.

**Verified working locally** (via `flask run` + a mix of real HTTP requests through Flask's test client and direct model calls): registration form (user tested manually in browser), magic-link request+verify+session flow (including anti-enumeration and single-use enforcement), admin dashboard and every other admin page, `assign_participant`, `delete_participant` (including the FK-history case), CSV export, area-signup-type toggling, IP blocking (404 tracking + honeypot), and the full scheduled-email pipeline (team updates/weekly summaries/admin digest) both as direct calls and through the real `/admin/test/trigger-*` HTTP routes.

## Local dev environment (already set up on this machine)

- Python venv at `.venv/` (already has all deps from `requirements.txt` installed).
- Local PostgreSQL: role `cbc` **owns** database `cbc_dev` (not `postgres`-owned+granted — avoids permission friction as Alembic creates new tables).
- `.env` (gitignored, not committed — see `.env.example` for the required variable names): `DATABASE_URL=postgresql+psycopg://cbc:...@localhost:5432/cbc_dev`, `SMTP2GO_USERNAME`/`SMTP2GO_PASSWORD` (real credentials, already configured and confirmed working), `TEST_MODE=true` (redirects all outgoing email to `birdcount@naturevancouver.ca` instead of real recipients — confirm this is still set before doing anything that sends email to avoid spamming real users, since this is still very much a test server).
- **Local DB is currently empty** — schema exists (migrated) but all data was wiped by two `alembic downgrade base && upgrade head` cycles needed to apply schema fixes during testing. The user's own manual UI registration test data is gone; they'll need to re-register if they want to look at that again.
- **Run the dev server with `flask run`, never `python app.py` directly** — `routes/auth.py` does `from app import csrf`, which only resolves correctly when `app.py` is *imported* as a module (as gunicorn/mod_wsgi and `flask run` do); running it as `__main__` creates two separate module identities and throws a circular-import error. Command (Git Bash — **this user's default shell**, don't default to PowerShell):
  ```bash
  cd /c/AndroidStudioProjects/christmas-bird-count-fullhost
  FLASK_APP=app.py .venv/Scripts/flask.exe run --host 127.0.0.1 --port 8080
  ```

## Not yet done / open items for next session

1. **Commit and push today's work** (see warning above) — do this first.
2. **Trigger the actual FullHost git deploy** and see what breaks. Known unknowns going in: whether `pip install` into `/var/www/webroot/virtenv/lib/python/` (nonstandard path, no trailing version number — a plain `python3 -m venv` may not match it exactly) works as expected; whether `processes=1` in `/etc/httpd/conf.d/wsgi.conf` survived (it was edited directly over SSH, not through the dashboard, on the *old* environment — needs re-confirming on `env-5397859`/node `11294`).
3. **Wire up production secrets on FullHost**: `DATABASE_URL` (grab fresh Postgres credentials from node 11293's `.pgpass` over SSH), `SMTP2GO_USERNAME`/`PASSWORD`, `SECRET_KEY`, `SCHEDULER_SECRET` — all via the app node's "Variables" panel, confirmed to actually reach the process as real env vars (still not empirically re-tested since the environment was recreated).
4. **Custom domain + TLS**: `cbc-test.birdcount.ca` CNAME exists but needs re-pointing at `env-5397859` (it was set up against the now-deleted `env-8450249`), and the FullHost-dashboard custom-domain/TLS registration needs to be redone too. HTTP was confirmed working on the old environment; HTTPS was never confirmed at all.
5. **Task Scheduler**: still completely unconfirmed against the real FullHost dashboard — whether it exists, whether it hits an HTTP URL (in which case the `SCHEDULER_SECRET` bearer-token approach in `routes/scheduler.py` should work) or does something else entirely.
6. **Rate limiter** (`config/rate_limits.py`, still `LIMITER_STORAGE_URL = 'memory://'`) — deferred fix, needs a shared backend eventually, ideally designed together with the ambient multi-circle goal rather than as a single-instance patch.
7. `deploy.sh` still calls `gcloud run deploy` — needs a FullHost-appropriate replacement once the deploy mechanism (git push vs. something else) is settled.
8. `CLAUDE.md` still documents Firestore-era patterns and Cloud Run testing URLs — stale, not updated this session.
9. Firestore → Postgres data migration script — not started, but low urgency (minimal live season data as of late August).

## Key files

- `docs/HOSTING_MIGRATION_PLAN.md` — original phased plan (Phase 0 confirmed, Phase 1/2 now done — plan text itself wasn't updated to reflect completion, treat it as historical intent, not current status)
- `REMINDER.md` — detailed chronological log of the FullHost investigation, cost analysis, and node-type decision-making
- `C:\Users\harve\.claude\plans\playful-cuddling-toast.md` — the approved implementation plan for the Phase 1+2 rewrite (useful if you need the original design reasoning for the schema/auth choices)
- `models/db.py` — the whole Postgres schema in one place
- `.env.example` — required local environment variables (never put real values here)
