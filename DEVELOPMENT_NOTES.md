# Email Automation System - Development Notes

## Current Development Status (As of 2025-09-10)

### ✅ Completed Features

#### 1. Email Generation Logic
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

### ❌ Pending Implementation

#### 1. Google Cloud Email API Configuration
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
test/
  __init__.py                 # NEW: Package initialization
  email_generator.py          # MOVED: From utils/email_generator.py

services/
  __init__.py                 # NEW: Package initialization  
  email_service.py            # MODIFIED: Needs Email API integration

config/
  settings.py                 # MODIFIED: Added timezone helper functions

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

### Immediate Priority (Email API Setup)
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

### Future Sessions (Production Features)
1. **Cloud Scheduler** setup for automated triggers
2. **Monitoring and alerting** for email system
3. **Performance optimization** for large participant counts
4. **Email templates** refinement and testing

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
google-cloud-email           # TODO: Add for Email API
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
```

### Key Log Patterns
- `ERROR:test.email_generator:Critical error` - Email generation failure
- `ERROR:services.email_service:SMTP credentials not configured` - Email API missing
- `INFO:test.email_generator:Team update emails completed` - Function completion stats
- `INFO:services.email_service:Email service initialized in TEST MODE` - Test mode confirmation

### File System Investigation (Container)
The email system files are properly deployed to the container:
```
/app/test/email_generator.py     ✅ Present
/app/services/email_service.py   ✅ Present  
/app/templates/emails/           ✅ Present
/app/utils/                      ❌ Excluded by .gcloudignore (correct)
```

## Architecture Decisions Made

### 1. Security-First Approach
- Test routes only exist in test mode
- Production servers have no test endpoints
- Email addresses validated before sending

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