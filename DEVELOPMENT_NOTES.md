# Christmas Bird Count Registration System - Development Notes
{# Updated by Claude AI on 2025-09-29 #}

## Current Development Status (As of 2025-09-29)

### 🔄 Major Architecture Change (2025-09-23)

The application has undergone a **complete architecture migration** from a dual-table design to a clean single-table design. This eliminates the complex synchronization logic and data management issues that were complicating development.

**Before (Dual-Table):**
- `participants_YYYY` - Regular registrations
- `area_leaders_YYYY` - Leadership assignments
- Complex synchronization between tables
- Dual-source data merging in admin interfaces
- Bidirectional sync bugs and data consistency issues

**After (Single-Table):**
- `participants_YYYY` only - All data in one collection
- Leadership tracked via `is_leader` flag and leadership fields
- No synchronization needed - single source of truth
- Clean, maintainable code with no data duplication

**Impact on Development Plans:**
Many of the planned features below are now **simplified or obsolete** due to the single-table design. Complex dual-source data handling is no longer needed.

### ✅ Recently Completed Features

#### 1. Leader Dashboard Implementation (2025-09-29)
- **Feature**: Read-only area leader dashboard at `/leader` route
- **Purpose**: Allow area leaders to view their team roster and participant details
- **Access Control**: Requires Google OAuth authentication and `is_leader=True` in participant records
- **Content**: Displays leader's contact info, team summary, and complete roster matching admin/participants layout
- **Layout**:
  - Leader information card with contact details
  - Team summary showing total, regular, and FEEDER participant counts
  - Separate tables for regular and FEEDER participants
  - Full notes visible (no truncation) for mobile readability
  - Same columns as admin interface: Name, Email, Cell Phone, Skill Level, Experience, Equipment, Notes, Leader Interest, Scribe Interest
- **Future Enhancement**: Historical data view (3-year lookback) deferred - see pending features below
- **Navigation**: Leader-branded navbar ("Vancouver CBC Area Leader")
- **Files Created**: routes/leader.py (simplified single-route implementation), templates/leader/dashboard.html
- **Files Modified**: templates/base.html (added leader context navigation)

#### 2. Single-Table Architecture Migration (2025-09-23)
- **Major Refactoring**: Converted from dual-table design (participants + area_leaders) to clean single-table design
- **Problem Solved**: Eliminated complex dual-table synchronization, data duplication, and consistency issues
- **Root Issue**: Dual tables created synchronization bugs, complex deduplication logic, and maintenance overhead
- **Solution**: Unified all data in `participants_YYYY` collections with integrated leadership fields
- **Implementation**:
  - Added leadership fields to ParticipantModel: `is_leader`, `assigned_area_leader`, `leadership_assigned_by/at`, `leadership_removed_by/at`
  - Replaced AreaLeaderModel completely with ParticipantModel methods: `get_leaders()`, `is_area_leader()`, `assign_area_leadership()`
  - Updated all routes to use single model: admin.py, auth.py, api.py, leader.py, main.py
  - Removed inappropriate auto-assignment logic from registration (leadership now admin-only)
  - Simplified authentication to check `is_leader` flag in participant records
- **Result**: Clean, maintainable single-source-of-truth architecture with no synchronization complexity
- **Files Modified**: All route files, models/participant.py, eliminated models/area_leader.py
- **Benefit**: Simplified maintenance, eliminated synchronization bugs, cleaner data model

#### 2. Secondary Phone Number Field Implementation (2025-09-16)
- **Registration Form**: Added optional secondary phone field labeled "Secondary Phone Number"
- **Primary Phone**: Relabeled to "Cell Number" for clarity
- **Data Model**: Added `phone2` field to participant model with validation
- **Admin Interface**: Displays secondary phone when present, hidden when empty
- **Email Templates**: Updated to include secondary phone information
- **Validation**: Same 20-character limit as primary phone with sanitization
- **Security**: Secondary phone included in suspicious input checking
- **CSV Export**: Automatically includes phone2 field with proper defaults

#### 2. Shared Email Address Support (2025-09-16)
- **Problem Solved**: Multiple participants can now share the same email address (household registrations)
- **Uniqueness Constraint**: Changed from email-only to email+name combination
- **Database Index**: Added composite index for email+first_name+last_name in `setup_databases.py`
- **Validation**: Updated `validate_skill_level()` to match form options (Newbie, Beginner, Intermediate, Expert)
- **Use Case**: Couples or families can register with shared email as long as names differ

#### 3. Centralized Field Management System (Updated for Single-Table 2025-09-23)
- **Updated Architecture**: `config/fields.py` now handles unified participant fields including leadership data
- **Schema Evolution Safety**: New fields guaranteed to appear in all outputs
- **Field Definitions**: Single set of ordered fields with defaults, display names, and CSV ordering
- **Normalization Function**: `normalize_participant_record()` handles all data including leadership fields
- **CSV Export Enhancement**: Uses explicit field enumeration for consistent participant exports
- **Problem Solved**: Eliminates risk of missing fields in CSV exports, simplified by single-table design
- **Admin Interface**: Single normalized data structure for all participant records

#### 4. Email Generation Logic
- **Location**: `test/email_generator.py` (moved from `utils/` for security)
- **Three Email Types**: Team updates, weekly summaries, admin digest
- **Features**: 
  - Change detection logic with participant diff tracking
  - Race condition prevention via timestamp management
  - Error handling and logging
  - Flask app context support for template rendering

#### 2. Environment-Based Security
- **Test Routes**: Only registered when `TEST_MODE=true` 
- **Production Safety**: Routes completely absent from production servers
- **Implementation**: Conditional route registration in `routes/admin.py`
- **Admin Access**: Requires `@require_admin` decorator

#### 3. Timezone Support System
- **Configuration**: Single `DISPLAY_TIMEZONE` variable in `deploy.sh` 
- **Default**: `America/Vancouver` for Christmas Bird Count timing
- **Storage Strategy**: All calculations in UTC, display conversion available
- **Helper Functions**: In `config/settings.py` for timezone conversion
- **Deployment Visibility**: Shows configured timezone during deployment

#### 4. Email Templates
- **Location**: `templates/emails/`
- **Files**: `team_update.html`, `weekly_summary.html`, `admin_digest.html`
- **Features**: Responsive HTML with environment-aware links

#### 5. Test Interface
- **Location**: Admin dashboard at `/admin` (test server only)
- **Buttons**: Manual trigger for all three email types
- **Feedback**: JSON response with success/failure details
- **Logging**: Detailed logs for debugging in Cloud Run

### 🎯 Current Migration Priorities

#### 1. Data Migration Utility (In Progress)
- **Purpose**: Migrate existing `area_leaders_YYYY` data to unified `participants_YYYY` collections
- **Implementation**: Create utility in `utils/migrate_to_single_table.py`
- **Tasks**:
  - Read existing area leader records
  - Convert to participant format with `is_leader=True`
  - Map fields: `leader_email`→`email`, `cell_phone`→`phone`
  - Populate leadership tracking fields
  - Handle identity conflicts with existing participants

#### 2. Legacy Code Cleanup
- **Remove**: `models/area_leader.py` completely
- **Update**: Remaining imports in test files and email utilities
- **Clean**: Documentation references to dual-table architecture

#### 3. Template Updates
- **Simplify**: Admin participant management (no dual-source complexity)
- **Update**: Leader management to work with participant-based leadership
- **Enhance**: Unified edit/delete functionality for all participant records

#### 4. Test Suite Updates
- **Update**: Identity synchronization tests for single-table design
- **Remove**: Bidirectional sync tests (no longer applicable)
- **Add**: Leadership field management tests

#### 6. Security Implementation (Implemented, Not Yet Deployed)
- **Input Sanitization**: Created `services/security.py` with sanitization functions for names, emails, phone numbers, notes
- **CSRF Protection**: Implemented Flask-WTF across all forms (registration, admin interfaces)
- **Rate Limiting**: Added Flask-Limiter with TEST_MODE-aware configuration (50/min test, 10/min production for registration)
- **XSS Prevention**: Added HTML escaping throughout admin templates using `|e` filter
- **Security Integration**: Updated test script (`utils/generate_test_participants.py`) to fetch CSRF tokens with BeautifulSoup
- **Files Created**: `services/security.py`, `services/limiter.py`, `config/rate_limits.py`
- **Dependencies Added**: Flask-WTF, Flask-Limiter (main), beautifulsoup4 (utils)

**Implementation Decisions**:
- Used Flask-WTF for CSRF protection (integrates well with existing Flask app)
- TEST_MODE-aware rate limits to allow efficient testing while maintaining production security
- Security code in `services/` (deployed) not `utils/` (excluded by .gcloudignore)
- Chose to test full security stack rather than bypass it in test environment
- Input sanitization preserves data integrity while preventing injection attacks

### ❌ Pending Implementation

#### 1. Leader Dashboard Historical Data View (2025-09-29)
- **Purpose**: Allow area leaders to view historical participant data (3-year lookback) for recruitment purposes
- **Current Status**: Year selector exists in template but only current year available
- **Requirements**:
  - Add historical data query method to get participants from previous years
  - Implement email deduplication logic (show most recent data when person appears in multiple years)
  - Add year selector functionality to leader dashboard
  - Consider read-only indicator for historical years
  - Maintain same layout as current year view
- **Technical Approach**:
  - Use existing `ParticipantModel.get_historical_participants()` method
  - Query collections: `participants_2025`, `participants_2024`, `participants_2023`, etc.
  - Deduplicate by email (keep most recent participant record)
  - Display historical data with year badges or indicators
- **Data Utility**: Helps leaders recruit previous participants who haven't registered for current year
- **Priority**: Medium - useful for recruitment but not critical for initial leader dashboard launch

#### 2. Email Provider Configuration Flexibility (2025-09-29)
- **Current Issue**: Email provider is hardcoded as 'smtp2go' in deploy.sh
- **Impact**: Future installations with different email providers would require deploy script modifications
- **Solution Needed**: Make email provider selection configurable via environment variable or configuration file
- **Implementation Ideas**:
  - Move EMAIL_PROVIDER to a configuration file that can be customized per installation
  - Add deployment parameter to override email provider selection
  - Document email provider options and setup procedures for different providers
- **Priority**: Low - current SMTP2GO setup works for current installation needs

#### 2. Inline Edit/Delete Functionality for Participants Table (2025-09-17)

**Objective**: Add the same inline edit/delete functionality to the participants table that exists for the leaders table.

**Complexity**: Recent implementation (2025-09-17) that combines participants from two data sources complicates this:
- **Regular Participants**: From `participants_2025` collection (form registrations)
- **Leaders-as-Participants**: From `area_leaders_2025` collection (manually added leaders)

**Implementation Plan**:

**Phase 1: Template Updates** (`templates/admin/participants.html`)
- Replace simple delete button with edit/delete button group similar to leaders
- Add data attributes for source detection (`data-source="participant|leader"`) and original ID
- Add hidden edit inputs for key fields:
  - Name fields (first_name, last_name)
  - Email and phone (primary only for leaders)
  - Area assignment dropdown
  - Skill level and experience dropdowns
  - Equipment checkboxes (has_binoculars, spotting_scope)
  - Leadership/scribe interest checkboxes
- Add visual indicators to distinguish leader-sourced participants

**Phase 2: JavaScript Client-Side Logic** (`static/js/participants.js` - new file)
- Edit mode toggle functionality (show/hide edit controls)
- Data source routing (detect source type and format requests appropriately)
- Client-side field validation for required fields
- UI state management (edit/save/cancel states)
- Similar patterns to existing `leaders-map.js` implementation

**Phase 3: Backend API Routes** (`routes/admin.py`)
- **Update Participant Route**: `PUT /admin/edit_participant/<participant_id>`
  - Route to participant model for regular participants
  - Route to leader model for leader-sourced participants
  - Handle field mapping between different collection schemas
- **Enhanced Delete Route**: Extend existing `DELETE /admin/delete_participant/<participant_id>`
  - Add source detection and appropriate collection routing
  - Handle leader-participant synchronization for promoted leaders
  - Maintain audit trail with removal logging

**Phase 4: Data Synchronization Logic**
Handle four main scenarios:
1. **Edit Regular Participant**: Update `participants` collection only
2. **Edit Leader-as-Participant**: Update `area_leaders` collection, sync to `participants` if promoted
3. **Delete Regular Participant**: Remove from `participants`, log removal
4. **Delete Leader-as-Participant**: Remove from `area_leaders`, clean up `participants` if promoted

**Phase 5: Field Mapping Strategy**
Leader → Participant field mappings:
```
leader_email → email
cell_phone → phone
(no phone2 for leaders)
area_code → preferred_area
"Area Leader" → skill_level (read-only)
"Area Leader" → experience (read-only)
```

Editable fields by source:
- **Regular Participants**: All fields editable except `is_leader`
- **Leader-as-Participants**: Limited fields (name, email, phone, area only)

**Phase 6: Enhanced User Experience**
- Gray out non-editable fields for leader-sourced records
- Pre-populate dropdowns with current values
- Clear user feedback for validation errors
- Confirmation dialogs before deleting leaders or participants with special roles

**Business Logic Considerations**:
- Prevent deleting leaders with teams (offer conversion instead)
- Maintain data consistency between collections
- Preserve audit trail with removal logging
- Handle edge cases for promoted participants who become leaders

**Benefits**:
- **Unified Interface**: All participants editable from single location
- **Data Integrity**: Proper synchronization between collections
- **Admin Efficiency**: No need to switch between participants and leaders pages
- **Consistency**: Same UX pattern as existing leaders edit functionality

**Implementation Priority**: Deferred - requires significant development effort for complex dual-source data handling.

#### 2. Email Template Enhancement for Shared Addresses
- **Current Status**: Email templates show secondary phone but still send multiple emails to shared addresses
- **Enhancement Needed**: Combine participants with same email into single email with multiple names
- **Template Changes**: Update email generation to group by email address before sending
- **Addressing Format**: "Dear John and Jane Doe" instead of separate emails
- **Implementation**: Modify email generation logic in `test/email_generator.py`
- **Location**: Should be implemented in email branch, not main branch

#### 2. Google Cloud Email API Configuration
**Current Issue**: Email service uses SMTP but needs Google Cloud Email API

**Required Steps**:
1. Enable Google Cloud Email API in project console
2. Create service account with email permissions
3. Store credentials in Google Secret Manager
4. Update `services/email_service.py` to use Email API instead of SMTP
5. Remove SMTP-specific configuration

**Code Changes Needed**:
```python
# Replace in services/email_service.py
from google.cloud import email_v1

class EmailService:
    def __init__(self):
        self.client = email_v1.EmailServiceClient()
        # Remove SMTP-specific code
```

**Environment Variables to Remove**:
- `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_SERVER`, `SMTP_PORT`

**New Dependencies**:
- Add `google-cloud-email` to `requirements.txt`

#### 2. Production Automation
**Missing**: Cloud Scheduler configuration for automated triggers

**Required Components**:
- Cloud Scheduler jobs for twice-daily and weekly triggers
- Pub/Sub topics for reliable message delivery
- HTTP endpoints for scheduler to call (different from test routes)
- Monitoring and alerting for failed email deliveries

## Current Bug Status

### Fixed Issues ✅
1. **"No module named 'utils'"**: Fixed by moving to `test/` directory and adding `__init__.py`
2. **Timezone comparison errors**: Fixed by ensuring all datetime comparisons are timezone-aware
3. **Route security**: Test routes only exist in test mode

### Active Issues ❌

#### 1. Email Service Not Functional
- **Error**: `SMTP credentials not configured`
- **Cause**: Missing Google Cloud Email API setup
- **Impact**: Emails not delivered despite successful generation
- **Priority**: High - blocks end-to-end testing

#### 2. Limited Area Processing
- **Symptom**: Only 4 areas processed instead of 24 (A-X)
- **Likely Cause**: Only 4 areas currently have assigned leaders
- **Investigation Needed**: Check area leader data in Firestore
- **Query**: `area_leaders_2025` collection - verify leader distribution

#### 3. Error Handling Improvements
- **Current**: Email failures don't prevent function completion
- **Needed**: Better error propagation and retry logic
- **Impact**: Silent failures in production environment

## File Structure and Key Changes Made

### New/Modified Files
```
config/
  fields.py                   # NEW: Centralized field definitions with defaults and ordering
  settings.py                 # MODIFIED: Added timezone helper functions

models/
  participant.py              # MODIFIED: Added email_name_exists() validation method

routes/
  main.py                     # MODIFIED: Added phone2 field handling and email+name validation
  admin.py                    # MODIFIED: Updated CSV exports to use centralized field definitions

templates/
  index.html                  # MODIFIED: Added secondary phone field, relabeled primary to "Cell Number"
  admin/participants.html     # MODIFIED: Display secondary phone when present
  emails/*.html               # MODIFIED: Include secondary phone information

test/
  __init__.py                 # NEW: Package initialization
  email_generator.py          # MOVED: From utils/email_generator.py

services/
  __init__.py                 # NEW: Package initialization
  email_service.py            # MODIFIED: Needs Email API integration
  security.py                 # MODIFIED: Fixed validate_skill_level() to match form options

utils/
  setup_databases.py          # MODIFIED: Added composite index for email+first_name+last_name

deploy.sh                     # MODIFIED: Added DISPLAY_TIMEZONE configuration
requirements.txt              # MODIFIED: Added pytz dependency
```

### Security Changes
```python
# routes/admin.py - Conditional route registration
def register_test_email_routes():
    # Test routes defined here
    pass

# Only register when in test mode
if os.getenv('TEST_MODE', '').lower() == 'true':
    register_test_email_routes()
```

## Testing Status

### Current Test Results
```
Team Update: 0 emails sent, 4 areas processed
Weekly Summary: 0 emails sent, 4 areas processed  
Admin Digest: 1 unassigned participants, 0 emails sent
```

### Expected vs Actual
- **Expected**: 24 areas (A-X) with varying leader counts
- **Actual**: Only 4 areas have leaders assigned
- **Email Delivery**: 0% success rate due to missing Email API

### Test Mode Verification
- ✅ Routes only exist on test server
- ✅ All emails would redirect to `birdcount@naturevancouver.ca`
- ✅ Timezone handling works correctly
- ❌ Email delivery fails at SMTP stage

## Next Development Session Tasks

### Immediate Priority (Database Index Creation & Testing)
1. **Deploy database index** for email+name uniqueness: `python utils/setup_databases.py`
2. **Test shared email registration** - verify multiple participants can share email with different names
3. **Verify phone2 field** in admin interface and CSV exports
4. **Test validation fixes** - ensure "Newbie" skill level validates correctly

### Immediate Priority (Security Deployment & Testing)
1. **Deploy security changes** to test environment (`./deploy.sh test`)
2. **Test CSRF protection** - verify registration form requires valid CSRF token
3. **Test rate limiting** - verify limits work correctly on Cloud Run infrastructure
4. **Test updated test script** - ensure CSRF token fetching works with BeautifulSoup
5. **Validate input sanitization** - check that malicious inputs are properly cleaned
6. **Monitor security logs** - check for any rate limit violations or security events

### Secondary Priority (Email API Setup)
1. **Enable Google Cloud Email API** in project console
2. **Create service account** with necessary permissions
3. **Update email service** to use Cloud Email API
4. **Test email delivery** end-to-end
5. **Verify test mode** redirects work correctly

### Secondary Priority (Data Investigation)
1. **Investigate area leader distribution** - why only 4 areas?
2. **Add better error handling** for email failures
3. **Improve logging** for debugging email issues
4. **Test with more realistic data** distribution

### Bug: Missing Area Y Boundary Data (2025-09-15)
- **Issue**: `static/data/area_boundaries.json` contains 24 areas (A-X) but `config/areas.py` defines 25 areas (A-Y)
- **Area Y**: "Burrard Inlet/English Bay" - boat-based marine counting area (admin-only)
- **Impact**: Caused off-by-one error in leaders map legend (showed 4 instead of 5 areas with leaders)
- **Current Fix**: JavaScript now uses areas.py count for legend calculations
- **TODO**: Add Area Y boundary data to area_boundaries.json (marine boundary polygon)

### Future Sessions (Production Features)
1. **Cloud Scheduler** setup for automated triggers
2. **Monitoring and alerting** for email system
3. **Performance optimization** for large participant counts
4. **Email templates** refinement and testing

### Security Monitoring and Refinement (Post Security Deployment)
1. **Rate limit adjustment** - Monitor actual usage patterns and adjust limits if needed
2. **Security log analysis** - Regular review of rate limit violations and blocked requests
3. **Input sanitization testing** - Test edge cases and malicious input patterns
4. **CSRF token monitoring** - Check for any CSRF-related failures in logs
5. **Performance impact assessment** - Ensure security features don't significantly impact response times
6. **Advanced rate limiting** - Consider implementing more sophisticated rate limiting if simple limits prove insufficient

### Authentication Security Audit (Post Email Implementation)
1. **Comprehensive route security audit** - verify all admin/leader routes are properly protected
2. **Authentication decorator verification** - ensure all data viewing/modification routes use appropriate decorators (@require_admin, @require_leader, @require_auth)
3. **Unauthenticated access review** - verify no sensitive endpoints are accessible to unauthenticated users
4. **Blueprint security review** - check route definitions in all Blueprint files (admin.py, leader.py, api.py, auth.py)
5. **Data modification endpoint security** - ensure all routes that modify participant/leader data require proper authentication
6. **Test unauthenticated access** - verify admin/leader interfaces are not accessible without proper authentication

## Environment Configuration

### Current Deploy Settings
```bash
# deploy.sh
DISPLAY_TIMEZONE="America/Vancouver"

# Test environment
FLASK_ENV=development,TEST_MODE=true,DISPLAY_TIMEZONE=$DISPLAY_TIMEZONE

# Production environment  
FLASK_ENV=production,DISPLAY_TIMEZONE=$DISPLAY_TIMEZONE
```

### Dependencies
```
# requirements.txt additions
pytz                          # For timezone handling
Flask-WTF                     # For CSRF protection
Flask-Limiter                 # For rate limiting
google-cloud-email           # TODO: Add for Email API

# utils/requirements.txt additions  
beautifulsoup4               # For CSRF token parsing in test scripts
```

## Debugging Information

### Useful Commands
```bash
# View recent logs
gcloud run services logs read cbc-test --region=us-west1 --limit=50

# Check service configuration
gcloud run services describe cbc-test --region=us-west1

# Test email triggers (on cbc-test.naturevancouver.ca)
curl -X POST https://cbc-test.naturevancouver.ca/admin/test/trigger-team-updates

# Test security features
python utils/generate_test_participants.py 5 --test-rate-limit  # Test rate limiting
python utils/generate_test_participants.py 20                  # Test normal CSRF operation
```

### Key Log Patterns
- `ERROR:test.email_generator:Critical error` - Email generation failure
- `ERROR:services.email_service:SMTP credentials not configured` - Email API missing
- `INFO:test.email_generator:Team update emails completed` - Function completion stats
- `INFO:services.email_service:Email service initialized in TEST MODE` - Test mode confirmation
- `ERROR:werkzeug:429 Too Many Requests` - Rate limiting triggered
- `ERROR:werkzeug:400 Bad Request` - CSRF token validation failed

### File System Investigation (Container)
Files are properly deployed to the container:
```
/app/test/email_generator.py     ✅ Present
/app/services/email_service.py   ✅ Present  
/app/services/security.py        ✅ Present (implemented, not yet deployed)
/app/services/limiter.py         ✅ Present (implemented, not yet deployed)
/app/config/rate_limits.py       ✅ Present (implemented, not yet deployed)
/app/templates/emails/           ✅ Present
/app/utils/                      ❌ Excluded by .gcloudignore (correct - security code moved to services/)

## Architecture Decisions Made

### 1. Security-First Approach
- Test routes only exist in test mode
- Production servers have no test endpoints
- Email addresses validated before sending
- Security code placed in `services/` (deployed) rather than `utils/` (excluded)
- Full security stack testing rather than bypass mechanisms

### 2. Timezone Strategy  
- UTC for all storage and calculations
- Configurable display timezone for user interfaces
- Single source of truth in deployment configuration

### 3. Email Service Architecture
- Test mode redirects all emails to admin address
- Separate service layer for email delivery abstraction
- Template-based HTML email generation

### 4. Error Handling Philosophy
- Log errors but continue processing other areas
- Return detailed status information for debugging
- Fail gracefully without breaking the main application

### 5. Security Implementation Strategy
- Flask-WTF chosen for CSRF protection (integrates well with existing Flask architecture)
- TEST_MODE-aware rate limits to balance testing efficiency with production security
- Input sanitization preserves data integrity while preventing injection attacks
- HTML escaping in templates using `|e` filter for XSS prevention
- Rate limiting with in-memory storage suitable for single-instance Cloud Run deployment

## Development Status Summary

The email automation system has made significant progress with most core features implemented:

### ✅ **Implemented and Tested**
1. **Email Generation Engine**: Implementation in `test/email_generator.py`
   - Three email types with change detection logic
   - Timezone-aware datetime handling for Vancouver operations
   - Race condition prevention via timestamp management
   - Flask app context support for template rendering
   - Error handling and logging

2. **Security Architecture**: Environment-based access control
   - Test routes only exist when `TEST_MODE=true`
   - Production servers exclude test functionality
   - Admin access protection via `@require_admin` decorator
   - Test mode email redirection to `birdcount@naturevancouver.ca`

3. **Timezone System**: Configurable display timezone support
   - UTC storage with `DISPLAY_TIMEZONE` environment variable
   - Default: `America/Vancouver` for Christmas Bird Count timing
   - Deployment configuration shows timezone during deployment
   - Helper functions in `config/settings.py`

4. **Package Structure**: Deployment-safe directory organization
   - Email code moved from `utils/` (excluded) to `test/` (included)
   - Python package initialization with `__init__.py` files
   - Import resolution fixed for container deployment

5. **Email Templates**: HTML templates for all three email types
   - `templates/emails/team_update.html`
   - `templates/emails/weekly_summary.html` 
   - `templates/emails/admin_digest.html`
   - Environment-aware links for test vs production

6. **Test Interface**: Admin dashboard integration
   - Manual trigger buttons for all three email types
   - Real-time feedback with success/failure status
   - JSON response format for debugging
   - Only available on test server (`cbc-test.naturevancouver.ca`)

### ❌ **Pending Implementation**
1. **Google Cloud Email API Configuration**
   - Currently uses SMTP which lacks proper credentials
   - Requires enabling Email API in Google Cloud Console
   - Service account creation with email permissions needed
   - Credentials storage in Google Secret Manager required

2. **Production Automation Infrastructure**
   - Cloud Scheduler jobs for automated triggers pending
   - Pub/Sub topics for reliable message delivery not configured
   - Monitoring and alerting for email failures not implemented

3. **Email Service Integration**
   - Update `services/email_service.py` to use Google Cloud Email API
   - Replace SMTP-specific configuration
   - Add proper error handling for API calls

### 🔧 **Current System Status**
- **Test Results**: "0 emails sent" due to SMTP credential absence
- **Email Generation**: Generates proper email content but delivery fails
- **Test Mode**: Properly redirects all emails to admin address
- **Area Processing**: Currently processes 4 areas (only areas with assigned leaders)
- **Error Handling**: Graceful failure with detailed logging

**Next Session Requirements**: Focus on Google Cloud Email API setup, production automation configuration, and email service integration.

### ✅ Recently Resolved Issues

#### CSV Export Field Enumeration Risk (Resolved 2025-09-16)
- **Problem**: Dynamic field enumeration from first record risked missing fields in CSV exports
- **Solution**: Implemented centralized field management in `config/fields.py`
- **Implementation**:
  - Explicit field enumeration with ordered lists
  - Normalization functions ensure all records have all fields
  - Default value management for missing fields
  - Both CSV exports and admin interfaces use centralized definitions
- **Result**: Schema evolution safety - new fields guaranteed to appear in all outputs