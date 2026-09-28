# Test Suite Setup Instructions
{# Updated by Claude AI on 2026-09-08 #}

## Overview

This document covers one-time setup for running the Christmas Bird Count registration test suite locally. The suite is Postgres-native and runs entirely against your local dev server and local Postgres database - it does not depend on any cloud service, OAuth flow, or Firestore, and it must never be pointed at production (see "Production Safety" below).

Two test suites exist:
- **Python (pytest)**: backend/functional/browser tests, `tests/test_*.py`, `tests/unit/`, `tests/installation/`
- **JavaScript (Jest)**: frontend email-validation logic, `tests/email_validation.test.js`

## Prerequisites

- **Python** matching the app's runtime, with the project's own `requirements.txt` already installed
- **PostgreSQL**, running locally, with a dev database migrated to the current schema (`cbc_dev` by convention - see `DATABASE_URL` below)
- **Node.js 18+** (for the Jest suite only)
- **Mozilla Firefox** (primary browser for Selenium tests; system geckodriver is used if present, otherwise `webdriver-manager` downloads and caches one automatically)
- **Google Chrome** (optional secondary browser - supported but Firefox is the default in `tests/test_config.py`)

## Installation Steps

### 1. Install Python test dependencies
```bash
pip install -r tests/requirements.txt
pytest --version
```

### 2. Install JavaScript test dependencies
```bash
cd tests
npm install
npx jest --version
cd ..
```
`node_modules/` lives under `tests/` (not the project root) and is excluded from git.

### 3. Configure environment variables
Copy `.env.example` to `.env` (if you haven't already for regular dev work) and confirm:
```
DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/cbc_dev
TEST_MODE=true
```
`DATABASE_URL`'s host **must** be `localhost`/`127.0.0.1` - the test suite deletes and inserts rows, and refuses to start otherwise (see "Production Safety" below).

### 4. Set up the dedicated test circle's hostname

This is a multi-circle platform: every request resolves its circle from the `Host` header subdomain (see `app.py`'s `resolve_circle()`), and there is deliberately **no default/fallback circle** - code must never guess "Vancouver" for an unspecified circle. Raw `localhost`/`127.0.0.1` has no subdomain to resolve from, so the test suite uses a dedicated circle (slug `test`) reached through a hostname under the IANA-reserved `.test` TLD (RFC 6761), which can never resolve on the real internet even if something bypasses your hosts file.

1. Add to your hosts file (`C:\Windows\System32\drivers\etc\hosts` on Windows, run your editor as Administrator):
   ```
   127.0.0.1 test.cbc.test
   ```
2. Confirm `http://test.cbc.test:8080` loads once the dev server (step 5) is running.

### 5. Start the local dev server
```bash
python app.py  # or: flask run --host 127.0.0.1 --port 8080
```
The server must be running in a separate process before browser/API tests execute - pytest does not start it for you. Make sure `TEST_MODE=true` is set in **that** process's environment too (it's a separate process from pytest, so setting it only in your shell for pytest isn't enough) - this redirects all outgoing email (including magic-link logins) to the configured `test_recipient` instead of a real participant, and raises rate limits (see "Rate Limiting" below).

### 6. Create the test circle and import its area boundaries
The test circle (`test`) and its 25 areas (a copy of Vancouver's areas, geographically shifted 45km northeast so they don't overlap any real circle) need to exist in your local Postgres before most tests can run:
1. Log in to `/bigbird` as a test admin and use the circle-management UI to create a circle with slug `test`, or use the equivalent admin API/console route directly.
2. Import `utils/Test_CBC_Areas.kml` via the circle's area-import UI (`/bigbird/circles/test/areas`).

### 7. Verify the setup
```bash
pytest tests/unit/ -v          # No server/browser required
pytest tests/ --collect-only   # Confirms all test files import cleanly
cd tests && npm run test:email-validation && cd ..
```

## Production Safety

`tests/conftest.py`'s `pytest_sessionstart` hook runs before any fixture or test and hard-aborts the whole run (`pytest.exit`, nonzero exit code) unless:
- `DATABASE_URL`'s host is `localhost`/`127.0.0.1`.
- The resolved Selenium/API target (`tests.test_config.get_base_url()`) **and** `config.cloud.TEST_BASE_URL` both resolve to `localhost`/`127.0.0.1` or a `.test` hostname.

This is a structural guard, not just convention: production Postgres lives on a separate host reachable only by SSH, so a legitimate local run's `DATABASE_URL` host can never legitimately be anything else - even if the suite were somehow launched from a production app server. There is no environment variable or flag to bypass this; if you need to test against a real remote host, that is a deliberate, separate decision outside this guard's scope.

## Test Accounts

Auth is magic-link (signed session cookie) based, not Google OAuth - there are no passwords or OAuth client credentials to configure for testing. `tests/utils/auth_utils.py`'s `login_as_test_user()`/`admin_login_for_test()` establish a session by directly injecting a validly-signed session cookie for a test account, without sending or clicking a real magic-link email.

Test account emails are defined in `config/admins.py`:
- `TEST_ADMIN_EMAILS` - auto-added to the admin whitelist whenever `config/admins.py`'s `is_test_environment()` is true (`TEST_MODE=true` or `FLASK_ENV=development`)
- `TEST_LEADER_EMAILS` - used for area-leader workflow tests

## Rate Limiting

`config/rate_limits.py` bumps limits under `TEST_MODE=true` (both `registration` and `auth` scale up to 100/minute) since a real public deployment is very unlikely to also run in test mode. If you see `429 Too Many Requests` during a test run, confirm the dev server process actually has `TEST_MODE=true` set - the rate limiter runs in the Flask process, not in pytest.

## Email Volume

Real SMTP sends go through SMTP2GO. Registration/reassignment-driving tests send real email (redirected to `test_recipient` under `TEST_MODE=true`); a full suite run sends on the order of a few dozen emails. If you're on SMTP2GO's free tier (throttled after a small daily cap, ~25/hour), watch cumulative send volume across a day of iterative test runs against that cap.

## Troubleshooting

**`Refusing to run: DATABASE_URL host '...' is not localhost/127.0.0.1`**
`.env`'s `DATABASE_URL` points somewhere other than your local Postgres. Fix `.env`, not the guard.

**`Bad Request: Could not determine which count circle this request is for`**
The hostname you navigated to doesn't match a `circle_slug` pattern in `app.py`'s `CIRCLE_SUBDOMAIN_PATTERNS`, or the hosts-file entry (step 4) is missing/wrong.

**Browser tests fail with a silent "not authenticated" redirect**
Usually a stale `session` cookie from a previous manual login colliding with the injected test cookie. `login_as_test_user()` already deletes any existing `session` cookie before injecting - if you're writing new auth-setup code, never call `driver.add_cookie()` with an explicit `domain` key (even one matching the current host exactly forces a leading-dot domain cookie in geckodriver/chromedriver, distinct from Flask's own host-only cookie, and the browser then sends both).

**`WebDriverException: geckodriver executable issues`**
Install Firefox, or let `webdriver-manager` download a driver automatically (first run only; cached for 30 days after).

**Tests reference data that isn't there**
Most functional tests expect the `test` circle and its areas (step 6) to already exist. `clean_database`/`populated_database` fixtures manage participant rows per-test; they do not create the circle or its areas.

## Test Directory Structure
```
tests/
├── conftest.py                 # Pytest fixtures, production-safety guard
├── test_config.py              # TEST_CONFIG, TEST_CIRCLE_SLUG, TEST_ACCOUNTS
├── requirements.txt            # Python test dependencies
├── package.json                # Jest configuration
├── fixtures/                   # CSV test data (test_participants_2025.csv)
├── data/                       # Test scenario definitions
├── utils/                      # auth_utils, database_utils, identity_utils, load_test_data
├── page_objects/               # Selenium page object model
├── unit/                       # Model/UI-conformance unit tests (no server needed)
├── installation/               # Portable, config-driven installation checks
├── test_*.py                   # Functional/integration test modules
└── email_validation.test.js    # Jest frontend validation tests
```

See `docs/TESTING.md` for how to run and select tests, and `docs/TEST_SUITE_SPEC.md` for what each test file/fixture covers.
