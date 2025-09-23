# Test Suite Setup Instructions
{# Updated by Claude AI on 2025-09-22 #}

## Overview

This document provides complete setup instructions for the Christmas Bird Count registration system test suite. The test suite runs functional tests against cloud environments using real Google OAuth and Firestore databases.

## Prerequisites

### System Requirements
- **Operating System**: Windows 11 (development environment)
- **Python**: 3.8 or higher
- **Google Chrome**: Latest version installed and available in PATH
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

### 2. Install Test Dependencies
```bash
# Install test-specific requirements
pip install -r tests/requirements.txt

# Verify pytest installation
pytest --version
```

### 3. Verify Google Cloud Authentication
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

### 4. Verify Chrome Browser Setup
```bash
# Check Chrome version (run in Command Prompt)
"C:\Program Files\Google\Chrome\Application\chrome.exe" --version

# Alternative location check
"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe" --version
```

**Chrome Installation Notes:**
- Download from: https://www.google.com/chrome/
- Ensure Chrome is installed in default location for automatic detection
- If using non-standard installation, update `PATH` environment variable

### 5. Test Environment Verification
```bash
# Navigate to test directory
cd tests

# Run configuration validation
python -c "from config import TEST_CONFIG, get_base_url; print(f'Target URL: {get_base_url()}')"

# Test Firestore connection
python -c "from google.cloud import firestore; client = firestore.Client(); print('Firestore connection successful')"

# Test Secret Manager access
python -c "from google.cloud import secretmanager; client = secretmanager.SecretManagerServiceClient(); print('Secret Manager connection successful')"
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
    'headless': True,           # Set to False for debugging
    'window_size': (1920, 1080),
    'browser': 'chrome',
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
Identity tests use the existing project models and utilities:
- **models/participant.py**: ParticipantModel with year-aware operations
- **models/area_leader.py**: AreaLeaderModel with identity-based methods
- **Identity Methods**: New methods added for identity-based operations:
  - `get_leaders_by_identity(first_name, last_name, email)`
  - `deactivate_leaders_by_identity(first_name, last_name, email, removed_by)`
  - `get_areas_by_identity(first_name, last_name, email)`

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

#### 3. Chrome Driver Issues
**Symptoms**: `WebDriverException: 'chromedriver' executable needs to be in PATH`
**Causes**:
- Chrome not installed
- Chrome not in PATH
- Version mismatch

**Solutions**:
```bash
# Install/update Chrome
# Download from: https://www.google.com/chrome/

# Verify installation
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
# Verify identity methods are available
python -c "
from models.area_leader import AreaLeaderModel
from google.cloud import firestore
model = AreaLeaderModel(firestore.Client())
assert hasattr(model, 'get_leaders_by_identity'), 'Missing get_leaders_by_identity method'
assert hasattr(model, 'deactivate_leaders_by_identity'), 'Missing deactivate_leaders_by_identity method'
print('Identity methods available')
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
Set `headless: False` in `tests/config.py` and run individual tests:
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

---

This setup guide provides the foundation for running the Christmas Bird Count registration test suite. Follow the troubleshooting section for resolving common issues, and refer to TESTING.md for test execution instructions.