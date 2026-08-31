# Resume Session: FullHost Multi-Circle Platform — Live, Iterating on Admin UX
Updated by Claude AI on 2026-08-30 (end of session)

## Context

This is the Christmas Bird Count registration system (Flask) for Nature Vancouver, migrated off **Google Cloud Run + Firestore** onto **FullHost's PaaS** (Jelastic/Virtuozzo-based, Canadian-owned), and now being extended into a **multi-circle platform** — one shared app + one shared Postgres DB serving multiple bird count circles (Vancouver live today; Nanaimo/Ladner/Comox to follow), rather than the old one-Cloud-Run-instance-per-circle model.

Working directory is a **git worktree** at `christmas-bird-count-fullhost`, branch `fullhost-paas-migration`, sibling to the original repo (`christmas-bird-count-registration`, stays on `main`/`gcloud-2026-working` — the fallback if this migration needs to be abandoned). Sibling repos `../ladner-cbc` and `../comox-spring` hold last season's forked codebases for those two circles (pre-migration; used this session only to diff for real feature differences before designing the multi-circle schema — see `multi-circle-architecture` memory).

**Read `docs/HOSTING_MIGRATION_PLAN.md` and `REMINDER.md`** for the original Phase 0/1/2 migration history (FullHost node-type investigation, Postgres/SQLAlchemy rewrite decisions) — both are historical/superseded in places now, treat as background, not current status. `docs/TLS_CERT_RENEWAL.md` is current and load-bearing — read it before touching TLS.

## Current live state — this is deployed and working, not just committed

`env-5397859` on FullHost CA West: node `11294` = Apache Python (mod_wsgi) app server, node `11293` = PostgreSQL. The app is **live and being actively used/tested** at:
- `https://vancouver.cbc.birdcount.ca/` — Vancouver's registration page (real registrations exist in the DB from this session's testing)
- `https://cbc.birdcount.ca/` — cross-circle landing page (map + circle list)
- `https://vancouver.cbc.birdcount.ca/bigbird/` — admin console (moved off `/admin` this session)
- `https://cbc.birdcount.ca/bigbird/circles` — super-admin console (create circles, manage circle-admins, edit circle config/area labels)

TLS is valid on both `*.cbc.birdcount.ca` and the bare `cbc.birdcount.ca` (single cert, two SANs), expiring **~2026-11-28** — renewal procedure is in `docs/TLS_CERT_RENEWAL.md`, budget ~80 days from issuance before it's due again.

Whether this environment should now be thought of as "production" or is still informally "test" is genuinely ambiguous — the standing `cbc-test.birdcount.ca` test domain was retired this session in favor of local dev, and real user testing has been happening directly against `vancouver.cbc.birdcount.ca`. Worth clarifying with the user early in the next session if it affects how carefully to tread.

## What's done this session (in order — each is a separate commit on `fullhost-paas-migration`, all pushed)

1. **Deployed the Phase 1+2 Postgres/magic-link rewrite** (already committed at session start as `f15ab30`) — created the `cbc` Postgres role/database via SSH+`psql` (admin user is `webadmin`, not `postgres`), wired `SECRET_KEY`/`SCHEDULER_SECRET`/`DATABASE_URL` via FullHost's Variables panel, ran `alembic upgrade head`.
2. **`521ddb0`** — fixed `area_boundaries.json` path resolution (relative path broke under mod_wsgi's CWD, unlike `flask run`/gunicorn).
3. **`07e4193`** + **`6a5c347`** — designed and built multi-circle architecture: wildcard subdomains (`<slug>.cbc.birdcount.ca`) instead of per-circle domains/deployments, which required attaching a **public IP directly to the app node** (FullHost's dashboard rejects wildcard custom-domain registration, so this bypasses their shared load balancer entirely) and a wildcard Let's Encrypt cert via `certbot` (manual DNS-01, run from **WSL** — native Windows certbot refuses to run without admin rights even in `--manual` mode; **must use `--key-type rsa`**, FullHost's Custom SSL upload form appears to validate key/cert pairing with an RSA-specific check and silently rejects a correctly-matched EC key). `circles`/`circle_areas` tables (migration `0002`) replace `config/organization.py`/`config/areas.py`'s old single-org static constants; `app.py`'s `resolve_circle()` before_request hook resolves the circle from the Host header; every tenant-scoped model auto-resolves `circle_slug` from request context via `resolve_default_circle_slug()`.
4. **`f6c7f7d`** — moved admin panel from `/admin` to `/bigbird` (bot-deterrence); the abandoned `/admin` path now feeds the existing honeypot instead of 404ing.
5. **`4401a9f`** + **`cde4268`** — built the `cbc.birdcount.ca` landing page (Leaflet map + circle table), added `circles.latitude`/`longitude` (migration `0003`) and `circles.circle_name` distinct from `circles.name`/managing-org (migration `0004`), obscured the contact email behind an on-demand `/api/circles/<slug>/contact` endpoint (bots scraping a plaintext contact address caused a real spam problem last year), draws each circle as a 12km-radius circle (official CBC size) rather than a point marker.
6. **`5a4616d`** — fixed a real, pre-existing (not migration-related) bug: CSRF tokens were leaking into the URL bar via the area-leader/scribe info page links.
7. **`bd80bf9`** + **`f3ae31f`** + **`7b3b3e1`** — built per-circle admin/leader role scoping: `circle_admins` table (migration `0005`), `super_admin`/`admin`(now circle-scoped)/`leader`/`public` role tiers, the `/bigbird/circles` super-admin console, landing-host `/bigbird/*` requests redirect to the console, and multi-circle admins get one magic-link email with a separate correctly-scoped link per circle they administer (sessions are deliberately isolated per subdomain — no `SESSION_COOKIE_DOMAIN` sharing, judged more secure against cross-subdomain session-fixation as circle count grows).
8. **`b752ad2`** + **`1a27905`** — fixed several circle-admin-form issues found via live testing: count-date wasn't pre-filling on edit, timezone is now a searchable `<datalist>`, removed the free-text logo-path field, and — importantly — discovered `circles.from_email` was **completely dead code** (every email always used one fixed environment-configured address regardless of circle) and wired it in properly, with server-side validation against a new code-level allowlist (`config/email_settings.py`'s `ALLOWED_FROM_EMAIL_DOMAINS = ['naturevancouver.ca']`) so a site admin can't make outgoing mail impersonate an address outside domains this deployment actually controls, while still allowing the real per-circle variation already in use (`cbc@`, `ladner-cbc@`, `comox-spring-count@naturevancouver.ca`).

**Migrations are at `0005`.** Production should already be caught up through `0005` as of end of session (the user ran `alembic upgrade head` after each schema-changing commit throughout) — **verify this first thing**, don't assume, especially if resuming after any gap.

## Not yet done / open items for next session

1. **KML boundary import** (highest-value next feature) — no map-drawing UI needed. The org already draws circles in Google My Maps, exports KML, and converts it via the existing one-off `utils/parse_area_boundaries.py` script (has `parse_kml_file()` and `calculate_map_center_and_bounds()` — reuse as library functions, don't shell out). Build: a KML-upload route on `/bigbird/circles/<slug>/areas`, storing results in a new `circle_areas.boundary_geojson` JSONB column (not the static per-circle JSON files used today — writing to the app server's filesystem at runtime is fragile on this PaaS, a redeploy or container recreation can silently lose it, as already happened once this migration). This also solves lat/lng for free via the calculated center — no separate map-picker needed. Once built, update `app.py`'s `load_area_boundaries()` and `routes/api.py`'s two boundary-file readers to read from the DB instead of `static/data/area_boundaries_<slug>.json`.
2. **Logo upload** — `logo_path` was removed from the circle-admin form this session (a free-text server path wasn't sound UX or safe). Needs: image bytes stored in the DB (same filesystem-fragility reasoning as boundaries) served via a dedicated route, with file-type and size limits.
3. **Nanaimo/Ladner/Comox circle data entry** — the multi-circle mechanism is fully built; no data has been entered for these three yet. Natural next major workstream once KML import exists (their area boundaries already exist as KML/GeoJSON from last season — check `../ladner-cbc` and `../comox-spring` for what's salvageable).
4. **`tests/installation/*.py`** hardcode `static/data/area_boundaries.json` (pre-rename path) — will need updating for the per-circle filename now, and again once boundaries move to the DB. This suite is still WIP per `CLAUDE.md`, not run automatically (`pytest` isn't even installed in `.venv`).
5. **Task Scheduler** — still completely unconfirmed against the real FullHost dashboard (whether it exists, whether it hits an HTTP URL matching `routes/scheduler.py`'s `SCHEDULER_SECRET` bearer-token design, or does something else). Carried over from the original migration, untouched this session.
6. **Rate limiter** (`config/rate_limits.py`) — still `LIMITER_STORAGE_URL = 'memory://'`, single-instance-only. Deferred, but worth revisiting given the app node now has a public IP attached (horizontal scaling was deliberately left off specifically because of this limiter, per `REMINDER.md` — re-check that's still the case if scaling is ever considered).
7. **`deploy.sh`** still calls `gcloud run deploy` — needs a FullHost-appropriate replacement (git push is being used manually so far).
8. **`CLAUDE.md`** still documents Firestore-era patterns and Cloud Run testing URLs — increasingly stale given how much has changed this session.
9. Firestore → Postgres data migration script for any remaining live Firestore data — not started, low urgency (per original note, minimal live season data).

## Key operational facts (don't re-derive these — they cost real debugging time to establish)

- **SSH**: `ssh -p 3022 <nodeid>-687@gate.vap.fullhost.cloud` — `11294` = app node, `11293` = Postgres node, `687` = account.
- **One-off commands on the app node** (migrations etc.): `cd /var/www/webroot/ROOT && /opt/jelastic-python314/bin/python3 -m alembic upgrade head` — dependencies live at `/opt/jelastic-python314/...` (shared engine-wide install via the git-deploy pipeline), **not** a per-app venv.
- **mod_wsgi only reloads on `wsgi.py`'s own mtime changing** — after `git pull`, either `touch /var/www/webroot/ROOT/wsgi.py` or use the FullHost dashboard restart, or code changes won't take effect.
- **Postgres admin user is `webadmin`**, not `postgres`. Database is named `cbc` (not `cbc_dev` — that's the local-dev-only name from `.env.example`, a real prior incident was `DATABASE_URL` accidentally pointing at the wrong name in production).
- **Local dev**: `FLASK_APP=app.py .venv/Scripts/flask.exe run --host 127.0.0.1 --port 8080` — never `python app.py` directly (circular import between `app.py` and `routes/auth.py`'s `from app import csrf, LANDING_HOST`).
- **Testing authenticated flows locally**: use `app.test_client()`, not raw `curl`/`requests` — `SESSION_COOKIE_SECURE=True` correctly refuses to send the session cookie over plain HTTP, which breaks naive multi-request curl/cookie-jar testing (the cookie appears to be silently dropped) even though the app itself is fine. Also remember Flask-WTF's CSRF protection needs a `Referer` header matching the request's own origin when testing over `https://` base URLs in the test client, or you'll get a confusing "referrer header is missing" 400.
- **`certbot` must run in WSL**, never native Windows, and always with `--key-type rsa` for this specific FullHost form. Full renewal procedure: `docs/TLS_CERT_RENEWAL.md`.

## Key files

- `docs/TLS_CERT_RENEWAL.md` — current, load-bearing, next renewal due ~2026-11 (budget from ~80 days after issuance)
- `docs/HOSTING_MIGRATION_PLAN.md`, `REMINDER.md` — historical migration reasoning, partially superseded
- `models/db.py` — full Postgres schema; `models/circle.py` — `CircleModel`/`CircleAreaModel`/`CircleAdminModel`
- `app.py` — `resolve_circle()` before_request hook (Host-header → circle resolution, landing-host detection)
- `routes/admin.py` — `/bigbird/circles` super-admin console lives here, alongside the original admin routes
- `config/email_settings.py` — `ALLOWED_FROM_EMAIL_DOMAINS` (code-level, not admin-editable — deliberately)
- Auto-memory (`hosting-migration`, `multi-circle-architecture`, `feedback-shell-preference`) should load automatically in a new session and has more granular detail than this file on several of the above.
