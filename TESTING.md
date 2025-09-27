# Test Execution Guide
{# Updated by Claude AI on 2025-09-24 #}

## Overview

This document provides instructions for running the Christmas Bird Count registration test suite. The test suite validates critical workflows, data integrity, and admin operations against cloud environments.

## Prerequisites

### Required Google Cloud Authentication

Before running tests, ensure you have the proper Google Cloud authentication configured:

#### 1. Basic gcloud Authentication
```bash
# Check if you're authenticated
gcloud auth list

# If not authenticated, login
gcloud auth login

# Verify project is set correctly
gcloud config get-value project
# Should return: vancouver-cbc-registration

# Set project if not configured
gcloud config set project vancouver-cbc-registration
```

#### 2. Application Default Credentials (Required)
Tests require Application Default Credentials for accessing Firestore and Secret Manager:

```bash
# Set up application default credentials (opens browser)
gcloud auth application-default login

# Verify credentials are working
gcloud auth application-default print-access-token
```

#### 3. Verify Test Dependencies Access
```bash
# Test Secret Manager access (should list test secrets)
gcloud secrets list --filter="name~test-"

# Test Firestore connection
python -c "from google.cloud import firestore; firestore.Client(); print('Firestore connection successful')"

# Test Secret Manager access
python -c "from google.cloud import secretmanager; secretmanager.SecretManagerServiceClient(); print('Secret Manager connection successful')"
```

#### 4. Firefox Browser Requirement
```bash
# Verify Firefox is installed (primary browser for OAuth stability)
firefox --version

# Chrome can also be used but has OAuth reliability issues
chrome --version
```

**Important Notes:**
- Application Default Credentials expire and need periodic renewal
- Run `gcloud auth application-default login` if tests fail with authentication errors
- Firefox is the primary browser due to better OAuth automation stability
- Chrome has known issues with Google Identity Services automation

## Quick Start

### Basic Test Execution
```bash
# Navigate to project root
cd C:\AndroidStudioProjects\christmas-bird-count-registration

# Run all tests with verbose output
pytest tests/ -v

# Run critical tests only
pytest tests/ -m critical -v

# Run with HTML report
pytest tests/ -v --html=test_reports/report.html --self-contained-html
```

### Test Categories

#### Critical Tests (Priority 1)
```bash
# Registration and authentication workflows
pytest tests/ -m critical -v

# Minimal functional test suite (6 smoke tests, ~3.5 minutes)
pytest tests/test_admin_core_functionality.py -v

# Specific critical test files
pytest tests/test_registration.py -v
pytest tests/test_authentication.py -v
pytest tests/test_data_consistency.py -v
pytest tests/test_identity_synchronization.py -v
```

#### Admin Operations (Priority 2)
```bash
# Admin interface functionality
pytest tests/ -m admin -v

# CSV export validation
pytest tests/ -m csv -v

# Participant management
pytest tests/test_admin_workflows.py -v
```

#### Security Tests (Priority 3)
```bash
# Security validation
pytest tests/ -m security -v

# Input sanitization and CSRF protection
pytest tests/test_security.py -v
```

#### Identity Tests (Critical for Data Integrity)
```bash
# All identity-based tests (family email scenarios, synchronization)
pytest tests/ -m identity -v

# Core identity synchronization tests (regression prevention)
pytest tests/test_identity_synchronization.py -v

# Family email scenario tests (shared email validation)
pytest tests/test_family_email_scenarios.py -v

# Critical identity tests only
pytest tests/ -m "critical and identity" -v

# Identity synchronization regression tests
pytest tests/test_identity_synchronization.py::TestSynchronizationRegression -v
```

## Test Execution Options

### Target Environment Selection
```bash
# Test against test environment (default)
set TEST_TARGET=test
pytest tests/ -v

# Test against production (read-only verification)
set TEST_TARGET=production
pytest tests/ -m "not destructive" -v
```

### Test Filtering and Selection

#### Run Specific Tests
```bash
# Single test file
pytest tests/test_registration.py -v

# Single test function
pytest tests/test_registration.py::test_basic_registration -v

# Multiple test files
pytest tests/test_registration.py tests/test_authentication.py -v
```

#### Filter by Markers
```bash
# Critical functionality only
pytest tests/ -m critical

# Admin tests only
pytest tests/ -m admin

# Exclude slow tests
pytest tests/ -m "not slow"

# Security tests only
pytest tests/ -m security

# Identity tests only (family email scenarios, synchronization)
pytest tests/ -m identity

# Browser tests only
pytest tests/ -m browser

# Combined markers
pytest tests/ -m "critical and identity"  # Critical identity tests only
pytest tests/ -m "identity and not slow"  # Fast identity tests only
```

#### Filter by Keywords
```bash
# Tests containing "registration" in name
pytest tests/ -k registration -v

# Tests containing "csv" or "export"
pytest tests/ -k "csv or export" -v

# Tests containing "identity" or "synchronization"
pytest tests/ -k "identity or synchronization" -v

# Tests containing "family" (family email scenarios)
pytest tests/ -k "family" -v

# Exclude database tests
pytest tests/ -k "not database" -v

# Exclude slow identity tests
pytest tests/ -k "identity and not performance" -v
```

### Parallel Execution
```bash
# Run tests in parallel (when pytest-xdist is installed)
pytest tests/ -n auto -v

# Run with specific number of workers
pytest tests/ -n 4 -v

# Note: Be careful with parallel execution for database tests
```

## Test Reports and Output

### HTML Reports
```bash
# Generate detailed HTML report
pytest tests/ -v --html=test_reports/report.html --self-contained-html

# Open report in browser (Windows)
start test_reports/report.html
```

### Console Output Formatting
```bash
# Verbose output with test details
pytest tests/ -v

# Show test durations
pytest tests/ --durations=10

# Show only failures
pytest tests/ --tb=short

# Quiet mode (minimal output)
pytest tests/ -q
```

### Logging and Debugging
```bash
# Enable debug logging
pytest tests/ --log-cli-level=DEBUG -v

# Capture and display print statements
pytest tests/ -s -v

# Save output to file
pytest tests/ -v > test_results.log 2>&1
```

## Test Data Management

### Database State Control
```bash
# [TO BE IMPLEMENTED]
# Tests automatically manage database state via fixtures

# Manual database cleanup (if needed)
python -c "
from tests.utils.database_utils import create_database_manager
from google.cloud import firestore
db = firestore.Client()
manager = create_database_manager(db)
manager.clear_test_collections()
print('Test collections cleared')
"
```

### Test Dataset Generation
```bash
# [TO BE IMPLEMENTED]
# Generate small test dataset
python tests/utils/dataset_generator.py --size small

# Generate large test dataset (350+ participants)
python tests/utils/dataset_generator.py --size large

# Generate edge case datasets
python tests/utils/dataset_generator.py --scenario edge_cases
```

## Debugging Failed Tests

### Browser Debugging
```bash
# Run with visible browser (set headless: False in config)
# Edit tests/config.py: TEST_CONFIG['headless'] = False
pytest tests/test_registration.py::test_basic_registration -v -s
```

### Step-by-Step Debugging
```bash
# Run single test with maximum verbosity
pytest tests/test_registration.py::test_basic_registration -vvv -s --tb=long

# Add Python debugger breakpoints in test code:
# import pdb; pdb.set_trace()
```

### Database State Inspection
```bash
# [TO BE IMPLEMENTED]
# Check current database state
python -c "
from tests.utils.database_utils import create_database_manager
from google.cloud import firestore
db = firestore.Client()
manager = create_database_manager(db)
stats = manager.get_database_stats()
print('Database Stats:', stats)
consistency = manager.verify_data_consistency()
print('Data Consistency:', consistency)
"
```

## Performance Testing

### Large Dataset Testing
```bash
# [TO BE IMPLEMENTED]
# Test with realistic data volumes
pytest tests/ -m "slow" -v --timeout=300

# CSV export performance
pytest tests/test_csv_export.py -k large_dataset -v
```

### Concurrent Operations
```bash
# [TO BE IMPLEMENTED]
# Test race conditions and concurrent admin operations
pytest tests/test_race_conditions.py -v
```

## Continuous Integration (Future)

### Test Suite Validation
```bash
# [PLACEHOLDER FOR FUTURE CI INTEGRATION]
# Run full test suite for deployment validation
pytest tests/ -m "critical or admin" --html=ci_report.html

# Production smoke tests (read-only)
set TEST_TARGET=production
pytest tests/ -m "smoke and not destructive" -v
```

## Test Maintenance

### Test Suite Health Checks
```bash
# [TO BE IMPLEMENTED]
# Verify test configuration
python tests/validate_test_config.py

# Check test account access
python tests/verify_test_accounts.py

# Validate test environment connectivity
python tests/health_check.py
```

### Updating Test Data
```bash
# [TO BE IMPLEMENTED]
# Regenerate test datasets after schema changes
python tests/utils/regenerate_test_datasets.py

# Update expected CSV outputs
python tests/utils/update_csv_expectations.py
```

## Common Test Scenarios

### Minimal Functional Test Suite Execution
```bash
# Basic functional smoke tests (6 tests, ~3.5 minutes)
# Note: These provide minimal validation of core admin workflows - foundation for comprehensive testing
pytest tests/test_admin_core_functionality.py -v

# Individual functional smoke tests
pytest tests/test_admin_core_functionality.py::TestAdminCoreFunctionality::test_01_admin_authentication_and_dashboard_access -v
pytest tests/test_admin_core_functionality.py::TestAdminCoreFunctionality::test_02_participant_search_and_filtering -v
pytest tests/test_admin_core_functionality.py::TestAdminCoreFunctionality::test_03_participant_editing_with_field_preservation -v
pytest tests/test_admin_core_functionality.py::TestAdminCoreFunctionality::test_04_leader_promotion_and_demotion_workflow -v
pytest tests/test_admin_core_functionality.py::TestAdminCoreFunctionality::test_05_area_assignment_changes -v
pytest tests/test_admin_core_functionality.py::TestAdminCoreFunctionality::test_06_basic_csv_export_functionality -v
```

### Registration Workflow Testing
```bash
# Basic registration flow
pytest tests/test_registration.py::test_basic_registration -v

# FEEDER participant constraints
pytest tests/test_registration.py::test_feeder_constraints -v

# Form validation and error handling
pytest tests/test_registration.py::test_form_validation -v
```

### Admin Workflow Testing
```bash
# Leader management workflow
pytest tests/test_admin_workflows.py::test_leader_promotion_deletion -v

# Participant management operations
pytest tests/test_admin_workflows.py::test_participant_assignment -v

# CSV export validation
pytest tests/test_csv_export.py -v
```

### Data Consistency Testing
```bash
# [TO BE IMPLEMENTED]
# Clive Roberts scenario (leader promotion/deletion bug) - single-table version
pytest tests/test_data_consistency.py::test_leader_promotion_deletion_cycle -v

# Single-table leadership flag synchronization
pytest tests/test_data_consistency.py::test_participant_leadership_flags -v
```

### Identity-Based Testing
```bash
# Core identity synchronization tests (validates bug fixes)
pytest tests/test_identity_synchronization.py -v

# Participant deletion → leader deactivation
pytest tests/test_identity_synchronization.py::TestIdentitySynchronization::test_participant_deletion_deactivates_leader -v

# Identity-based deactivation method validation
pytest tests/test_identity_synchronization.py::TestIdentitySynchronization::test_identity_based_deactivation_method -v

# Regression tests for specific bugs
pytest tests/test_identity_synchronization.py::TestSynchronizationRegression::test_some_guy_scenario -v
pytest tests/test_identity_synchronization.py::TestSynchronizationRegression::test_clive_roberts_scenario -v

# Family email scenario tests
pytest tests/test_family_email_scenarios.py -v

# Family creation and isolation
pytest tests/test_family_email_scenarios.py::TestFamilyEmailSharing::test_family_creation_and_isolation -v

# Family member independence
pytest tests/test_family_email_scenarios.py::TestFamilyEmailSharing::test_family_member_identity_isolation -v

# Family leader management
pytest tests/test_family_email_scenarios.py::TestFamilyEmailSharing::test_family_leader_management_independence -v

# Edge cases and performance tests
pytest tests/test_family_email_scenarios.py::TestFamilyEmailEdgeCases -v
pytest tests/test_family_email_scenarios.py::TestFamilyEmailPerformance -v

# All identity tests (comprehensive)
pytest tests/ -m identity -v
```

## Troubleshooting

### Common Test Failures

#### Authentication Issues
**Common Symptoms:**
- `google.auth.exceptions.DefaultCredentialsError`
- `PermissionDenied` errors accessing Secret Manager or Firestore
- OAuth flow timeouts or crashes

**Solutions:**
```bash
# Renew application default credentials (most common fix)
gcloud auth application-default login

# Check current authentication
gcloud auth list

# Verify project configuration
gcloud config get-value project

# Test Secret Manager access
gcloud secrets list --filter="name~test-"

# Test Firestore access
python -c "from google.cloud import firestore; firestore.Client().collection('test').limit(1).get()"

# OAuth debugging with visible Firefox browser
# Set headless: False in tests/config.py and browser: 'firefox'
```

**OAuth-Specific Issues:**
- **Chrome crashes**: Switch to Firefox in `tests/config.py`
- **Consent screen**: Should be handled automatically by auth_utils.py
- **Session timeouts**: Increase oauth_timeout in TEST_CONFIG

#### Database Connection Issues
```bash
# Verify Firestore connection
python -c "from google.cloud import firestore; firestore.Client().collection('test').limit(1).get()"

# Check project configuration
gcloud config get-value project
```

#### Browser Issues
```bash
# Update Chrome browser
# Install latest Chrome from https://www.google.com/chrome/

# Clear browser cache and data
# May require manual browser reset
```

#### Identity Test Issues
```bash
# Check single-table leadership functionality
python -c "
from models.participant import ParticipantModel
from google.cloud import firestore
model = ParticipantModel(firestore.Client())
participants = model.get_all_participants()
leaders = model.get_leaders()
print(f'Single-table design working: {len(participants)} participants, {len(leaders)} leaders')
"

# Test identity helper functionality
python -c "
from tests.utils.identity_utils import create_identity_helper
from google.cloud import firestore
helper = create_identity_helper(firestore.Client())
print('Identity helper initialized successfully')
"

# Check for test data pollution
pytest tests/test_identity_synchronization.py::TestIdentitySynchronization::test_identity_based_deactivation_method -v --tb=short

# Clean up leftover identity test data
python -c "
from tests.utils.identity_utils import create_identity_helper
from google.cloud import firestore
helper = create_identity_helper(firestore.Client())
count = helper.cleanup_test_identities('test-')
print(f'Cleaned up {count} identity test records')
"

# Verify synchronization fix deployment
curl -s https://cbc-test.naturevancouver.ca | grep -q "Christmas Bird Count" && echo "Test environment accessible" || echo "Test environment issue"
```

#### Family Email Scenario Issues
```bash
# Test family scenario creation
pytest tests/test_family_email_scenarios.py::TestFamilyEmailSharing::test_family_creation_and_isolation -v -s

# Verify family isolation
pytest tests/test_family_email_scenarios.py::TestFamilyEmailSharing::test_family_member_identity_isolation -v -s

# Check family scenario database state
python -c "
from tests.utils.identity_utils import STANDARD_FAMILY_SCENARIOS
for scenario in STANDARD_FAMILY_SCENARIOS:
    print(f'Family: {scenario[\"email\"]} with {len(scenario[\"members\"])} members')
"

# Manual family cleanup if tests fail
python -c "
from tests.utils.identity_utils import create_identity_helper
from google.cloud import firestore
helper = create_identity_helper(firestore.Client())
count = helper.cleanup_test_identities('test-scenarios.ca')
print(f'Cleaned up {count} family scenario records')
"
```

### Test Environment Issues

#### Test Environment Unavailable
```bash
# Check test environment status
curl -I https://cbc-test.naturevancouver.ca

# Monitor Cloud Run logs
gcloud run services logs read cbc-test --region=us-west1 --limit=20
```

#### Rate Limiting
```bash
# Reduce test execution speed
# Edit tests/config.py to increase delays

# Use smaller test datasets
# Modify TEST_CONFIG batch sizes
```

## Best Practices

### Test Development
- **Start Small**: Begin with single, focused test cases
- **Use Fixtures**: Leverage database and browser fixtures for consistency
- **Test Isolation**: Ensure tests don't depend on execution order
- **Clear Assertions**: Use descriptive assertion messages

### Test Execution
- **Run Critical Tests First**: Get fast feedback on core functionality
- **Use Appropriate Markers**: Tag tests for efficient filtering
- **Monitor Resources**: Watch browser memory and Cloud Run usage
- **Save Reports**: Keep HTML reports for analysis and sharing

### Debugging
- **Enable Verbose Logging**: Use DEBUG level for detailed OAuth and database operations
- **Use Visible Browser**: Set headless=False for visual debugging
- **Check Database State**: Verify data consistency after failed tests
- **Isolate Failures**: Run failing tests individually to understand root causes

---

This testing guide provides comprehensive instructions for executing and maintaining the Christmas Bird Count registration test suite. Refer to TEST_SETUP.md for initial setup and TEST_SUITE_SPEC.md for complete test requirements and scope.