# Code Coverage Guide
Updated by Claude AI on 2025-10-11

## Overview

This project uses code coverage measurement for both Python (backend) and JavaScript (frontend) code to track which parts of the codebase are exercised by tests.

## Coverage Tools

- **Python**: `coverage.py` with `pytest-cov` integration
- **JavaScript**: Jest built-in coverage (Istanbul)

## Python Coverage (Server-Side)

**Note: All Python test commands should be run from the project root directory.**

### Measuring Coverage from Selenium Tests

Since Selenium tests execute code on the remote Cloud Run server, coverage measurement requires special instrumentation:

#### 1. Deploy Test Server with Coverage Enabled

```bash
./deploy.sh test --coverage
```

The `--coverage` flag enables coverage measurement on the test server only. This triggers:
- Coverage instrumentation in `app.py`
- Coverage data collection to `/tmp/.coverage` on server
- Coverage endpoints at `/test/coverage/*` (test mode only)

**Important Notes:**
- Coverage is **never** enabled on production, even with `--coverage` flag
- The flag works with `test` or `both` deployment targets
- Default behavior (no flag) disables coverage for faster execution

#### 2. Run Your Selenium Tests

```bash
pytest tests/test_participant_reassignment.py
```

Coverage data accumulates on the server as tests execute routes and business logic.

#### 3. Download Coverage Data

After tests complete, download the server coverage file from the test server:

**Manual Download (Current Method):**
1. Open your browser and navigate to `https://cbc-test.naturevancouver.ca/admin` (log in if needed)
2. Once authenticated, visit `https://cbc-test.naturevancouver.ca/test/coverage/save`
3. The coverage file will automatically download as `.coverage.server`
4. Move the downloaded file to your project root directory

**How it works:**
- The `/test/coverage/save` endpoint stops coverage measurement and sends the coverage data file
- This endpoint requires admin authentication and is only available when `TEST_MODE=true`
- The file downloads with the name `.coverage.server` automatically

**Future Enhancement:**
- Automated download via `download_coverage_after_tests()` fixture in `conftest.py` is planned
- Currently requires manual browser download due to session transfer complexity between Selenium and requests library

#### 4. Merge Coverage Data

If you have local unit tests with coverage:

```bash
coverage combine .coverage .coverage.server
```

Otherwise, just use the server coverage:

```bash
mv .coverage.server .coverage
```

#### 5. Generate Reports

```bash
# Terminal summary
coverage report

# HTML report (detailed, recommended)
coverage html

# Open in browser
start htmlcov/index.html  # Windows
open htmlcov/index.html   # macOS
```

#### 6. Redeploy Without Coverage

Once you've collected coverage data, redeploy normally:

```bash
./deploy.sh test
```

This disables coverage measurement for faster test execution.

### Coverage Configuration

Coverage behavior is controlled by `.coveragerc`:

**Included:**
- `routes/` - Flask route handlers
- `models/` - Database models
- `services/` - Business logic
- `config/` - Configuration modules

**Excluded:**
- `tests/` - Test files
- `utils/` - Development utilities (not deployed)
- `*.pyc`, `__pycache__/` - Compiled Python
- Deployment files (`deploy.sh`, `Dockerfile`, etc.)

**Branch Coverage:**
Enabled - measures both line execution and conditional branch paths.

### Local Unit Test Coverage

For unit tests that don't require Selenium:

```bash
pytest --cov=. --cov-report=html --cov-report=term tests/test_email_validation.py
```

This measures coverage from Python unit tests running locally.

## JavaScript Coverage (Client-Side)

### Running Jest with Coverage

```bash
cd tests

# All Jest tests with coverage
npm run test:coverage

# Email validation tests only
npm run test:coverage:email
```

### Coverage Configuration

Jest coverage is configured in `tests/package.json`:

**Included:**
- `static/js/validation.js` - Form validation (90% threshold)

**Excluded (no tests yet):**
- `static/js/map.js` - Leaflet map functionality
- `static/js/leaders-map.js` - Leaders map
- `static/js/registration.js` - Registration form

**Thresholds:**
- Global: 50% statements/branches/functions/lines
- `validation.js`: 90% (has dedicated test suite)

### Viewing JavaScript Coverage

After running with coverage:

```bash
# Terminal summary is shown automatically

# Open HTML report
cd tests
start coverage/lcov-report/index.html  # Windows
open coverage/lcov-report/index.html   # macOS
```

## Coverage Workflow Summary

### Complete Selenium Test Coverage Run

```bash
# 1. Deploy with coverage
./deploy.sh test --coverage

# 2. Verify coverage is enabled (optional)
# Visit https://cbc-test.naturevancouver.ca/test/coverage/status
# Should return: {"enabled": true, "data_file": "/tmp/.coverage"}

# 3. Run tests
pytest tests/test_participant_reassignment.py

# 4. Download coverage (manual step)
# Visit https://cbc-test.naturevancouver.ca/test/coverage/save
# Save as .coverage.server in project root

# 5. Generate report
coverage report
coverage html
start htmlcov/index.html

# 6. Redeploy without coverage
./deploy.sh test
```

### JavaScript-Only Coverage

```bash
cd tests
npm run test:coverage
start coverage/lcov-report/index.html
```

### Combined Coverage (Future)

When local Python unit tests exist:

```bash
# Python unit tests
pytest --cov=. --cov-report=html tests/test_security.py

# Download server coverage
# (manual step - save as .coverage.server in project root)

# Merge
coverage combine .coverage .coverage.server

# Generate combined report
coverage html

# JavaScript tests
cd tests
npm run test:coverage
```

## Security Notes

### Coverage Endpoints

Coverage endpoints are **test server only**:
- Only enabled when `TEST_MODE=true` AND `ENABLE_COVERAGE=true`
- Require admin authentication
- Never exposed in production (protected by dual env var check)

### Coverage Package in Production

The `coverage` package is installed in production (listed in `requirements.txt`) but:
- Never activated (requires both env vars)
- No performance impact when not running
- No endpoints registered without `TEST_MODE=true`
- Follows same security pattern as test email triggers

## Coverage Goals

### Current Targets

**Python:**
- `services/security.py`: 90%+ (email validation tests)
- `models/`: 60%+ (CRUD operations tested via Selenium)
- `routes/`: 40%+ (admin workflows covered)
- Overall: 50%+

**JavaScript:**
- `validation.js`: 90%+ (dedicated Jest tests)
- `registration.js`: 0% (future: form interaction tests)
- `map.js`, `leaders-map.js`: 0% (future: map component tests)

### Future Enhancements

1. **Automated coverage download** - Eliminate manual step 3
2. **Integration tests** - Use Flask test client for route coverage without Selenium
3. **Frontend component tests** - Add Jest tests for map and registration UIs
4. **CI integration** - Automated coverage reporting on commits
5. **Coverage badges** - Display current coverage in README

## Troubleshooting

### Coverage Not Enabled on Server

**Symptom:** `/test/coverage/status` returns `{"enabled": false}`

**Solution:**
- Ensure deployment used `./deploy.sh test --coverage` (not just `./deploy.sh test`)
- Check deployment output for: `⚠️  Coverage measurement ENABLED for test server`
- Check server logs: `gcloud run services logs read cbc-test --region=us-west1 | grep -i coverage`
- Look for "Coverage measurement started" in logs
- Verify you're checking the test server, not production (coverage never enabled on production)

### Coverage File Not Found

**Symptom:** `/test/coverage/save` returns error

**Solution:**
- Run at least one test to generate coverage data
- Coverage starts when app.py loads, saves on endpoint hit

### Low Coverage Numbers

**Expected:** Selenium tests measure server-side code only
- Template rendering not measured
- JavaScript execution not measured (use Jest for that)
- Only Python routes, models, services counted

## File Locations

- **Configuration:** `.coveragerc` (project root)
- **Python reports:** `htmlcov/` (project root)
- **JavaScript reports:** `tests/coverage/`
- **Server coverage data:** `/tmp/.coverage` (on Cloud Run)
- **Downloaded coverage:** `.coverage.server` (project root after download)

## References

- [Coverage.py documentation](https://coverage.readthedocs.io/)
- [Jest coverage documentation](https://jestjs.io/docs/configuration#collectcoverage-boolean)
- [pytest-cov documentation](https://pytest-cov.readthedocs.io/)
