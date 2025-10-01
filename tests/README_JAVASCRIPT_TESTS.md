# JavaScript Test Suite

## Overview

This directory contains JavaScript unit tests that run locally using Jest without requiring a server. These tests complement the Python test suite and ensure validation consistency between frontend and backend.

## Test Files

- **email_validation.test.js** - 81 tests for `static/js/validation.js::validateEmailFormat()`
  - Mirrors the Python test suite in `test_email_validation.py`
  - Validates RFC 5322 compliance with security restrictions
  - Tests plus sign support, length limits, and edge cases

## Installation

**One-time setup** (from the `tests/` directory):

```bash
cd tests
npm install
```

This installs Jest and dependencies in `tests/node_modules/` (not in project root).

## Running Tests

From the `tests/` directory:

```bash
# Run email validation tests
npm run test:email-validation

# Run with verbose output
npm run test:email-validation:verbose

# Or run Jest directly
npx jest email_validation.test.js
```

## Test Results

All 81 tests should pass, confirming that the JavaScript validation matches the Python backend validation exactly.

Example output:
```
Test Suites: 1 passed, 1 total
Tests:       81 passed, 81 total
Time:        0.494 s
```

## Test Coverage

The test suite validates:
- **Valid emails** (17 tests): Standard formats, plus signs, complex patterns
- **Invalid emails** (23 tests): Malformed addresses, invalid characters
- **Length limits** (6 tests): Local part (64), domain (255), total (254)
- **Plus sign support** (5 tests): Various positions in local part
- **TLD requirements** (5 tests): Minimum 2 characters, proper format
- **Subdomain support** (3 tests): Single and multi-level subdomains
- **Edge cases** (5 tests): Single characters, all numbers, special combinations
- **Security restrictions** (6 tests): Percent signs and exclamation marks rejected
- **Real-world patterns** (10 tests): Gmail, Outlook, Yahoo, corporate, educational
- **User-reported cases** (1 test): Specific bug report validation

## Consistency with Python Tests

The JavaScript test suite uses the same test cases as `test_email_validation.py` to ensure:
- Frontend validation matches backend validation exactly
- No discrepancies between user-facing validation and server-side validation
- Changes to validation rules are tested in both environments

## Adding New Tests

To add new test cases:

1. Edit `email_validation.test.js`
2. Add test cases in the appropriate `describe` block
3. Use Jest's `test()` or `test.each()` for parameterized tests
4. Run tests to verify: `npm run test:email-validation`
5. Add equivalent tests to `test_email_validation.py` for consistency

## Deployment Notes

**Important**: The `tests/` directory with `node_modules/` should **NOT** be deployed to production servers.

- Tests are for local development only
- The `.gcloudignore` file should exclude `tests/` directory
- Only `static/js/validation.js` is deployed for production use

## Further Reading

- Jest Documentation: https://jestjs.io/
- Email Validation Specification: See `EMAIL_SPEC.md` (project root)
- Python Test Suite: See `test_email_validation.py` (this directory)
