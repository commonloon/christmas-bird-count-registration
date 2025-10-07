# Christmas Bird Count Registration Test Suite Specification
{# Updated by Claude AI on 2025-10-07 #}

## Overview

This document defines the requirements and scope for a comprehensive functional test suite for the Christmas Bird Count registration system. The test suite prioritizes workflow validation, data integrity testing, and CSV export verification to prevent regression bugs in critical user flows.

## Core Requirements

### Testing Environment
- **Target Platform**: Cloud-based testing against `cbc-test.naturevancouver.ca`
- **Database**: Test instance uses `cbc-test` Firestore database (isolated from production)
- **Year Strategy**: Use current year for functional testing, year 2000 for historical/isolation testing
- **Authentication**: Real Google OAuth with dedicated test accounts
- **Browser Support**: Primary testing with Firefox due to Chrome OAuth stability issues

### Test Suite Architecture

#### Configuration Management
```
tests/
├── config.py                     # Non-sensitive test configuration
├── conftest.py                   # Pytest fixtures and setup
├── package.json                  # Jest configuration for JavaScript tests
├── utils/                        # Test utilities and helpers
│   ├── database_utils.py         # Database state management
│   ├── auth_utils.py             # OAuth automation helpers
│   └── dataset_generator.py     # Test data creation utilities
├── test_*.py                     # Python test modules (pytest)
├── *.test.js                     # JavaScript test modules (Jest)
└── node_modules/                 # Jest dependencies (excluded from git/deploy)
```

**Configuration Structure:**
- **Test URLs**: `cbc-test.naturevancouver.ca` and `cbc-registration.naturevancouver.ca`
- **Database Names**: `cbc-test` and `cbc-register`
- **Test Years**: Current year (functional), 2000 (isolation)
- **Retry Logic**: 3 attempts with exponential backoff
- **Credentials**: Google Secret Manager for test account passwords

### Test Data Management

#### Database State Management
- **Clean Database Fixtures**: Empty database for initialization testing
- **Populated Database Fixtures**: Realistic datasets for workflow testing
- **State Reset**: Clear year 2000 + current year `participants_YYYY` and `removal_log_YYYY` collections between test scenarios
- **Isolation**: Tests must not depend on execution order or previous test outcomes
- **Single-Table Design**: Leadership data stored as flags in participant records (`is_leader`, `assigned_area_leader`)

#### Test Dataset Requirements
1. **Small Dataset**: ~50 participants with `is_leader=True` flags for 40% of areas
2. **Large Dataset**: ~350 participants (realistic production scale) with leadership flags
3. **Edge Case Datasets**: All areas assigned leaders, some areas empty, single participant per area
4. **Realistic Distribution**: Uneven area assignments, at least one area with leader but no other participants

#### Test Data Generation
- **Extension of Existing Tool**: Enhance `utils/generate_test_participants.py`
- **Rate Limit Handling**: Batch requests with delays to stay under rate limits
- **Realistic Data**: Use area distributions that match actual usage patterns
- **Deterministic Output**: Consistent data generation for reproducible tests

#### ⚠️ **Critical Test Data Requirements (2025-09-27)**
**Name Sanitization Constraints:**
- **NEVER use numbers in participant names**: Input sanitization strips numbers from names, causing identity conflicts
- **Use alphabetic-only names**: Test names like `Parent1`, `Child1` become `Parent`, `Child` after sanitization
- **Identity conflict prevention**: Sanitized names must remain unique (e.g., `Mom`, `Dad`, `Alice`, `Bob`)
- **Family scenarios**: Use distinct alphabetic names for family members sharing email addresses

**Root Cause**: The `sanitize_name()` function in `services/security.py` removes numbers for security, causing test data with numeric suffixes to create duplicate identities.

**Correct Test Pattern**:
```python
# ❌ WRONG - Numbers stripped, causes conflicts
family_members = [
    {'name': 'Parent1', 'email': 'family@example.com'},
    {'name': 'Parent2', 'email': 'family@example.com'}
]
# After sanitization: Both become 'Parent' with same email = conflict

# ✅ CORRECT - Alphabetic names remain unique
family_members = [
    {'name': 'Mom', 'email': 'family@example.com'},
    {'name': 'Dad', 'email': 'family@example.com'}
]
# After sanitization: 'Mom' and 'Dad' remain distinct
```

### Authentication Testing

#### Test Accounts (Google Workspace)
- **Admin Accounts**:
  - `cbc-test-admin1@naturevancouver.ca`
  - `cbc-test-admin2@naturevancouver.ca`
- **Leader Account**:
  - `cbc-test-leader1@naturevancouver.ca`

**Note**: Test account passwords must be provided separately when resuming development. Passwords are NEVER stored in version-controlled files.

#### OAuth Integration
- **Real OAuth Flow**: Test against actual Google Identity Services with automated consent handling
- **Firefox WebDriver**: Selenium-based authentication using Firefox for OAuth stability
- **Automated Flow**: Handles email entry, password entry, and consent screen automatically
- **Role Verification**: Confirm admin whitelist and leader database access
- **Session Management**: Test login persistence and role-based redirects

## Test Suite Scope

### Phase 1: Critical Workflows (Priority)

#### Registration Flow Testing
**Requirements:**
- Valid participant registration with all field types
- Form validation and error handling (client and server-side)
- FEEDER participant constraints (no UNASSIGNED, no leadership interest)
- Form data preservation during navigation to info pages (`/area-leader-info`, `/scribe-info`)
- Basic map functionality (area clicking, dropdown synchronization)
- Duplicate email prevention within same year
- Registration success confirmation

**Critical Bug Prevention:**
- Data integrity across registration types (regular vs FEEDER)
- Required field validation
- Area assignment validation

#### Data Consistency Testing
**Requirements:**
- Leader promotion → deletion → re-addition workflow validation
- Participant/leader record synchronization within single-table design
- Leadership flag consistency (`is_leader` and `assigned_area_leader` fields)
- Data consistency after various admin operations in single-table architecture

**Critical Bug Prevention (Clive Roberts Scenario):**
- Promote participant to leader → delete leader → re-add participant → verify promotion availability
- Ensure leader deletion properly resets leadership flags in participant record
- Validate participant leadership status remains synchronized with area assignments

#### Identity-Based Data Management Testing
**Requirements:**
- **Family email sharing scenarios**: Multiple family members with same email address
- **Identity-based leader operations**: Create, update, delete using `(first_name, last_name, email)` tuple
- **Single-table leadership management**: Leadership stored as flags in participant records
- **Duplicate prevention using identity matching**: Prevent same person duplicates while allowing family members
- **Identity-based data consistency**: Ensure operations work correctly with shared emails in single-table design
- **Identity isolation**: Operations on one family member don't affect others sharing same email

**Critical Bug Prevention (Family Email Support):**
- Participant deletion → proper cleanup of leadership flags using identity matching (not email-only)
- Leader assignment duplicate prevention by identity (allowing family members with shared email)
- Participant display deduplication using identity tuples (not email-only matching)
- Authentication privilege sharing among family members (by design)
- Email-only operation failures prevented through identity-based validation

**Test Scenarios:**
- Create family with shared email → promote different members to leaders → verify independent management
- Delete participant who is leader → verify leadership flags properly reset → verify other family members unaffected
- Attempt duplicate leader assignment → verify prevention for same person → verify allowance for different family members
- Admin interface display → verify family members show separately despite shared email
- CSV export validation → verify family members export correctly with shared email in single-table format

### Phase 2: Admin Operations

#### Authentication & Dashboard Testing
**Requirements:**
- OAuth flow completion with test accounts
- Admin whitelist enforcement
- Dashboard functionality with empty vs populated database
- Year selector operations
- Basic admin navigation

#### CSV Export Validation (Primary Validation Mechanism)
**Requirements:**
- Schema validation (headers, field types, required fields)
- Sorting order verification (area → participation type → first name)
- Content validation against known datasets from `tests/fixtures/test_participants_2025.csv`
- Large dataset export performance (350+ participants)
- Field completeness (all defined fields present with proper defaults)
- Data accuracy (exported data matches database state)
- Route accessibility testing (`/admin/export_csv`)

**Test Data Source:**
- **Fixture File**: `tests/fixtures/test_participants_2025.csv` (347 participants)
- **Loading**: Automated via `tests/utils/load_test_data.py`
- **Database Cleanup**: Test environment cleared before loading fixture data
- **Validation**: All 347 fixture participants verified present in CSV export with correct data

**Performance Optimization:**
- **Shared CSV Download**: Single OAuth login and CSV download shared across multiple validation tests
- **Session Caching**: Downloaded CSV cached in pytest session to eliminate redundant downloads
- **Browser Download Handling**: Firefox configured with dedicated download directory (`tests/tmp/downloads/`)
- **Download Detection**: File comparison before/after navigation to detect new downloads
- **Timeout Handling**: Short page load timeout (3s) for file downloads with expected timeout exceptions

**Validation Approach:**
- Hybrid validation combining schema checks with content verification
- Complete record matching by email with name validation
- Missing participant detection and reporting
- Field-level validation for data types and business rules
- Cross-reference with database state for accuracy
- Performance testing with realistic data volumes

#### Participant Management Testing
**Requirements:**
- View all participants by area
- Participant area reassignment workflows (regular participants and leaders)
- Leader reassignment with leadership retention options
- Delete operations with confirmation
- Search and filtering functionality
- Leader promotion from participant list
- FEEDER vs regular participant display

**Reassignment Workflow Testing (Completed 2025-10-07):**
- Regular participant reassignment to different area
- Leader reassignment with leadership decline via "Team Member" button in Bootstrap modal
- Leader reassignment with leadership acceptance via "Leader" button in Bootstrap modal
- Validation preventing reassignment to same area (JavaScript alert)
- Reassignment cancellation workflow
- Database integrity verification after reassignment operations
- Leadership flag synchronization during area changes
- **UI Update**: Bootstrap modal with three explicit buttons ("Cancel", "Team Member", "Leader") replaces confusing confirm() dialog
- **All 5 tests passing**: Complete test suite validates all reassignment workflows including new modal UI

### Phase 3: Security & Edge Cases

#### Security Testing
**Requirements:**
- Input sanitization validation with malicious patterns
- Email validation security (percent sign and exclamation mark rejection)
- CSRF protection on admin forms
- Rate limiting behavior (ensure doesn't interfere with test execution)
- XSS prevention in template rendering

**Email Validation Security Testing:**
- Plus sign support validation (`user+tag@example.com`)
- Percent sign rejection (`user%name@example.com`)
- Exclamation mark rejection (`user!name@example.com`)
- RFC 5322 compliance verification
- Python/JavaScript validation consistency

**Malicious Input Patterns:**
- Script injection attempts (`<script>`, `javascript:`)
- SQL injection patterns (though Firestore is NoSQL)
- Path traversal attempts
- Oversized input testing

#### Race Condition Testing
**Requirements:**
- Two admins editing same participant simultaneously
- Admin editing participant while leader promotion/demotion occurs
- Concurrent leader management operations
- Data consistency validation after concurrent operations

#### Error Handling & Recovery
**Requirements:**
- Graceful handling when Firestore temporarily unavailable
- User-friendly error messages vs crash behavior
- Admin interface behavior with invalid data states
- Database connection recovery testing

## Error Handling & Robustness

### Network Resilience
- **Retry Logic**: 3 attempts with exponential backoff (1s, 2s, 4s delays)
- **Timeout Management**: 30-second timeouts for web requests
- **Cold Start Handling**: Wait for Cloud Run instance warm-up
- **OAuth Retry**: Handle OAuth flow intermittent failures

### Database Robustness
- **Connection Monitoring**: Verify Firestore availability before tests
- **State Validation**: Confirm database state matches expectations
- **Recovery Testing**: Behavior when database becomes available after outage

## Test Reporting & Execution

### Reporting Requirements
- **Console Output**: Verbose pytest output with clear pass/fail per test
- **HTML Reports**: Detailed reports for review and sharing (`pytest-html`)
- **Test Timing**: Performance metrics for slow operations
- **Failure Details**: Comprehensive error information for debugging

### Execution Strategy
- **Individual Test Execution**: Support running single tests for debugging
- **Fast Feedback**: Critical workflows tested first
- **Parallel Execution**: Where possible, run independent tests concurrently
- **Manual Execution**: No CI integration required initially

## Future Development & Deferred Features

### Email System Testing (Deferred - Current Implementation Incomplete)
**Future Requirements:**
- Email content validation using test email routes
- Automated email trigger testing
- Email delivery verification in test mode
- Template rendering validation

**Implementation Notes:**
- Current email system uses SMTP, needs Google Cloud Email API
- Test mode redirects emails to `birdcount@naturevancouver.ca`
- Manual trigger buttons available in admin dashboard (test server only)

### Advanced Testing Features (Deferred)

#### Rate Limiting Testing
- Validate rate limiting doesn't interfere with test execution
- Test rate limit enforcement under load
- Verify TEST_MODE higher limits (50/minute vs 10/minute)

#### Year Transition Testing
- Behavior around New Year's Day transitions
- Admin year selector with non-existent years
- Data isolation between years validation
- Historical data access patterns

#### Cross-Year Data Validation
- Historical data remains untouched during current year operations
- Email deduplication across multiple years
- Read-only access enforcement for historical years

#### Advanced Error Scenarios
- Invalid area codes in database handling
- Area leaders with invalid area assignments
- Database schema migration testing

#### Monkey Testing
- Randomized user action testing with data consistency validation
- Complex workflow combinations
- Stress testing with rapid user actions

### Map Integration Testing (Lower Priority)
- **Basic Functionality**: Area clicking, dropdown synchronization
- **Advanced Features**: Polygon rendering, color coding, tooltip display
- **Mobile Interaction**: Touch-based map interactions
- **Fallback Behavior**: Map failure graceful degradation

### Performance & Scalability Testing
- Large dataset handling (1000+ participants)
- Concurrent user simulation
- Database query optimization validation
- Cloud Run scaling behavior

### Browser Compatibility Testing
- Cross-browser testing (Firefox primary, Chrome has OAuth issues)
- Mobile browser testing
- JavaScript disabled scenarios
- Accessibility compliance testing

## Implementation Strategy

### Development Approach
1. **Framework Setup**: Create basic test configuration and utilities
2. **Working Example**: Implement basic registration test to validate approach
3. **Incremental Build**: Add utilities and infrastructure as needed for additional tests
4. **Iterative Refinement**: Expand test coverage based on discovered requirements

### Technical Stack
- **Testing Framework (Python)**: pytest with fixtures and parametrization
- **Testing Framework (JavaScript)**: Jest for frontend unit tests
- **Browser Automation**: Selenium WebDriver with Firefox (Chrome has OAuth stability issues)
- **HTTP Requests**: requests library for API testing
- **Database**: google-cloud-firestore client for direct database operations
- **Reporting**: pytest-html for detailed test reports
- **Retry Logic**: tenacity library for robust network operations

### ⚠️ **Element Selector Best Practices (2025-09-27)**
**Selector Ordering Strategy:**
- **Order selectors by success probability**: Place most reliable selectors first in lists
- **Specific before generic**: Use targeted selectors (IDs, data attributes) before broad patterns
- **Cross-browser compatibility**: Test Firefox compatibility (primary) and avoid Chrome-specific selectors

**Browser Compatibility Issues:**
- **Firefox CSS limitations**: `:contains()` pseudo-class not supported in Firefox CSS selectors
- **XPath alternative**: Use `//h1[contains(text(), "Dashboard")]` instead of `h1:contains("Dashboard")`
- **Selector fallback pattern**: Provide multiple selector alternatives ordered by reliability

**Correct Selector Pattern**:
```python
# ✅ CORRECT - Ordered by success probability
dashboard_selectors = [
    'dashboard-title',                                    # Most specific - ID/data attribute
    (By.XPATH, '//h1[contains(text(), "Dashboard")]'),   # Cross-browser XPath
    (By.CSS_SELECTOR, '.admin-dashboard'),               # CSS class fallback
    (By.PARTIAL_LINK_TEXT, 'Dashboard')                  # Generic fallback
]

# ❌ WRONG - Browser-specific selector first
dashboard_selectors = [
    (By.CSS_SELECTOR, 'h1:contains("Dashboard")'),       # Firefox incompatible
    'dashboard-title'                                     # Should be first priority
]
```

**Root Cause**: Firefox WebDriver doesn't support CSS `:contains()` pseudo-class, causing element detection failures in tests that worked during development with different browser configurations.

### Dependencies & Setup
- Full requirement specification in test-specific requirements file
- Browser installation and PATH configuration instructions
- Google test account setup and Secret Manager configuration
- Test environment verification procedures

## Success Criteria

### Primary Objectives
1. **Regression Prevention**: Catch data integrity bugs like the Clive Roberts leader management issue
2. **Workflow Validation**: Ensure critical user flows work end-to-end
3. **CSV Export Accuracy**: Validate primary data export mechanism
4. **Admin Interface Stability**: Prevent admin workflow disruptions

### Quality Metrics
- **Coverage**: All critical workflows have automated tests
- **Reliability**: Tests pass consistently in cloud environment
- **Maintainability**: Test suite can be updated when features change
- **Documentation**: Clear setup and execution instructions

### Risk Mitigation
- **Production Bug Prevention**: Reduce bugs discovered by admins in production
- **Feature Development Safety**: Confident code changes without breaking existing functionality
- **Data Integrity Assurance**: Comprehensive validation of single-table operations
- **User Experience Protection**: Ensure UI workflows remain functional

## Critical Bug Fixes and Lessons Learned (2025-09-27, Updated 2025-09-30)

### ✅ **Resolved Critical Issues**
**Test Framework Timeout Resolution:**
- **Issue**: Tests timing out at 2 minutes during execution
- **Root Cause**: Claude Code Bash tool default 2-minute timeout, not pytest timeout
- **Solution**: Use `timeout=600000` (10 minutes) parameter in Bash tool calls
- **Lesson**: Distinguish between tool limitations and application timeouts

**Email Validation Centralization and Security (2025-09-30):**
- **Issue**: Email validation inconsistent across forms, plus signs rejected, security gaps
- **Root Cause**: 6 different validation implementations, plus sign missing from regex
- **Solution**:
  - Created centralized `services/security.py::validate_email_format()`
  - Created matching `static/js/validation.js::validateEmailFormat()`
  - Added security restrictions rejecting percent (%) and exclamation (!) characters
  - Comprehensive test suite with 51 Python tests and 81 JavaScript tests
- **Locations**:
  - Backend: `services/security.py:149-228`
  - Frontend: `static/js/validation.js:33-97`
  - Python tests: `tests/test_email_validation.py`
  - JavaScript tests: `tests/email_validation.test.js`
- **Lesson**: Centralize validation logic, ensure Python/JavaScript consistency, comprehensive test coverage prevents regression

**Browser Compatibility - CSS Selector Issues:**
- **Issue**: Firefox doesn't support `:contains()` pseudo-class in CSS selectors
- **Root Cause**: CSS selectors like `h1:contains("Dashboard")` invalid in Firefox
- **Solution**: Replaced with XPath selectors: `//h1[contains(text(), "Dashboard")]`
- **Files**: `tests/page_objects/admin_dashboard_page.py`, `admin_participants_page.py`
- **Lesson**: Always test selectors in target browser, provide XPath alternatives

**Name Sanitization Identity Conflicts:**
- **Issue**: Family registration tests failing with identical participant names
- **Root Cause**: Names with numbers (`Parent1`, `Child1`) sanitized to remove numbers
- **Solution**: Use alphabetic-only names (`Mom`, `Dad`, `Alice`, `Bob`) in test data
- **Files**: `tests/test_family_email_scenarios.py`
- **Lesson**: Test data must account for application security sanitization

**Experience Field UI Bug:**
- **Issue**: Experience field displayed as text input instead of dropdown
- **Root Cause**: Template used `<input type="text">` instead of `<select>`
- **Solution**: Fixed frontend template and added backend validation
- **Files**: `templates/admin/participants.html:182-188`, `routes/admin.py`
- **Lesson**: UI field types must match specification, require both frontend and backend fixes

### 🔧 **Test Development Patterns Established**
**Systematic Bug Investigation:**
1. Reproduce issue in test environment
2. Identify root cause through code inspection
3. Apply minimal targeted fix (avoid speculative changes)
4. Verify fix resolves specific issue without side effects
5. Document lesson learned for future sessions

**Element Detection Strategy:**
1. Start with most specific selectors (IDs, data attributes)
2. Provide cross-browser compatible alternatives (XPath)
3. Test in actual target browser (Firefox primary)
4. Order selectors by success probability

**Test Data Generation Guidelines:**
1. Use alphabetic-only names to avoid sanitization conflicts
2. Create realistic family scenarios with shared emails
3. Generate unique identities that survive input sanitization
4. Test identity-based operations with proper tuples

## Test Implementation Status (Updated 2025-10-06)

### ✅ **Completed and Verified**
**Email Validation Test Suite (132 tests passing)**:
- **Python Backend Tests (51 tests)**: `tests/test_email_validation.py`
  - Valid email acceptance (17 tests including plus sign support)
  - Invalid email rejection (22 tests including security restrictions)
  - Length limits, TLD requirements, subdomain support
  - Security restrictions (percent/exclamation rejection)
  - Real-world email patterns
- **JavaScript Frontend Tests (81 tests)**: `tests/email_validation.test.js`
  - Mirrors Python test suite for consistency validation
  - Runs locally with Jest (no server required)
  - Validates `static/js/validation.js::validateEmailFormat()`
  - Confirms Python/JavaScript validation consistency

**Core Registration Tests (4/4 passing)**:
- Single-table participant registration for all types (regular, FEEDER, leadership candidates, scribes)
- Form validation and success page verification
- Database integration with single-table design
- Equipment preferences and role interests

**Admin Infrastructure Tests (9/9 passing)**:
- OAuth authentication flow automation with error handling
- Admin participant management interface validation
- Page object model for participant table parsing
- Database state cleanup and test isolation

**OAuth Authentication System (Complete)**:
- **Working OAuth Flow**: Google OAuth automation with popup error handling and automatic dismissal
- **Performance Optimization**: Reduced timeouts from 15s to 5s maximum per operation
- **Code Consolidation**: Shared `admin_login_for_test()` function eliminates duplication across test files
- **Error Resilience**: Automatic error dialog detection and dismissal, authentication retry logic
- **Test Account Integration**: Seamless integration with Google Secret Manager credentials

**Key Technical Solutions Implemented**:
- **Element Interaction Framework**: `safe_click()` helper function resolves ElementClickInterceptedException
- **Success Verification Framework**: `verify_registration_success()` validates URL-based success and database creation
- **Import Path Resolution**: Project root path setup for test file imports
- **Single-Table Validation**: Comprehensive verification of leadership flags and participation types
- **Page Object Robustness**: Fixed table parsing for mixed participant types and column structure variations

### ✅ **OAuth Infrastructure Complete**
**Authentication Consolidation (2025-09-26)**:
- Eliminated duplicate `_admin_login` functions across multiple test files
- Centralized OAuth logic in `tests/utils/auth_utils.py` with `admin_login_for_test()` function
- Updated all OAuth-dependent tests to use shared authentication mechanism
- Automatic error popup handling reduces manual intervention to zero
- Performance improved 6x (from 15+ seconds to under 5 seconds per operation)

**Test Files Updated with Consolidated OAuth**:
- `test_admin_participant_management.py` - 9 tests passing with shared OAuth
- `test_single_table_regression.py` - Updated to use consolidated authentication
- `test_csv_export_workflows.py` - Updated authentication flow
- `test_participant_reassignment.py` - 5 comprehensive reassignment workflow tests
- All admin workflow tests now use `admin_login_for_test()` from auth_utils

### ✅ **Minimal Functional Test Suite (Foundation Established)**
**Basic Admin Functionality Validation (6 functional tests operational - starting point for comprehensive coverage)**:
1. **✅ Admin Authentication & Dashboard Access** - OAuth flow and basic dashboard loading verified
2. **✅ Participant Search & Filtering** - Core search functionality smoke test
3. **✅ Participant Editing with Field Preservation** - Basic field preservation validation
4. **✅ Leader Promotion & Demotion Workflow** - Leader management functions smoke test
5. **✅ Area Assignment Changes** - Participant area reassignment basic validation
6. **✅ Basic CSV Export Functionality** - Data export functionality smoke test

**Implementation**: `test_admin_core_functionality.py` with basic functional testing framework
**Scope**: Minimal validation of critical admin workflows - foundation for expanding test coverage
**Performance**: 6 smoke tests execute in 3.5 minutes (proves framework efficiency)
**Framework Status**: Test infrastructure operational with OAuth, database integration, and page objects working
**Purpose**: Proof of concept successful - provides foundation for comprehensive test suite development

**Test Framework Infrastructure Completed (2025-09-26)**:
- **OAuth Integration**: Google OAuth automation with error handling operational
- **Database Operations**: Firestore integration with proper cleanup working
- **Page Object Model**: Element interaction framework with optimized selector strategies
- **Selector Optimization**: Direct tuple selectors `(By.ID, 'element')` with 0.5s timeouts to eliminate multi-strategy delays
- **Page Load Detection**: Optimized `is_*_loaded()` methods in page objects to prevent 30+ second timeout delays
- **Bug Fixes Applied**: Timeout, method name, and element interaction issues resolved
- **Execution Pipeline**: Reliable test execution environment established

### ✅ **Participant Reassignment Tests (Completed 2025-10-07)**
**Comprehensive Reassignment Workflow Testing (5 tests - All Passing)**:
- **Test File**: `tests/test_participant_reassignment.py`
- **Test Data**: Uses 347 participants from `tests/fixtures/test_participants_2025.csv`
- **Module-Scoped Fixture**: Single database load per test file execution for efficiency
- **Coverage**:
  1. Regular participant reassignment (Area A → C) - Non-leader workflow
  2. Leader reassignment declining new leadership (Area B → D) - Clicks "Team Member" button in Bootstrap modal
  3. Leader reassignment accepting new leadership (Area D → E) - Clicks "Leader" button in Bootstrap modal
  4. Validation error for same-area reassignment (Area F → F) - JavaScript alert prevents modal
  5. Reassignment cancellation workflow (Area G) - Tests UI state restoration
- **Validation**: Database state verification, leadership flag synchronization, UI workflow correctness
- **UI Implementation**:
  - **Bootstrap Modal**: Replaced confusing confirm() dialog with clear 3-button modal
  - **Modal Buttons**: "Cancel" (no changes), "Team Member" (move without leadership), "Leader" (move with leadership)
  - **Modal Message**: Shows participant name and area transition clearly
  - **JavaScript Integration**: Modal handling via `bootstrap.Modal` API
- **Test Implementation**:
  - Tests updated to interact with Bootstrap modal elements by ID
  - Browser window resizing (+500px width) ensures buttons visible
  - ActionChains for reliable button clicks
  - Success alert handling after reassignment operations
  - Method name fixes: `get_participant_by_email_and_names()` for identity-based queries
- **Execution**: All 5 tests pass individually and as complete suite (2m 31s total)

**Next Steps for Comprehensive Coverage**:
- Expand from 6 smoke tests to comprehensive scenario coverage
- Add edge case validation and error condition testing
- Implement security testing and race condition validation
- Develop performance testing under load conditions

### 🔧 **Test Framework Improvements**
**Reliability Enhancements**:
- Robust element clicking with scroll-into-view and wait conditions
- URL-based success verification (more reliable than DOM inspection)
- Comprehensive database state validation using actual participant IDs
- Consistent error handling and debugging output
- Page object model handles mixed participant types and table structure variations

**Authentication Strategy**:
- OAuth automation via `tests/utils/auth_utils.py` with consolidated shared functions
- Test account credentials in Google Secret Manager
- Authentication failure results in test skip (not failure) for better reporting
- Automatic error dialog handling eliminates manual intervention

---

This specification provides the foundation for implementing a comprehensive functional test suite that prioritizes the most critical aspects of the Christmas Bird Count registration system while establishing a framework for future test development.