# Running the Test Suite
{# Updated by Claude AI on 2026-09-08 #}

For one-time setup (hosts file, test circle, dependencies), see `docs/TEST_SETUP.md` first. This document covers day-to-day test execution. See `docs/TEST_SUITE_SPEC.md` for what each test file/fixture actually covers.

## Before Every Run

1. Local Postgres is running and `DATABASE_URL` in `.env` points at it (`localhost`/`127.0.0.1` - the suite refuses to start otherwise).
2. The dev server is running in its own process with `TEST_MODE=true` set: `python app.py`.
3. `test.cbc.test` resolves via your hosts file (see `docs/TEST_SETUP.md`).

Unit tests (`tests/unit/`) don't need steps 2-3; everything else does.

## Running Tests

```bash
# Everything
pytest tests/ -v

# One file
pytest tests/test_registration_workflows.py -v

# One test
pytest tests/test_registration_workflows.py::TestRegistration::test_basic_registration -v

# Unit tests only (fast, no server/browser)
pytest tests/unit/ -v

# JavaScript email-validation tests
cd tests && npm run test:email-validation && cd ..
```

An HTML report is written to `reports/test_report.html` after every run (`pytest.ini`'s `addopts`).

## Selecting Tests by Marker

Markers are defined in `pytest.ini` and some are also auto-applied by `tests/conftest.py`'s `pytest_collection_modifyitems` based on test name/location (e.g. anything with "registration", "auth", "identity" in its node ID picks up `critical`/`identity` automatically - you don't need to tag those by hand).

```bash
pytest -m registration -v      # Registration workflow tests
pytest -m admin -v             # Admin interface tests
pytest -m critical -v          # Critical-path tests (registration, admin dashboard, CSV export)
pytest -m identity -v          # Family-email / identity-based matching tests
pytest -m "browser" -v         # Selenium-driven tests
pytest -m "api" -v             # Direct HTTP/requests-based tests (no browser)
pytest -m "not slow" -v        # Skip slow tests for a quick pass
```

Full marker list: `pytest --markers`.

## Debugging a Failing Test

```bash
# See the browser instead of running headless
# (tests/test_config.py's TEST_CONFIG['headless'] - flip to False)

# Verbose logging
pytest tests/test_registration_workflows.py -v --log-cli-level=DEBUG

# Stop at first failure
pytest tests/ -x

# Re-run only what failed last time
pytest tests/ --lf
```

Since fixtures like `clean_database` wipe and reload rows for the `test` circle's current/isolation years on every run, a failing test's leftover data doesn't need manual cleanup between attempts - re-running the same test starts from a clean slate.

## Rate Limiting

If a run trips `429 Too Many Requests`, the dev server process doesn't actually have `TEST_MODE=true` set (rate limits are bumped to 100/minute under test mode - see `config/rate_limits.py`). Confirm in the server process's own environment, not just your pytest shell.

## Email Volume

Registration/reassignment-driving tests send real email via SMTP2GO (redirected to `test_recipient` under `TEST_MODE=true`, never to a real participant). A full suite run sends on the order of a few dozen emails - keep an eye on cumulative volume across a day of runs if you're on a throttled/free SMTP2GO tier.

## What NOT to Do

- Never set `TEST_TARGET=production` or point `DATABASE_URL` at anything but your local Postgres. `tests/conftest.py`'s `pytest_sessionstart` guard refuses to start the run at all if it detects this, but don't rely on the guard as your only safety check - it exists as a backstop, not a feature to test against.
- Never run the suite against the `vancouver` circle's real data. All fixtures target `TEST_CIRCLE_SLUG` (`'test'`, defined in `tests/test_config.py`) specifically because there is no default/fallback circle in this app - tests must always pass a circle explicitly.
