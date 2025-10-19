# Test Suite Setup Instructions
{# Updated by Claude AI on 2025-10-19 #}

## Overview

This document provides complete setup instructions for the Christmas Bird Count registration system test suite. The test suite includes both Python (pytest) and JavaScript (Jest) tests that validate backend and frontend functionality.

**Prerequisites**: Before running tests, complete the initial project configuration as described in `DEPLOYMENT.md`. This includes:
- Google Cloud project setup and authentication
- OAuth client configuration
- Firestore database creation and indexes
- Cloud Run deployment to test environment

All test types (installation tests, functional tests, unit tests) use the same configuration. This document covers test-specific setup only.

## Prerequisites

### System Requirements
- **Operating System**: Windows 11 (development environment)
- **Python**: 3.8 or higher
- **Node.js**: 18.x or higher (for JavaScript tests)
- **Mozilla Firefox**: Latest version installed (primary browser for OAuth stability)
- **Google Chrome**: Optional secondary browser (has OAuth stability issues)
- **Git**: For version control
- **Google Cloud SDK**: For accessing Secret Manager and Firestore

### Google Cloud Access
- **Project**: `vancouver-cbc-registration`
- **Authentication**: Service account or user account with appropriate permissions
- **Required Permissions**:
  - `secretmanager.secretAccessor` (to retrieve test credentials)
  - Firestore read/write access to `cbc-test` and `cbc-register` databases
  - Cloud Run viewer permissions (for monitoring test environments)

## Installation Steps

### 1. Clone and Navigate to Project
```bash
cd C:\AndroidStudioProjects\christmas-bird-count-registration
```

### 2. Install Python Test Dependencies
```bash
# Install test-specific requirements
pip install -r tests/requirements.txt

# Verify pytest installation
pytest --version
```

### 3. Install JavaScript Test Dependencies
```bash
# Navigate to tests directory
cd tests

# Install Jest and dependencies
npm install

# Verify Jest installation
npx jest --version

# Navigate back to project root
cd ..
```

**JavaScript Test Notes:**
- Node.js 18.x or higher required
- Dependencies installed in `tests/node_modules/` (not project root)
- `node_modules/` excluded from git and deployment via `.gitignore` and `.gcloudignore`
- JavaScript tests run locally without server (Node.js environment)

### 4. Verify Google Cloud Authentication
```bash
# Check authentication status
gcloud auth list

# Verify project configuration
gcloud config get-value project
# Should output: vancouver-cbc-registration

# Test Secret Manager access
gcloud secrets list --filter="name~test-"
# Should show test account secrets
```

### 5. Verify Firefox Browser Setup
```bash
# Check Firefox version (run in Command Prompt)
firefox --version

# Alternative check via Windows
"C:\Program Files\Mozilla Firefox\firefox.exe" --version
```

**Firefox Installation Notes:**
- Download from: https://www.mozilla.org/en-US/firefox/new/
- Firefox is the primary browser due to better OAuth stability than Chrome
- WebDriver (geckodriver) is automatically managed by webdriver-manager

**Chrome Notes (Optional):**
- Chrome can still be used but has OAuth stability issues with Google Identity Services
- Chrome crashes frequently during automated OAuth flows

### 6. Test Environment Verification
```bash
# Navigate to test directory
cd tests

# Run configuration validation
python -c "from config import TEST_CONFIG, get_base_url; print(f'Target URL: {get_base_url()}')"

# Test Firestore connection
python -c "from google.cloud import firestore; client = firestore.Client(); print('Firestore connection successful')"

# Test Secret Manager access
python -c "from google.cloud import secretmanager; client = secretmanager.SecretManagerServiceClient(); print('Secret Manager connection successful')"

# Test JavaScript tests
npm run test:email-validation
# Should show: Tests: 81 passed, 81 total
```

## Test Account Configuration

### Google Workspace Accounts
The following test accounts have been created in the Nature Vancouver Google Workspace:

- **Admin Accounts**:
  - `cbc-test-admin1@naturevancouver.ca` (primary admin testing)
  - `cbc-test-admin2@naturevancouver.ca` (concurrent admin testing)
- **Leader Account**:
  - `cbc-test-leader1@naturevancouver.ca` (area leader testing)

### Password Storage
Test account passwords are stored securely in Google Secret Manager:
- `test-admin1-password`
- `test-admin2-password`
- `test-leader1-password`

**Security Note**: Passwords are NEVER stored in version-controlled files. They are retrieved automatically during test execution.

### Admin Whitelist Configuration
Test admin accounts are automatically configured based on environment detection:

- **Test Environment**: Test admin accounts (`cbc-test-admin1@`, `cbc-test-admin2@naturevancouver.ca`) are automatically added
- **Production Environment**: Only production admin accounts are active
- **No Manual Configuration**: Admin whitelist is managed automatically via environment detection

The system detects test environments using:
- `TEST_MODE=true` environment variable
- `FLASK_ENV=development` setting
- Project name containing 'test'

**Security Feature**: Runtime validation prevents test accounts from being accidentally deployed to production.

## Environment Configuration

### Test Target Configuration
Set the target environment for testing:

```bash
# Test against test environment (default)
set TEST_TARGET=test

# Test against production environment (use carefully)
set TEST_TARGET=production
```

### Browser Configuration
Configure browser behavior in `tests/config.py`:

```python
TEST_CONFIG = {
    # Browser configuration
    'browser': 'firefox',  # Primary browser (Chrome has OAuth issues)
    'headless': True,  # Set to False for debugging OAuth flows
    'window_size': (1920, 1080),
    # ... other settings
}
```

**Debugging Configuration:**
- Set `headless: False` to see browser interactions
- Increase timeouts if tests are failing due to slow page loads
- Enable verbose logging for detailed OAuth flow debugging

## Database Setup

### Test Data Isolation
The test suite uses year-based isolation:
- **Current Year**: For functional testing with realistic data
- **Year 2000**: For isolated testing to avoid conflicts

### Database State Management
Tests automatically manage database state:
- **Clean Database**: Clears test collections before critical tests
- **Populated Database**: Creates realistic test datasets
- **State Verification**: Validates data consistency after operations

### Identity-Based Testing Setup
The test suite includes comprehensive identity-based testing for family email scenarios:

#### Test Database Fixtures
- **`identity_test_database`**: Pre-populated with family scenarios for comprehensive testing
- **`single_identity_test`**: Clean database with identity utilities for isolated testing
- **Family Scenarios**: Standard test families with shared emails and multiple members

#### Identity Test Utilities
The test suite includes specialized utilities in `tests/utils/identity_utils.py`:
- **IdentityTestHelper**: Complete helper class for identity-based operations
- **Family Scenario Creation**: Automated setup of multi-member families
- **Synchronization Validation**: Participant/leader record consistency checking
- **Isolation Testing**: Verification that family members don't affect each other
- **Cleanup Utilities**: Automatic cleanup of test data

#### Test Configuration
Identity test configuration is defined in `tests/config.py`:
```python
# Identity-specific test settings
IDENTITY_TEST_CONFIG = {
    'family_scenarios': [...],  # Standard family test scenarios
    'identity_rules': {...},    # Identity validation rules
    'test_data': {...},         # Test data generation settings
    'synchronization_expectations': {...}  # Expected behaviors
}
```

#### Required Project Dependencies
Identity tests use the existing project models and utilities with single-table design:
- **models/participant.py**: ParticipantModel with year-aware operations and leadership flags
- **Single-Table Leadership**: Leadership stored as flags (`is_leader`, `assigned_area_leader`) in participant records
- **Identity-Based Operations**: All participant operations use `(first_name, last_name, email)` tuple matching
- **Synchronization**: Leadership status maintained within participant records for data consistency

## Troubleshooting

### Common Issues

#### 1. OAuth Authentication Failures
**Symptoms**: `AuthenticationError` during login tests
**Causes**:
- OAuth consent screen not published
- Environment detection not working (test accounts not automatically added)
- Invalid credentials in Secret Manager

**Solutions**:
```bash
# Verify secret values
gcloud secrets versions access latest --secret="test-admin1-password"

# Check OAuth client configuration in Google Console
# Ensure consent screen is PUBLISHED (not in testing mode)

# Verify environment detection and deployment
./deploy.sh test

# Check environment detection in logs
gcloud run services logs read cbc-test --region=us-west1 --limit=10 | grep "environment detected"
```

#### 2. Firestore Connection Issues
**Symptoms**: `google.api_core.exceptions.PermissionDenied`
**Causes**:
- Incorrect project configuration
- Missing Firestore permissions
- Database doesn't exist

**Solutions**:
```bash
# Verify project setting
gcloud config set project vancouver-cbc-registration

# Check Firestore permissions
gcloud projects get-iam-policy vancouver-cbc-registration

# Create databases if missing
python utils/setup_databases.py
```

#### 3. Browser Driver Issues
**Firefox Issues (Primary Browser):**
- `WebDriverException: 'geckodriver' executable issues`
- Firefox not installed
- Geckodriver automatically managed by webdriver-manager

**Chrome Issues (Secondary Browser):**
- OAuth stability problems with Google Identity Services
- Frequent crashes during automated OAuth flows
- Use Firefox instead for reliable OAuth testing

**Solutions**:
```bash
# Install/update Firefox (recommended)
# Download from: https://www.mozilla.org/en-US/firefox/new/

# For Chrome (secondary option with OAuth issues)
# Download from: https://www.google.com/chrome/

# Verify installation
firefox --version
chrome --version

# Install webdriver-manager (included in requirements)
pip install webdriver-manager
```

#### 4. Rate Limiting Issues
**Symptoms**: Tests failing with 429 Too Many Requests
**Causes**:
- Test execution too fast for rate limits
- Not using TEST_MODE environment

**Solutions**:
- Increase delays in `tests/config.py`
- Verify test environment uses higher rate limits
- Use smaller test datasets for rapid iteration

#### 5. Test Data Conflicts
**Symptoms**: Inconsistent test results, duplicate data errors
**Causes**:
- Previous test data not cleaned up
- Multiple test runs overlapping

**Solutions**:
```bash
# Manual database cleanup
python -c "
from tests.utils.database_utils import create_database_manager
from google.cloud import firestore
db = firestore.Client()
manager = create_database_manager(db)
manager.clear_test_collections()
"
```

#### 6. Identity Test Issues
**Symptoms**: Identity synchronization test failures, family scenario errors
**Causes**:
- Missing identity-based methods in AreaLeaderModel
- Outdated project code without synchronization fixes
- Test data pollution between identity tests

**Solutions**:
```bash
# Verify single-table design is working
python -c "
from models.participant import ParticipantModel
from google.cloud import firestore
model = ParticipantModel(firestore.Client())
# Check if model supports leadership flags
participants = model.get_all_participants()
leaders = model.get_leaders()
print(f'Single-table design working: {len(participants)} participants, {len(leaders)} leaders')
"

# Clean up identity test data
python -c "
from tests.utils.identity_utils import create_identity_helper
from google.cloud import firestore
helper = create_identity_helper(firestore.Client())
count = helper.cleanup_test_identities('test-')
print(f'Cleaned up {count} identity test records')
"

# Verify synchronization fix deployment
curl -I https://cbc-test.naturevancouver.ca/admin
# Should redirect to login - confirms test environment is accessible
```

**Identity Test Validation**:
```bash
# Test identity helper functionality
python -c "
from tests.utils.identity_utils import create_identity_helper
from google.cloud import firestore
helper = create_identity_helper(firestore.Client())
pid, lid = helper.create_test_identity('ValidationTest', 'A', 'both')
print(f'Created test identity: participant={pid}, leader={lid}')
helper.cleanup_test_identities('ValidationTest')
print('Identity helper working correctly')
"
```

### Network and Cloud Issues

#### Cloud Run Cold Starts
**Symptoms**: Timeouts on first requests to test environment
**Solutions**:
- Increase initial timeout values
- Implement warm-up requests in test setup
- Use retry logic for first requests

#### Firestore Eventual Consistency
**Symptoms**: Tests pass individually but fail in sequence
**Solutions**:
- Add delays after write operations
- Use document existence verification
- Implement proper wait conditions

### Debugging Tips

#### Enable Verbose Logging
```bash
# Run tests with detailed logging
pytest tests/ -v --log-cli-level=DEBUG

# Save logs to file
pytest tests/ -v --log-cli-level=DEBUG > test_output.log 2>&1
```

#### Browser Debugging
Set `headless: False` in `tests/config.py` and run individual tests with Firefox:
```bash
pytest tests/test_registration.py::test_basic_registration -v
```

#### Database State Inspection
```python
# Check database contents
from tests.utils.database_utils import create_database_manager
from google.cloud import firestore

db = firestore.Client()
manager = create_database_manager(db)
stats = manager.get_database_stats()
print(stats)
```

## Performance Optimization

### Test Execution Speed
- **Parallel Execution**: Use `pytest-xdist` for independent tests
- **Test Categorization**: Run critical tests first, slow tests separately
- **Browser Reuse**: Consider session-scoped browser fixtures for related tests

### Resource Management
- **Memory Usage**: Close browser instances properly
- **Network Efficiency**: Batch database operations where possible
- **Cloud Costs**: Monitor Cloud Run usage during extended test runs

## Security Considerations

### Credential Management
- **Never commit passwords** to version control
- **Rotate test account passwords** periodically
- **Monitor Secret Manager access** logs

### Test Environment Isolation
- **Use test database** (`cbc-test`) exclusively
- **Verify environment** before destructive operations
- **Limit production access** to read-only verification tests

### Data Privacy
- **Use synthetic test data** for participant information
- **Avoid real email addresses** in test data
- **Clean up test data** after test completion

## Test Suite Organization

### Python Tests (pytest)
- **Location**: `tests/test_*.py`
- **Framework**: pytest with fixtures and markers
- **Environment**: Runs against cloud environments (cbc-test.naturevancouver.ca)
- **Authentication**: Uses Google OAuth with test accounts
- **Database**: Tests against Firestore (cbc-test database)
- **Total Tests**: 51+ Python tests for backend validation

### JavaScript Tests (Jest)
- **Location**: `tests/*.test.js`
- **Framework**: Jest with Node.js environment
- **Environment**: Runs locally without server
- **Focus**: Frontend validation logic (email validation)
- **Total Tests**: 81 JavaScript tests for frontend validation
- **Execution Time**: ~0.5 seconds

### Test Directory Structure
```
tests/
├── config.py                     # Python test configuration
├── conftest.py                   # Pytest fixtures
├── pytest.ini                    # Pytest settings
├── requirements.txt              # Python test dependencies
├── package.json                  # Jest configuration
├── node_modules/                 # Jest dependencies (excluded from git/deploy)
├── utils/                        # Test utilities (auth, database, identity)
├── test_*.py                     # Python test modules (pytest)
└── *.test.js                     # JavaScript test modules (Jest)
```

### Deployment Safety
- **JavaScript dependencies**: Installed in `tests/node_modules/` only (not project root)
- **Git exclusions**: `.gitignore` excludes `node_modules/`, `package-lock.json`, `*.log`
- **Deployment exclusions**: `.gcloudignore` excludes entire `tests/` directory
- **No accidental deployment**: Test code and dependencies never deployed to Cloud Run

## Recent Test Framework Improvements (Updated 2025-09-30)

### ✅ **Email Validation Testing Complete**

**✅ Frontend and Backend Validation Consistency (132 tests)**:
- **Python Tests**: 51 pytest tests for backend email validation (`test_email_validation.py`)
- **JavaScript Tests**: 81 Jest tests for frontend email validation (`email_validation.test.js`)
- **Consistency**: Both test suites use identical test cases to ensure validation parity
- **Security**: Both validate RFC 5322 compliance with security restrictions (reject % and !)
- **Coverage**: Valid emails, invalid emails, length limits, plus signs, TLDs, subdomains, edge cases

### ✅ **Functional Test Framework Established**

**✅ Basic Functional Test Suite (6 smoke tests operational)**:
- **Implementation**: `test_admin_core_functionality.py` with OAuth integration framework
- **Scope**: Minimal validation of core admin workflows (starting point for comprehensive coverage)
- **Performance**: 6 smoke tests execute in 3.5 minutes (proves framework efficiency)
- **Framework**: Test infrastructure established with OAuth, database, and page object integration

### ✅ **Resolved Issues (Complete)**

**Global Timeout Issues (Resolved 2025-09-26)**:
- **Issue**: 2-minute global timeout too short for OAuth + database operations
- **Root Cause**: Pytest timeout configuration inappropriate for functional tests
- **Solution**: Removed global timeout from `pytest.ini`, use individual test timeouts
- **Result**: Tests now run without artificial time constraints

**Method Name Issues (Resolved 2025-09-26)**:
- **Issue**: `AttributeError: 'ParticipantModel' object has no attribute 'get_participant_by_id'`
- **Root Cause**: Test used incorrect method name for database queries
- **Solution**: Updated tests to use correct `get_participant()` method
- **Result**: All database operations work correctly

**Element Interaction Problems (Resolved)**:
- **Issue**: `ElementClickInterceptedException` and `ElementNotInteractableException`
- **Root Cause**: Elements not in viewport or covered by other elements
- **Solution**: Implemented scroll-into-view with JavaScript click fallbacks
- **Result**: All UI interactions work reliably

**Success Page Verification Problems (Resolved)**:
- **Issue**: Tests expecting `<h1>` elements on success pages that don't exist
- **Root Cause**: Tests relied on DOM structure rather than functional verification
- **Solution**: Implemented `verify_registration_success()` using URL patterns and database validation
- **Result**: More robust success verification using participant IDs from URLs

**Import Path Problems (Resolved)**:
- **Issue**: `ModuleNotFoundError` for project imports in test files
- **Root Cause**: Missing project root path setup in test files
- **Solution**: Added project root path configuration to test files
- **Result**: All imports work correctly

### 📊 **Current Test Status (2025-09-26)**

**✅ Basic Functional Test Suite (6 smoke tests operational)**:
```bash
# Basic functional smoke tests - framework validation
pytest tests/test_admin_core_functionality.py -v
# Result: 6 passed in 209.51s (0:03:29)
```

**✅ Registration Tests (4/4 Passing)**:
```bash
# All registration types working
pytest tests/test_single_table_regression.py::TestParticipantRegistration -v
```

**✅ OAuth Authentication (Working)**:
- Google OAuth automation with error handling
- Automatic popup dismissal and session management
- Performance improved 6x (from 15+ seconds to under 5 seconds)

### 🔧 **Current Verification Commands**

**Run Basic Functional Test Suite**:
```bash
# Execute 6 smoke tests for core admin functionality (~3.5 minutes)
pytest tests/test_admin_core_functionality.py -v

# Individual smoke test execution
pytest tests/test_admin_core_functionality.py::TestAdminCoreFunctionality::test_01_admin_authentication_and_dashboard_access -v
```

**Quick Status Check**:
```bash
# Verify all critical systems working
pytest tests/test_admin_core_functionality.py::TestAdminCoreFunctionality::test_01_admin_authentication_and_dashboard_access -v

# Check registration functionality
pytest tests/test_single_table_regression.py::TestParticipantRegistration -v
```

**Debug Authentication (if needed)**:
```bash
# Check Secret Manager access
gcloud secrets list --filter="name~test-"

# Verify OAuth configuration
curl -I https://cbc-test.naturevancouver.ca/auth/login
```

### 🎯 **Test Framework Achievement Summary**

**✅ Foundation Established**: Basic functional test framework operational with 6 smoke tests
**✅ Infrastructure Working**: OAuth integration, database operations, and page object model functional
**✅ Framework Reliability**: Test execution environment reliable with resolved infrastructure bugs
**✅ Proof of Concept**: Demonstrates feasibility for comprehensive test suite development
**✅ Development Ready**: Framework ready for expanding from smoke tests to comprehensive coverage

---

This setup guide provides the foundation for running the Christmas Bird Count registration test suite. Follow the troubleshooting section for resolving common issues, and refer to TESTING.md for test execution instructions.