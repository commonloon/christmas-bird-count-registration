# Test Execution Guide
{# Updated by Claude AI on 2025-10-15 #}

## Overview

This document provides instructions for running the Christmas Bird Count registration test suite. The test suite validates critical workflows, data integrity, and admin operations against cloud environments.

### Test Suite Organization

The test suite is organized into three main categories:

**Unit Tests** (`tests/unit/`):
- Fast local tests using Flask test client
- No browser, no network, no OAuth required
- Validates UI conformance (dropdowns, form fields, table columns)
- Tests model logic and data transformations
- Runs in seconds, ideal for development feedback

**Integration Tests** (`tests/`):
- Selenium-based tests against deployed servers
- Real browser automation with OAuth
- Tests complete workflows and user interactions
- Validates JavaScript behavior and AJAX operations
- Runs in minutes, comprehensive validation

**JavaScript Tests** (`tests/*.test.js`):
- Jest-based frontend unit tests
- Validates client-side validation functions
- Tests JavaScript utilities and form behaviors
- No server required, runs locally
- Fast execution for frontend development

## Prerequisites

### Required Google Cloud Authentication

Before running tests, ensure you have the proper Google Cloud authentication configured:

#### 1. Basic gcloud Authentication and application default credentials
```bash
# These two commands should ensure sufficient gcloud auth permissions to run the test suite
# Tests require Application Default Credentials for accessing Firestore and Secret Manager:

gcloud auth login
gcloud auth application-default login

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

#### Python Tests (pytest)
```bash
# Navigate to project root
cd C:\AndroidStudioProjects\christmas-bird-count-registration

# Run all Python tests with verbose output
pytest tests/ -v

# Run critical tests only
pytest tests/ -m critical -v

# Run with HTML report
pytest tests/ -v --html=test_reports/report.html --self-contained-html
```

#### JavaScript Tests (Jest)
```bash
# Navigate to tests directory
cd C:\AndroidStudioProjects\christmas-bird-count-registration\tests

# Run JavaScript email validation tests
npm run test:email-validation

# Run with verbose output
npm run test:email-validation:verbose

# Or run Jest directly
npx jest email_validation.test.js
```

#### Unit Tests (Local Flask Tests)
```bash
# Run all unit tests (fast, local execution, no server required)
pytest tests/unit/ -v

# Run UI conformance tests specifically
pytest tests/unit/test_ui_conformance.py -v

# Run specific UI test classes
pytest tests/unit/test_ui_conformance.py::TestRegistrationFormUI -v
pytest tests/unit/test_ui_conformance.py::TestAdminParticipantsUI -v

# Run model tests
pytest tests/unit/test_participant_model.py -v
pytest tests/unit/test_removal_log_model.py -v

# Run all unit tests with coverage
pytest tests/unit/ --cov=app --cov=models --cov=routes -v
```

**Unit Test Characteristics:**
- ⚡ **Fast execution** (no browser, no network, no OAuth)
- 🔧 **Local development** (runs against local code, not deployed server)
- 📋 **UI validation** (dropdown options, form fields, table columns)
- 🧪 **Model testing** (database operations, data transformations)
- 💰 **No rate limits** (purely local execution)

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

## Understanding Test Results

### Reading Test Output

When you run tests with pytest, the output follows a standard format:

```bash
# Example test run output:
============================= test session starts =============================
platform win32 -- Python 3.13.7, pytest-8.4.2, pluggy-1.6.0
rootdir: C:\AndroidStudioProjects\christmas-bird-count-registration\tests
collected 12 items

tests/test_registration.py::test_basic_registration PASSED           [  8%]
tests/test_registration.py::test_feeder_constraints FAILED           [ 16%]
tests/test_admin_workflows.py::test_leader_management SKIPPED        [ 25%]
tests/test_csv_export.py::test_export_format PASSED                  [ 33%]
...

================================== FAILURES ===================================
______________________ test_feeder_constraints ________________________________
[detailed error information here]

========================= short test summary info =============================
PASSED tests/test_registration.py::test_basic_registration
FAILED tests/test_registration.py::test_feeder_constraints - AssertionError
SKIPPED tests/test_admin_workflows.py::test_leader_management - No leaders found
================== 10 passed, 1 failed, 1 skipped in 45.23s ==================
```

**Understanding the symbols:**
- `.` = Test passed
- `F` = Test failed
- `s` = Test skipped
- `x` = Expected failure (xfail)
- `E` = Error during test execution

**Understanding the summary:**
- `PASSED` - Test completed successfully with all assertions passing
- `FAILED` - Test failed due to assertion error or exception
- `SKIPPED` - Test was intentionally skipped (e.g., missing prerequisites)
- `ERROR` - Test could not complete due to setup/teardown errors

### Test Result Details

When a test fails, pytest shows:
1. **Test name and location** - Which test failed and where it's defined
2. **Failure reason** - The assertion that failed or exception that occurred
3. **Traceback** - Full stack trace showing where the error happened
4. **Failed assertion context** - Values that caused the assertion to fail

Example failure output:
```bash
tests/test_registration.py:42: in test_feeder_constraints
    assert participant.area == "A"
E   AssertionError: assert "UNASSIGNED" == "A"
E    +  where "UNASSIGNED" = participant.area
```

This shows:
- Test location: `test_registration.py` line 42
- What failed: `assert participant.area == "A"`
- Why it failed: area was "UNASSIGNED" instead of "A"

### Verbose Output Options

```bash
# Minimal output (one character per test)
pytest tests/ -q

# Standard output (one line per test)
pytest tests/

# Verbose output (shows full test names)
pytest tests/ -v

# Extra verbose (shows test details and output)
pytest tests/ -vv

# Show local variables on failure
pytest tests/ -l

# Show full tracebacks
pytest tests/ --tb=long

# Show short tracebacks (default)
pytest tests/ --tb=short

# Show only one line per failure
pytest tests/ --tb=line

# No traceback
pytest tests/ --tb=no
```

## Test Reports and Output

### HTML Reports

**Note:** HTML reports are **not generated automatically**. You must explicitly request them using the `--html` flag.

```bash
# Generate detailed HTML report (requires pytest-html plugin)
pytest tests/ -v --html=test_reports/report.html --self-contained-html

# Open report in browser (Windows)
start test_reports/report.html

# Generate report in specific directory
pytest tests/ -v --html=reports/$(date +%Y%m%d)/test_results.html --self-contained-html
```

**HTML Report Contents:**
- Summary statistics (passed, failed, skipped counts)
- Test duration breakdown
- Full failure details with tracebacks
- Test logs and captured output
- Browser screenshots (for browser-based tests)
- Filterable and sortable results

**Default Behavior:**
- Without `--html` flag: Results displayed in console only
- With `--html` flag: Results in both console and HTML file
- `--self-contained-html`: Embeds CSS/JS in single file for easy sharing

### Console Output Formatting
```bash
# Verbose output with test details
pytest tests/ -v

# Show test durations (slowest 10 tests)
pytest tests/ --durations=10

# Show all test durations
pytest tests/ --durations=0

# Show only failures
pytest tests/ --tb=short

# Quiet mode (minimal output)
pytest tests/ -q
```

### Filtering Test Results Display

```bash
# Show only failed tests in summary
pytest tests/ --tb=short -v | grep FAILED

# Show only test names (no setup/teardown)
pytest tests/ --no-header --no-summary -q

# Show statistics summary only
pytest tests/ -q --tb=no

# Show detailed failure information only
pytest tests/ --tb=short -v 2>&1 | grep -A 20 "FAILURES"
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

### UI Conformance Testing (Unit Tests)

**Overview**: UI conformance tests validate that rendered HTML templates match the SPECIFICATION.md using Flask test client + BeautifulSoup. These tests run locally without a browser and connect to the real cbc-test database for data-driven validation.

**Characteristics**:
- ⚡ **Fast**: 77 tests in ~4.5 minutes
- 🔧 **Local**: No browser, no OAuth, runs against local Flask app
- 🎯 **Comprehensive**: 11 test classes covering all major UI pages
- 💾 **Data-driven**: Uses real test data from `tests/fixtures/test_participants_2025.csv`
- 🐛 **Bug detection**: Catches template errors like missing dropdown options
- ♿ **Accessibility**: Validates ARIA attributes, semantic HTML, and keyboard support

#### Run All UI Conformance Tests
```bash
# Run complete suite (77 tests)
pytest tests/unit/test_ui_conformance.py -v

# Run with coverage report
pytest tests/unit/test_ui_conformance.py --cov=templates --cov=routes -v

# Run fast (no verbose output)
pytest tests/unit/test_ui_conformance.py -q
```

#### Registration Form Tests (25 tests)
```bash
# All registration form tests
pytest tests/unit/test_ui_conformance.py::TestRegistrationFormUI -v

# Dropdown validation tests
pytest tests/unit/test_ui_conformance.py::TestRegistrationFormUI::test_skill_level_dropdown_has_all_four_options -v
pytest tests/unit/test_ui_conformance.py::TestRegistrationFormUI::test_experience_dropdown_has_correct_options -v
pytest tests/unit/test_ui_conformance.py::TestRegistrationFormUI::test_area_dropdown_has_all_public_areas -v
pytest tests/unit/test_ui_conformance.py::TestRegistrationFormUI::test_area_dropdown_has_unassigned_option -v

# Required field tests
pytest tests/unit/test_ui_conformance.py::TestRegistrationFormUI::test_required_fields_present -v
pytest tests/unit/test_ui_conformance.py::TestRegistrationFormUI::test_skill_level_dropdown_is_required -v
pytest tests/unit/test_ui_conformance.py::TestRegistrationFormUI::test_area_dropdown_is_required -v

# UI element presence tests
pytest tests/unit/test_ui_conformance.py::TestRegistrationFormUI::test_guide_links_present -v
pytest tests/unit/test_ui_conformance.py::TestRegistrationFormUI::test_privacy_section_present -v
pytest tests/unit/test_ui_conformance.py::TestRegistrationFormUI::test_map_div_present -v

# Label and field tests
pytest tests/unit/test_ui_conformance.py::TestRegistrationFormUI::test_phone_field_label_is_cell_phone -v
pytest tests/unit/test_ui_conformance.py::TestRegistrationFormUI::test_optional_fields_present -v
```

#### Admin Participants Page Tests (14 tests)
```bash
# All admin participants tests
pytest tests/unit/test_ui_conformance.py::TestAdminParticipantsUI -v

# Inline edit dropdown tests
pytest tests/unit/test_ui_conformance.py::TestAdminParticipantsUI::test_edit_skill_level_dropdown_includes_newbie -v
pytest tests/unit/test_ui_conformance.py::TestAdminParticipantsUI::test_edit_experience_is_dropdown_not_input -v
pytest tests/unit/test_ui_conformance.py::TestAdminParticipantsUI::test_edit_experience_dropdown_has_correct_options -v

# Year tabs and historical warnings tests
pytest tests/unit/test_ui_conformance.py::TestAdminParticipantsUI::test_year_tabs_present_with_multiple_years -v
pytest tests/unit/test_ui_conformance.py::TestAdminParticipantsUI::test_historical_year_warning_banner -v
pytest tests/unit/test_ui_conformance.py::TestAdminParticipantsUI::test_historical_year_tabs_have_distinctive_styling -v

# Table structure and modal tests
pytest tests/unit/test_ui_conformance.py::TestAdminParticipantsUI::test_table_has_all_required_columns -v
pytest tests/unit/test_ui_conformance.py::TestAdminParticipantsUI::test_delete_modal_structure -v
pytest tests/unit/test_ui_conformance.py::TestAdminParticipantsUI::test_leader_reassignment_modal_structure -v
```

#### Admin Leaders Page Tests (2 tests)
```bash
# All admin leaders tests
pytest tests/unit/test_ui_conformance.py::TestAdminLeadersUI -v

# Table validation
pytest tests/unit/test_ui_conformance.py::TestAdminLeadersUI::test_leaders_table_has_required_columns -v
pytest tests/unit/test_ui_conformance.py::TestAdminLeadersUI::test_potential_leaders_table_present -v
```

#### Admin Unassigned Page Tests (3 tests)
```bash
# All unassigned page tests (critical workflow)
pytest tests/unit/test_ui_conformance.py::TestAdminUnassignedPage -v

# Individual tests
pytest tests/unit/test_ui_conformance.py::TestAdminUnassignedPage::test_unassigned_page_loads -v
pytest tests/unit/test_ui_conformance.py::TestAdminUnassignedPage::test_unassigned_page_has_table -v
pytest tests/unit/test_ui_conformance.py::TestAdminUnassignedPage::test_unassigned_table_has_assignment_controls -v
```

#### CSV Export Tests (3 tests)
```bash
# All CSV export validation tests (critical for data integrity)
pytest tests/unit/test_ui_conformance.py::TestCSVExport -v

# Individual tests
pytest tests/unit/test_ui_conformance.py::TestCSVExport::test_csv_export_returns_csv_content_type -v
pytest tests/unit/test_ui_conformance.py::TestCSVExport::test_csv_export_has_filename_with_year -v
pytest tests/unit/test_ui_conformance.py::TestCSVExport::test_csv_export_has_required_headers -v
```

#### Data-Driven Rendering Tests (6 tests)
```bash
# All data-driven tests (validates actual database rendering)
pytest tests/unit/test_ui_conformance.py::TestDataDrivenParticipantRendering -v

# Individual rendering validation tests
pytest tests/unit/test_ui_conformance.py::TestDataDrivenParticipantRendering::test_participants_render_with_data -v
pytest tests/unit/test_ui_conformance.py::TestDataDrivenParticipantRendering::test_participant_names_display_correctly -v
pytest tests/unit/test_ui_conformance.py::TestDataDrivenParticipantRendering::test_skill_level_badges_render -v
pytest tests/unit/test_ui_conformance.py::TestDataDrivenParticipantRendering::test_feeder_participants_have_special_styling -v
pytest tests/unit/test_ui_conformance.py::TestDataDrivenParticipantRendering::test_equipment_icons_display -v
pytest tests/unit/test_ui_conformance.py::TestDataDrivenParticipantRendering::test_leader_badges_display_correctly -v
```

#### Info Pages and Dashboard Tests (6 tests)
```bash
# Info pages (3 tests)
pytest tests/unit/test_ui_conformance.py::TestInfoPages -v
pytest tests/unit/test_ui_conformance.py::TestInfoPages::test_area_leader_info_page_accessible -v
pytest tests/unit/test_ui_conformance.py::TestInfoPages::test_scribe_info_page_accessible -v
pytest tests/unit/test_ui_conformance.py::TestInfoPages::test_area_leader_info_preserves_form_data -v

# Dashboard (3 tests)
pytest tests/unit/test_ui_conformance.py::TestDashboardUI -v
pytest tests/unit/test_ui_conformance.py::TestDashboardUI::test_dashboard_loads_for_admin -v
pytest tests/unit/test_ui_conformance.py::TestDashboardUI::test_dashboard_has_statistics_section -v
pytest tests/unit/test_ui_conformance.py::TestDashboardUI::test_dashboard_has_year_selector -v
```

#### Empty State Display Tests (5 tests)
```bash
# All empty state tests
pytest tests/unit/test_ui_conformance.py::TestEmptyStateDisplays -v

# Individual empty state tests
pytest tests/unit/test_ui_conformance.py::TestEmptyStateDisplays::test_participants_page_empty_state_message -v
pytest tests/unit/test_ui_conformance.py::TestEmptyStateDisplays::test_unassigned_page_empty_state -v
pytest tests/unit/test_ui_conformance.py::TestEmptyStateDisplays::test_leaders_page_shows_areas_without_leaders -v
pytest tests/unit/test_ui_conformance.py::TestEmptyStateDisplays::test_dashboard_handles_zero_participants -v
pytest tests/unit/test_ui_conformance.py::TestEmptyStateDisplays::test_empty_area_shows_appropriate_message -v
```

#### Accessibility Tests (15 tests)
```bash
# All accessibility tests
pytest tests/unit/test_ui_conformance.py::TestAccessibility -v

# Semantic HTML structure tests
pytest tests/unit/test_ui_conformance.py::TestAccessibility::test_tables_have_thead_and_tbody -v
pytest tests/unit/test_ui_conformance.py::TestAccessibility::test_buttons_have_correct_type_attribute -v
pytest tests/unit/test_ui_conformance.py::TestAccessibility::test_main_content_has_semantic_structure -v
pytest tests/unit/test_ui_conformance.py::TestAccessibility::test_heading_hierarchy_exists -v

# ARIA attribute tests
pytest tests/unit/test_ui_conformance.py::TestAccessibility::test_navigation_has_aria_label -v
pytest tests/unit/test_ui_conformance.py::TestAccessibility::test_modals_have_aria_attributes -v

# Form accessibility tests
pytest tests/unit/test_ui_conformance.py::TestAccessibility::test_form_fields_have_associated_labels -v
pytest tests/unit/test_ui_conformance.py::TestAccessibility::test_select_fields_have_labels -v

# Image accessibility tests
pytest tests/unit/test_ui_conformance.py::TestAccessibility::test_images_have_alt_text -v
pytest tests/unit/test_ui_conformance.py::TestAccessibility::test_scope_icon_has_alt_text -v
```

#### Bug Detection Examples

These tests would catch:
```bash
# Missing "Newbie" option (bug we fixed)
pytest tests/unit/test_ui_conformance.py::TestAdminParticipantsUI::test_edit_skill_level_dropdown_includes_newbie -v

# Wrong area codes in dropdown
pytest tests/unit/test_ui_conformance.py::TestRegistrationFormUI::test_area_dropdown_has_all_public_areas -v

# Missing CSV headers (data integrity)
pytest tests/unit/test_ui_conformance.py::TestCSVExport::test_csv_export_has_required_headers -v

# Wrong phone label ("Phone" vs "Cell Phone")
pytest tests/unit/test_ui_conformance.py::TestRegistrationFormUI::test_phone_field_label_is_cell_phone -v
pytest tests/unit/test_ui_conformance.py::TestAdminParticipantsUI::test_participant_table_displays_phone_as_cell_phone -v

# Missing modals or buttons
pytest tests/unit/test_ui_conformance.py::TestAdminParticipantsUI::test_delete_modal_structure -v
pytest tests/unit/test_ui_conformance.py::TestAdminParticipantsUI::test_leader_reassignment_modal_structure -v
```

#### What These Tests Validate

✅ **These tests check**:
- Server-rendered HTML structure and content
- Hidden elements (inline edit controls that JavaScript toggles)
- Dropdown options match specification
- Table structures and column headers
- Modal HTML structure and buttons
- Data rendering with actual database records
- Bootstrap styling classes applied correctly
- Configuration values (areas from `config/areas.py`)
- Form validation attributes (email type, tel type, required fields)
- Year tabs and historical warnings
- Empty state handling across all pages
- Accessibility compliance (ARIA attributes, semantic HTML, alt text)
- Label associations and keyboard navigation support

❌ **These tests DON'T check** (use Selenium for these):
- JavaScript execution (button clicks, AJAX requests)
- Dynamic interactions (form submission, edit mode toggle)
- Visual rendering (CSS, layout, responsiveness)
- Browser-specific behavior

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

# Participant reassignment workflows (5 tests - All Passing, 1m 05s with optimizations)
pytest tests/test_participant_reassignment.py -v

# Individual reassignment tests (Bootstrap modal UI)
pytest tests/test_participant_reassignment.py::TestParticipantReassignment::test_01_regular_participant_reassignment -v
pytest tests/test_participant_reassignment.py::TestParticipantReassignment::test_02_leader_reassignment_decline_leadership -v  # Clicks "Team Member" button
pytest tests/test_participant_reassignment.py::TestParticipantReassignment::test_03_leader_reassignment_accept_leadership -v  # Clicks "Leader" button
pytest tests/test_participant_reassignment.py::TestParticipantReassignment::test_04_reassignment_validation_same_area -v  # JavaScript alert validation
pytest tests/test_participant_reassignment.py::TestParticipantReassignment::test_05_reassignment_cancel -v  # UI state restoration

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