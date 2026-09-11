# Test Suite Specification
{# Updated by Claude AI on 2026-09-08 #}

What each part of the test suite covers. For setup, see `docs/TEST_SETUP.md`; for running tests, see `docs/TESTING.md`. Coverage tooling/targets are intentionally out of scope for this document.

## Scope and Non-Goals

All tests run against a local dev server (`http://test.cbc.test:8080`) and local Postgres, targeting a dedicated `test` circle - never a real circle's data, never a remote host. `tests/conftest.py`'s `pytest_sessionstart` guard enforces this structurally (see `docs/TEST_SETUP.md`).

## Core Fixtures (`tests/conftest.py`)

- **`db_session`** (session-scoped): the app's real SQLAlchemy session (Postgres).
- **`clean_database`** (function-scoped): deletes `Participant`/`RemovalLog` rows for the `test` circle, for both the current year and the isolation year (2000), before yielding. Most tests that mutate data depend on this directly or indirectly.
- **`populated_database`** (class-scoped): loads `tests/fixtures/test_participants_2025.csv` into Postgres via `tests/utils/load_test_data.py`'s `load_participants_to_postgres()`, for the `test` circle/current year; cleans up after the class.
- **`identity_test_database`** / **`single_identity_test`**: built on `clean_database`, pre-populate family-email scenarios via `tests/utils/identity_utils.py`'s `IdentityTestHelper` for identity/synchronization testing.
- **`browser`** (function-scoped) / **`authenticated_browser`** (session-scoped): Selenium WebDriver instances. `authenticated_browser` logs in once per session via a directly-injected session cookie (`tests/utils/auth_utils.py`) rather than a real magic-link email.
- **`base_url`**: resolves to the local test target (`tests.test_config.get_base_url()`).
- **`second_test_circle`** (function-scoped): a second, lightweight circle (`TEST_CIRCLE_SLUG_2 = 'test2'`, `tests/test_config.py`) for proving cross-circle isolation, not just that `TEST_CIRCLE_SLUG` itself works. Field values (`name`/`count_event_name`/`count_contact`/`is_cbc`/`display_timezone`) are deliberately distinct from both Vancouver's module constants and `TEST_CIRCLE_SLUG`'s own row, so a test asserting on these can catch cross-circle bleed-through. Label-only - no KML/area boundaries. Wipes everything scoped to `circle_slug='test2'` (the circle row plus any `Participant`/`RemovalLog`/`ReassignmentLog`/`WithdrawalLog`/`CircleArea`/`CircleAdmin`/`EmailTimestamp`/`EmailContentOverride` rows a test created) both before and after, via `tests/conftest.py`'s `_wipe_test_circle_2_data()`.

Auto-applied markers (`pytest_collection_modifyitems`): `critical` (node ID contains registration/auth/data_consistency/identity_synchronization), `admin` (node ID or name contains "admin"), `slow` (name contains large/export/concurrent/performance), `identity` (node ID contains identity/family_email).

## Test Data

- `tests/fixtures/test_participants_2025.csv` - realistic participant dataset (Vancouver-shaped area codes), loaded by `populated_database`. A stale `scribe`-role column from a since-removed feature is ignored on load.
- `tests/data/test_scenarios.py` - programmatically generated registration scenarios (regular/leadership-interested/skill-level variations, family groupings) used by workflow tests instead of hand-written fixtures per test.
- `tests/data/test_accounts.py` - test account/role definitions consumed by `tests/test_config.py`'s `TEST_ACCOUNTS`.
- `utils/Test_CBC_Areas.kml` - the `test` circle's 25 areas: a copy of Vancouver's real area boundaries, translated 45km northeast so they don't overlap any real circle (including the real Sechelt circle, which an earlier northwest translation did overlap).

## Unit Tests (`tests/unit/`)

No server or browser required. `tests/unit/conftest.py` provides shared `app`/`client`/`admin_client`/`super_admin_client` fixtures - see its own docstring/comments for two non-obvious gotchas worth knowing before adding a new file here: (1) `admin_client` is backed by a real (temporary) `circle_admins` row rather than a hardcoded session role, since `app.py`'s `before_request` recomputes `session['user_role']` from the email on every request, and (2) Flask-Limiter's rate limiting is disabled once, at conftest-import time, via `limiter.enabled = False` (the `services.limiter` singleton) - `app.config['RATELIMIT_ENABLED'] = False` does NOT work, since Flask-Limiter reads that flag once at `init_app()` time (already run during `import app`, before any fixture executes), not per-request. Without this, enough `tests/unit/` files hitting admin routes in one run exhausts a route's real per-minute budget partway through collection (state is shared process-wide via the `memory://` storage - see `config/rate_limits.py`), 429ing whichever unrelated test happens to run later.
- **`test_participant_model.py`** / **`test_removal_log_model.py`**: `ParticipantModel`/`RemovalLog` behavior directly against Postgres.
- **`test_ui_conformance.py`**: Flask test-client checks against templates/routes (required fields, checkbox presence, historical-year warning banner) using a real Flask app instance with `SERVER_NAME` set to the test circle's hostname.
- **`test_circle_resolution.py`**: `app.py`'s `resolve_circle()` - the Host-header-based routing the whole multi-circle platform depends on. An unresolvable host (raw IP, bare hostname, wrong-TLD-shaped domain) 400s rather than silently falling back to any circle's data (the single most important case - there is no default circle); a host matching a known pattern but naming no real circle 404s; the two landing hosts (`cbc.birdcount.ca`/`birdcount.ca`) resolve with `g.circle_slug is None` and the right `is_landing_host`/`is_apex_landing_host` combination; `routes/admin.py`'s `CIRCLE_CONSOLE_ENDPOINTS` stay reachable from a non-circle host (landing or even unresolvable) without tripping the 400 path, while a non-console admin route still 400s from the same host; both CBC and non-CBC subdomain levels resolve the same slug, case-insensitively.
- **`test_multi_circle_isolation.py`**: with `TEST_CIRCLE_SLUG` and `TEST_CIRCLE_SLUG_2` both populated (via `second_test_circle`), proves circle_slug scoping actually isolates data rather than just working for the one circle every other test exercises - `ParticipantModel` queries, the real `/bigbird/export_csv` route (end-to-end, not just the model), and `CircleAreaModel.get_boundary_data()` (both circles given an area under the *same* code, to prove that doesn't collide) never leak one circle's rows into the other's; and `routes/auth.py`'s `get_user_role()` resolves a `circle_admins` row to `'admin'` only for that email's own circle (not the other), while a global super-admin resolves to `'super_admin'` under both - the sharpest test of the single-table `circle_admins` design.
- **`test_organization_variables.py`**: `config/organization.py`'s `get_organization_variables()`/`_circle_value()` - resolved to `TEST_CIRCLE_SLUG_2` inside a request context, values match that circle's own DB row, not Vancouver's module constants or `TEST_CIRCLE_SLUG`'s row; outside any request context (a script) or on the landing host (`g.circle` is `None`), values fall back to the Vancouver module constants - documented *current* behavior, not a bug to fix here, but pinned since it's exactly the mechanism behind the known cross-circle magic-link-subject bug (a regression guard for that eventual fix, for free).
- **`test_scheduler_multi_circle.py`**: `routes/scheduler.py`'s `_run_for_every_circle()`, using a fake generator function (not the real digest generators, so this stays fast and doesn't touch real circles' data) - called once per circle including both test circles (`CircleModel.get_all()` returns every circle in the local DB, so assertions check both test circles were included, not that they were the *only* ones processed); one circle's generator raising is caught and attributed to that circle's own `errors` entry without blocking or losing the other circle's results.
- **`tests/test_natural_sorting.py`**, **`tests/test_email_validation.py`**: pure-function tests (`models/area_signup_type.py`'s `natural_sort_key()`, `services/security.py`'s `validate_email_format()`).
- **`test_email_content.py`**: the per-circle customizable email content feature (`EMAIL_CUSTOMIZATION_PLAN.txt` Stage 1) - placeholder substitution safety (`services/email_content_service.py`, including that malicious-looking `${...}` text can never execute), `sanitize_email_content()`, `EmailContentModel`'s 3-tier resolution (circle override → super-admin default → hardcoded fallback) and cross-circle isolation, and the `/bigbird/circles/<slug>/email-content` + `/bigbird/email-content/defaults` admin routes' access control (a circle-admin can manage only their own circle; a super-admin can manage any circle; `/defaults` is super-admin only) and save/reset behavior (an out-of-whitelist placeholder rejects the whole save, nothing partially persisted). Uses `tests/unit/conftest.py`'s `app`/`client`/`admin_client`/`super_admin_client` fixtures - `admin_client` is backed by a real (temporary) `circle_admins` row rather than a hardcoded session role, since `app.py`'s `before_request` recomputes `session['user_role']` from the email on every request.
- **`test_digest_email_content.py`**: Stage 2 of the same feature - the three Task-Scheduler-driven digest emails (`team_update`/`weekly_summary`/`admin_digest`) becoming admin-customizable. Block registry contents for the three types (and that their subject fallback text no longer hardcodes "Vancouver" - `test/email_generator.py`'s old `EMAIL_SUBJECTS` dict did, unconditionally, regardless of which circle), the three preview routes, a saved override actually reaching the rendered preview per type, per-area `$date`/`$area_code` subject substitution (team_update/weekly_summary send one email per area, so the subject is resolved once per circle but substituted fresh per area), and the admin_digest recipients fix (now the union of that circle's own `circle_admins` and the global `ADMIN_EMAILS` whitelist, not just the global list) verified against a real `generate_admin_digest_email()` call with `email_service.send_email` mocked to capture recipients instead of sending.
- **`test_concurrency_audit_fixes.py`**: fixes from a concurrency/transaction-safety code audit. Historical-year writes now rejected server-side, not just UI-hidden (`delete_participant`/`withdraw_participant`/`edit_participant` all tested with a past `year`, confirming no DB change, plus a current-year write still succeeding as the negative control); `delete_participant` is now one atomic transaction (delete + `log_removal` + leader deactivation) rather than several separately-committed steps - tested both the success path (removal logged) and, by mocking `deactivate_leaders_by_identity` to raise, that a mid-operation failure rolls back the *entire* transaction (the participant is still there, `is_leader` still `True`, no removal-log entry) rather than leaving a deleted participant with no log entry; magic-link token redemption is now an atomic `UPDATE ... WHERE used_at IS NULL` (was read-then-write) - tested that a second redemption of the same token is rejected with "already been used" rather than silently succeeding a second time.
- **`test_circle_admin_permissions.py`**: circle-admin self-service editing of their own circle's config via `admin.edit_circle` (`routes/admin.py`'s `SUPER_ADMIN_ONLY_CIRCLE_FIELDS`). Access control (a circle-admin can reach only their own circle - by URL slug, for both GET and POST - a super-admin any circle); the three locked fields (`test_recipient`, `latitude`, `longitude`) render `disabled` with a "Super-admin only" badge for a circle-admin and fully editable for a super-admin; and - the real point of the feature - a circle-admin's POST changes every other field but a crafted POST that also includes the three locked fields leaves them untouched (enforced server-side against `circle.get(field)`, not just via the disabled UI attribute), while a super-admin's POST can change all three. Mutating tests use a `restore_test_circle` fixture (snapshot/restore via `CircleModel`) so `TEST_CIRCLE_SLUG`'s shared config isn't permanently altered by the suite.

## Installation Tests (`tests/installation/`)

Portable, configuration-driven checks intended to validate any deployment of this app (not hardcoded to Vancouver specifics beyond the dedicated test circle's own config).
- **`test_configuration.py`**: area codes/boundaries are internally consistent, base-URL/domain configuration is sane.
- **`test_core_functionality.py`**: the app is reachable, admin dashboard loads under authentication.
- **`test_deployment.py`**: live `/api/areas` matches the DB-backed boundary data directly (`models/circle.py`'s `CircleAreaModel.get_boundary_data()`).

Its `conftest.py` provides `installation_config`/`area_boundaries_data`/`configured_areas`/`public_areas`/`org_config`, all resolved for `TEST_CIRCLE_SLUG` via direct model calls (not through a request context, since these run as plain pytest setup).

## Functional/Integration Tests (`tests/test_*.py`)

**Registration**
- `test_registration_workflows.py` - registration form workflows per participant type, form validation, data preservation during navigation.
- `test_family_email_scenarios.py` - multiple family members sharing one email address; identity-based (not email-only) deduplication.
- `test_email_validation_integration.py` - browser + direct-API email validation, including admin-side and security cases (malformed/oversized input).
- `test_basic_regression_check.py`, `test_single_table_regression.py` - regression coverage for the single-table participant/leadership design (no separate `area_leaders` collection - leadership is `is_leader`/`assigned_area_leader` flags on the participant row).

**Admin**
- `test_admin_core_functionality.py` - minimal smoke tests for critical admin operations (auth, dashboard access).
- `test_admin_dashboard_workflows.py` - dashboard auth/access control, data access, workflow transitions.
- `test_admin_participant_management.py` - viewing, editing, and leadership-flag operations on participants.
- `test_admin_leaders_sorting.py` / `test_admin_leaders_backend_sorting.py` - area-leader list sort order, including natural (non-lexicographic) sorting of area codes.
- `test_leader_area_assignment_bug.py` - regression coverage for a specific leader/area assignment bug.
- `test_csv_export_workflows.py` - CSV export correctness (headers, sort order, content) via real browser downloads.

**Reassignment and Email**
- `test_participant_reassignment.py` - participant/leader area-reassignment workflows against CSV-loaded data.
- `test_reassignment_email_notifications.py` - reassignment-triggered emails, using a mocked `email_service.send_email` (`EmailCapture`) so no real SMTP send occurs; drives `test/email_generator.py`'s digest generators directly with an explicit circle.

## Page Objects (`tests/page_objects/`)

Selenium page-object model: `base_page.py` (shared waits/scroll-into-view/click helpers), `registration_page.py`, `admin_dashboard_page.py`, `admin_participants_page.py`. Test files interact with these rather than raw Selenium locators.

## Test Utilities (`tests/utils/`)

- **`auth_utils.py`** - `login_as_test_user()`/`admin_login_for_test()`: session-cookie injection auth. Deletes any pre-existing `session` cookie first and never sets an explicit cookie `domain` (doing so causes a duplicate leading-dot-domain cookie in Selenium's browser, which silently breaks auth).
- **`database_utils.py`** - `DatabaseManager`/`create_database_manager()`: row counts, consistency checks, and collection-clearing helpers against Postgres, scoped by `circle_slug`.
- **`identity_utils.py`** - `IdentityTestHelper`: family-scenario creation, identity-based lookup, and cleanup, built on `ParticipantModel`.
- **`load_test_data.py`** - CSV parsing (`load_csv_participants`) and Postgres loading (`load_participants_to_postgres`, `load_test_fixture`) for the `populated_database` fixture and any test file that loads its own dataset.
- **`reassignment_helper.py`** - shared setup for reassignment-workflow tests.

## JavaScript Tests

- `tests/email_validation.test.js` (Jest) - frontend email-validation logic, mirroring `test_email_validation.py`'s backend cases so both layers reject/accept the same inputs (RFC 5322 compliance plus this app's stricter rejection of `%`/`!`).

## Known Gaps

- No automated coverage reporting is wired up yet (deliberately out of scope for this document).
- `download_coverage_after_tests` in `tests/conftest.py` documents a manual coverage-download step rather than an automated one.
