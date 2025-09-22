# Christmas Bird Count Registration Test Suite Specification
{# Updated by Claude AI on 2025-09-22 #}

## Overview

This document defines the requirements and scope for a comprehensive functional test suite for the Christmas Bird Count registration system. The test suite prioritizes workflow validation, data integrity testing, and CSV export verification to prevent regression bugs in critical user flows.

## Core Requirements

### Testing Environment
- **Target Platform**: Cloud-based testing against `cbc-test.naturevancouver.ca`
- **Database**: Test instance uses `cbc-test` Firestore database (isolated from production)
- **Year Strategy**: Use current year for functional testing, year 2000 for historical/isolation testing
- **Authentication**: Real Google OAuth with dedicated test accounts
- **Browser Support**: Primary testing with Chrome, designed for cross-browser compatibility

### Test Suite Architecture

#### Configuration Management
```
tests/
├── config.py                 # Non-sensitive test configuration
├── conftest.py              # Pytest fixtures and setup
├── utils/                   # Test utilities and helpers
│   ├── database_utils.py    # Database state management
│   ├── auth_utils.py        # OAuth automation helpers
│   └── dataset_generator.py # Test data creation utilities
└── test_*.py               # Individual test modules
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
- **State Reset**: Clear year 2000 + current year collections between test scenarios
- **Isolation**: Tests must not depend on execution order or previous test outcomes

#### Test Dataset Requirements
1. **Small Dataset**: ~50 participants, 40% of areas have assigned leaders
2. **Large Dataset**: ~350 participants (realistic production scale)
3. **Edge Case Datasets**: All areas assigned, some areas empty, single participant per area
4. **Realistic Distribution**: Uneven area assignments, at least one area with leader but no participants

#### Test Data Generation
- **Extension of Existing Tool**: Enhance `utils/generate_test_participants.py`
- **Rate Limit Handling**: Batch requests with delays to stay under rate limits
- **Realistic Data**: Use area distributions that match actual usage patterns
- **Deterministic Output**: Consistent data generation for reproducible tests

### Authentication Testing

#### Test Accounts (Google Workspace)
- **Admin Accounts**:
  - `cbc-test-admin1@naturevancouver.ca`
  - `cbc-test-admin2@naturevancouver.ca`
- **Leader Account**:
  - `cbc-test-leader1@naturevancouver.ca`

**Note**: Test account passwords must be provided separately when resuming development. Passwords are NEVER stored in version-controlled files.

#### OAuth Integration
- **Real OAuth Flow**: Test against actual Google Identity Services
- **Automated Browser**: Selenium-based authentication with retry logic
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
- Participant/leader record synchronization across collections
- Deletion operations properly remove from both `participants_YYYY` and `area_leaders_YYYY`
- Data consistency after various admin operations

**Critical Bug Prevention (Clive Roberts Scenario):**
- Promote participant to leader → delete leader → re-add participant → verify promotion availability
- Ensure leader deletion removes from both collections
- Validate participant/leader data remains synchronized

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
- Content validation against known datasets
- Large dataset export performance (350+ participants)
- Field completeness (all defined fields present with proper defaults)
- Data accuracy (exported data matches database state)

**Validation Approach:**
- Hybrid validation combining schema checks with content verification
- Field-level validation for data types and business rules
- Cross-reference with database state for accuracy
- Performance testing with realistic data volumes

#### Participant Management Testing
**Requirements:**
- View all participants by area
- Participant assignment and reassignment
- Delete operations with confirmation
- Search and filtering functionality
- Leader promotion from participant list
- FEEDER vs regular participant display

### Phase 3: Security & Edge Cases

#### Security Testing
**Requirements:**
- Input sanitization validation with malicious patterns
- CSRF protection on admin forms
- Rate limiting behavior (ensure doesn't interfere with test execution)
- XSS prevention in template rendering

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
- Cross-browser testing (Chrome, Firefox, Safari, Edge)
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
- **Testing Framework**: pytest with fixtures and parametrization
- **Browser Automation**: Selenium WebDriver with Chrome
- **HTTP Requests**: requests library for API testing
- **Database**: google-cloud-firestore client for direct database operations
- **Reporting**: pytest-html for detailed test reports
- **Retry Logic**: tenacity library for robust network operations

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
- **Data Integrity Assurance**: Comprehensive validation of multi-collection operations
- **User Experience Protection**: Ensure UI workflows remain functional

---

This specification provides the foundation for implementing a comprehensive functional test suite that prioritizes the most critical aspects of the Christmas Bird Count registration system while establishing a framework for future test development.