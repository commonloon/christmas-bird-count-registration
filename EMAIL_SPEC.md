# Email System Specification for Single-Table Architecture
{# Updated by Claude AI on 2025-09-29 #}

This document specifies the automated email notification system for the Christmas Bird Count registration application, adapted for the single-table architecture where all participant and leadership data is unified in `participants_YYYY` collections.

## Overview

The email system provides automated notifications to area leaders and administrators about registration activity, team changes, and administrative tasks. The system is designed for:

- **Seasonal usage patterns**: Active September-December, dormant January-August
- **Single-table architecture**: Leadership data integrated into participant records with `is_leader` flag
- **Test mode safety**: All emails redirect to admin in test environments
- **Change detection**: Only sends emails when actual changes occur

## Email Types

### 1. Twice-Daily Team Updates

**Purpose**: Notify area leaders when their team composition changes

**Recipients**:
- All leaders for the area (from `participants_YYYY` where `is_leader=True` and `assigned_area_leader=area_code`)
- Not sent for areas without assigned leaders

**Trigger Conditions**:
- New participant registrations in the area
- Participants reassigned to/from the area
- Participant deletions from the area
- Email address changes for existing team members

**Content**:
- **Subject**: "{date} Vancouver CBC Area {area_code} Update" (date prefix format: YYYY-MM-DD)
- **New team members**: Added or reassigned to area since last update (simplified list format)
- **Removed team members**: Deleted or reassigned from area since last update (simplified list format)
- **Email Summary Section**: Dedicated section with all team email addresses in copy-friendly format with copy button
- **Complete current roster**: Professional table format matching admin interface (Name, Email, Cell Phone, Skill Level, Experience, Equipment, Leader Interest, Scribe Interest)
- **Leader dashboard link**: Environment-appropriate URL

**Frequency**: Automated checks twice daily (production scheduling pending)

### 2. Weekly Team Summary

**Purpose**: Provide consistent weekly communication to all area leaders

**Recipients**:
- All leaders for all areas (from `participants_YYYY` where `is_leader=True`)
- Sent to every area leader regardless of whether team changes occurred

**Trigger Conditions**:
- Sent every Friday at 11pm Pacific Time
- No change detection - sent to all leaders for consistent communication

**Content**:
- **Subject**: "{date} Vancouver CBC Area {area_code} Weekly Summary" (date prefix format: YYYY-MM-DD)
- **Team status**: Visual badge indicating "Changes this week" or "No changes this week"
- **Team statistics**: Interactive grid showing total members, skill level breakdown, experience distribution, leadership interest count
- **Email Summary Section**: Dedicated section with all team email addresses in copy-friendly format with copy button
- **Complete team roster**: Professional table format matching admin interface (Name, Email, Cell Phone, Skill Level, Experience, Equipment, Leader Interest, Scribe Interest)
- **Leader dashboard link**: Environment-appropriate URL

### 3. Daily Admin Digest

**Purpose**: Notify administrators of participants needing area assignment

**Recipients**:
- All admin emails from `config/admins.py`

**Trigger Conditions**:
- Participants exist with `preferred_area="UNASSIGNED"`
- Only sent when unassigned participants are present

**Content**:
- **Subject**: "{date} Vancouver CBC Unassigned Participants" (date prefix format: YYYY-MM-DD)
- **Unassigned participant list**: Names, contact info, registration details
- **Statistics**: Count, leadership interest, average days waiting
- **Admin interface link**: Direct link to unassigned management page

**Frequency**: Daily checks (production scheduling pending)

## Technical Architecture

### Data Model Integration (Single-Table)

**Participant Collection Schema**:
```javascript
{
  // Standard participant fields
  first_name: string,
  last_name: string,
  email: string,
  phone: string,
  phone2: string,                    // Secondary phone (NEW)

  // Leadership fields (integrated)
  is_leader: boolean,                // True for area leaders
  assigned_area_leader: string,      // Area code they lead (e.g., "A", "B")
  leadership_assigned_by: string,    // Admin who assigned leadership
  leadership_assigned_at: timestamp, // When leadership assigned
  leadership_removed_by: string,     // Admin who removed leadership
  leadership_removed_at: timestamp,  // When leadership removed

  // Other fields...
  preferred_area: string,            // "A"-"X" or "UNASSIGNED"
  created_at: timestamp,
  updated_at: timestamp,
  year: integer
}
```

**Email Timestamp Tracking**:
```javascript
// Collection: email_timestamps_{year}
{
  area_code: string,                 // "A", "B", etc.
  email_type: string,                // "team_update", "weekly_summary"
  last_sent: timestamp,              // UTC timestamp of last email
  year: integer
}
```

**Removal Log Integration**:
```javascript
// Collection: removal_log_{year}
{
  participant_name: string,
  area_code: string,
  removed_by: string,
  reason: string,
  removed_at: timestamp,
  year: integer,
  emailed: boolean,                  // Tracks if removal was included in email
  emailed_at: timestamp              // When removal notification sent
}
```

### Email Generation System

**Core Components**:
- **Email Generator**: `test/email_generator.py` - Core logic for all email types
- **Email Service**: `services/email_service.py` - SMTP delivery with test mode support
- **Email Templates**: `templates/emails/` - HTML templates for each email type
- **Configuration**: `config/email_settings.py` - Provider-agnostic email settings

**Change Detection Logic**:
1. **Race Condition Prevention**: Select timestamp before queries, update after successful send
2. **Participant Changes**: Compare `created_at` and `updated_at` against last email timestamp
3. **Removal Changes**: Query `removal_log` for entries since last email with `emailed=False`
4. **Area Reassignments**: Track `updated_at` with area code comparison

**Leader Email Resolution**:
```python
def get_area_leaders_emails(participant_model, area_code):
    """Get leader emails for specific area from unified participant data."""
    leaders = participant_model.get_leaders_by_area(area_code)
    return [leader['email'] for leader in leaders if leader.get('is_leader', False)]
```

### Template System

**HTML Email Templates**:
- `templates/emails/team_update.html` - Twice-daily team updates
- `templates/emails/weekly_summary.html` - Weekly summaries for all leaders
- `templates/emails/admin_digest.html` - Daily admin digest

**Template Features**:
- **Professional Table Format**: Participant roster displayed in table matching admin interface exactly
  - Columns: Name, Email, Cell Phone, Skill Level, Experience, Equipment, Leader Interest, Scribe Interest
  - FEEDER participants distinguished with light blue row background
  - Equipment shown with emoji icons (🔭 binoculars, 🏁 spotting scope)
  - Interest badges for leadership and scribe roles
- **Email Summary Section**: Dedicated section for easy email copying
  - Copy button with JavaScript functionality and visual feedback
  - Fallback text selection for email clients without JavaScript support
  - All team emails in comma-separated format for easy copying
- **Enhanced Statistics** (Weekly Summary): Grid layout showing team composition breakdown
- **Date-Prefixed Subjects**: All emails include YYYY-MM-DD date prefix to prevent Gmail threading issues
- **Responsive HTML**: Bootstrap-based styling for mobile compatibility (800px max width)
- **Environment-aware links**: Test vs production URL generation
- **Secondary phone display**: Includes both primary and secondary phone numbers
- **Test mode indicators**: Visual indicators for test email mode
- **Timezone display**: Pacific Time formatting for user convenience
- **Security**: All user input properly escaped with `|e` filter

**Template Context Variables**:
```python
{
    'area_code': str,
    'leader_names': List[str],         # Full names of area leaders
    'new_participants': List[Dict],    # Recently added participants (team updates only)
    'removed_participants': List[Dict], # Recently removed participants (team updates only)
    'current_team': List[Dict],        # Complete current team roster
    'has_changes': bool,               # Whether team had changes this week (weekly summary)
    'skill_breakdown': Dict[str, int], # Skill level statistics
    'experience_breakdown': Dict[str, int], # CBC experience statistics
    'leadership_interest_count': int,  # Count interested in leadership
    'current_date': datetime,          # Email generation timestamp
    'leader_dashboard_url': str,       # Environment-appropriate URL
    'admin_unassigned_url': str,       # Admin interface URL
    'test_mode': bool,                 # Test mode indicator
    'branding': Dict[str, str]         # Organizational branding configuration
}
```

**Branding Configuration**:
```python
# config/email_settings.py
EMAIL_BRANDING = {
    'organization_name': 'Nature Vancouver',
    'logo_url': None,  # Set dynamically based on environment
    'logo_alt': 'Nature Vancouver Logo',
    'primary_color': '#2e8b57',      # Sea green (matches logo)
    'secondary_color': '#1e5c3a',    # Darker green
    'accent_color': '#90ee90',       # Light green
    'background_color': '#f0fff0',   # Honeydew (very light green)
}

def get_email_branding() -> dict:
    """Get complete email branding with environment-specific logo URL."""
    branding = EMAIL_BRANDING.copy()
    branding['logo_url'] = get_logo_url()  # Environment-specific URL
    return branding
```

### Security & Environment Handling

**Test Mode Implementation**:
- **Environment Detection**: `TEST_MODE=true` or hostname contains 'test'
- **Email Redirection**: All emails redirect to `TEST_RECIPIENT` from `config/organization.py`
- **Subject Preservation**: Test emails maintain original subject format (no test modification)
- **Route Security**: Test email routes only exist when `TEST_MODE=true`

**Production Security**:
- **Route Isolation**: Test routes completely absent from production servers
- **Admin Protection**: All email routes require `@require_admin` decorator
- **Input Validation**: All email addresses validated before sending
- **Error Handling**: Graceful failure without breaking main application

**Organization Configuration Management**:
- **Configuration Source**: All organization-specific values from `config/organization.py`
- **No Hardcoding**: Email service loads organization name, contact emails, URLs dynamically
- **Portability**: Other Christmas Bird Count clubs can adapt by editing configuration only
- **Configuration Helper**: `get_organization_variables()` returns all organization settings
- **Available Values**: `organization_name`, `organization_contact`, `count_contact`, `count_event_name`, `count_info_url`, `registration_url`, `admin_url`, `test_recipient`

### Email Service Configuration

**Provider-Agnostic Design** (from email branch):
```python
EMAIL_PROVIDERS = {
    'smtp2go': {
        'smtp_server': 'mail.smtp2go.com',
        'smtp_port': 587,
        'use_tls': True,
        'username_env': 'SMTP2GO_USERNAME',
        'password_env': 'SMTP2GO_PASSWORD'
    },
    # Additional providers: gmail, sendgrid, mailgun
}
```

**Configuration Management**:
- **Provider Selection**: Via `EMAIL_PROVIDER` environment variable
- **Credential Storage**: Google Secret Manager for production
- **Test Mode Support**: Automatic email redirection
- **Error Handling**: Graceful fallback when credentials missing

### Integration with Single-Table Architecture

**Leadership Query Methods**:
```python
class ParticipantModel:
    def get_leaders(self):
        """Get all leaders from participant records."""
        return [p for p in self.get_all_participants() if p.get('is_leader', False)]

    def get_leaders_by_area(self, area_code):
        """Get leaders assigned to specific area."""
        return [p for p in self.get_leaders() if p.get('assigned_area_leader') == area_code]

    def is_area_leader(self, email, area_code):
        """Check if person is leader for specific area."""
        leaders = self.get_leaders_by_area(area_code)
        return any(leader['email'].lower() == email.lower() for leader in leaders)
```

**Participant Change Detection**:
```python
def get_participants_changes_since(participant_model, area_code, since_timestamp):
    """Get participants added/removed since timestamp."""
    current_participants = participant_model.get_participants_by_area(area_code)

    # New participants: created_at or updated_at > since_timestamp
    new_participants = [p for p in current_participants
                       if (p.get('created_at', datetime.min) > since_timestamp or
                           p.get('updated_at', datetime.min) > since_timestamp)]

    # Removed participants: from removal_log since timestamp
    removal_model = RemovalLogModel(participant_model.db, participant_model.year)
    removed_participants = removal_model.get_removals_since(area_code, since_timestamp)

    return new_participants, removed_participants
```

## Migration from Two-Table Architecture

### Key Changes Required

**1. Leadership Data Source**:
- **Before**: `area_leaders_YYYY` collection with separate schema
- **After**: Integrated leadership fields in `participants_YYYY` collection

**2. Leader Email Resolution**:
- **Before**: `AreaLeaderModel.get_leaders_by_area(area_code)`
- **After**: `ParticipantModel.get_leaders_by_area(area_code)` with `is_leader=True` filter

**3. Field Mapping**:
- **Email**: `leader_email` → `email`
- **Phone**: `cell_phone` → `phone`
- **Area**: `area_code` → `assigned_area_leader`
- **Names**: `first_name`, `last_name` (unchanged)

**4. Authentication**:
- **Before**: Check `area_leaders_YYYY` collection for leadership
- **After**: Check `is_leader=True` and `assigned_area_leader` in participant records

### Compatibility Considerations

**Template Updates Needed**:
- Email templates already support unified participant schema
- No template changes required for single-table migration

**Email Generation Logic**:
- Core email generation logic is architecture-agnostic
- Only leader query methods need updating for single-table

**Test Mode Functionality**:
- Test mode email redirection unchanged
- Admin dashboard integration remains the same

## Production Deployment Requirements

### Email Service Configuration

**SMTP Provider Setup** (current implementation):
- **Provider**: SMTP2GO (configurable to Gmail, SendGrid, Mailgun)
- **Credentials**: Stored in Google Secret Manager
- **Environment Variables**: `SMTP2GO_USERNAME`, `SMTP2GO_PASSWORD`, `EMAIL_PROVIDER`

**Alternative: Gmail API Setup** (planned):
- **OAuth Scope**: `https://www.googleapis.com/auth/gmail.send`
- **Service Account**: Email-specific OAuth tokens in Secret Manager
- **Dependencies**: `google-auth`, `google-api-python-client`

### Automation Infrastructure

**Cloud Scheduler Jobs** (pending implementation):
- **Twice-daily updates**: `0 8,20 * * *` (8am, 8pm Pacific)
- **Weekly summaries**: `0 6 * * 5` (Friday 11pm Pacific = Saturday 6am UTC)
- **Daily admin digest**: `0 17 * * *` (10am Pacific)

**Monitoring & Alerting** (pending):
- **Email delivery failures**: Cloud Monitoring alerts
- **Function execution errors**: Cloud Logging alerts
- **Performance monitoring**: Email generation time tracking

### Environment Variables

**Production Configuration**:
```bash
# Email service
EMAIL_PROVIDER=smtp2go
FROM_EMAIL=cbc@naturevancouver.ca

# Environment detection
FLASK_ENV=production
TEST_MODE=false
DISPLAY_TIMEZONE=America/Vancouver

# Secret Manager references
SMTP2GO_USERNAME=projects/PROJECT/secrets/smtp2go-username/versions/latest
SMTP2GO_PASSWORD=projects/PROJECT/secrets/smtp2go-password/versions/latest
```

**Test Configuration**:
```bash
# Email service (same as production)
EMAIL_PROVIDER=smtp2go
FROM_EMAIL=cbc@naturevancouver.ca

# Environment detection
FLASK_ENV=development
TEST_MODE=true
DISPLAY_TIMEZONE=America/Vancouver

# Same secret references (test mode redirects emails)
```

## Implementation Status

### ✅ Completed Components (Updated 2025-09-29)
✅ **Single-Table Migration**: Successfully migrated from dual-table email branch to single-table main branch architecture
✅ **Email Generation Logic**: Complete with timezone support and change detection using participant-based leadership
✅ **Enhanced HTML Email Templates**: Professional table format matching admin interface with simplified email copying
✅ **Leadership Query Integration**: Updated to use `ParticipantModel.get_leaders()` and identity-based operations
✅ **Weekly Summary Logic**: Updated to send to ALL area leaders (not just unchanged areas)
✅ **Date-Prefixed Subjects**: All emails include YYYY-MM-DD prefix to prevent Gmail threading issues
✅ **Registration Confirmation**: Updated to include year prefix in subject line
✅ **Email Summary Section**: Dedicated copy-friendly email list with text selection (JavaScript copy button removed for Gmail compatibility)
✅ **Security Architecture**: Test-only routes with production isolation and proper input escaping
✅ **Test Interface**: Admin dashboard integration with manual triggers and CSRF protection
✅ **Timezone Support**: Configurable display timezone (America/Vancouver)
✅ **Provider-Agnostic Email Service**: Support for multiple SMTP providers (SMTP2GO, Gmail, SendGrid, Mailgun)
✅ **Firestore Index Management**: Added required composite index for removal_log queries (area_code + removed_at)
✅ **Organizational Branding**: Configurable email branding system with Nature Vancouver logo and green color scheme
✅ **Configuration-Based Organization Values**: All organization-specific values (names, emails, URLs) loaded from `config/organization.py`
  - Added `TEST_RECIPIENT` configuration for test mode email redirection
  - Eliminated hardcoded organization names, contact emails, and URLs from `services/email_service.py`
  - All email methods use `get_organization_variables()` for consistent configuration access
  - Improved portability for other Christmas Bird Count clubs
✅ **Template Features**:
  - Professional table layout identical to admin/participants interface
  - Equipment icons and role interest badges
  - FEEDER participant visual distinction
  - Mobile-responsive design (800px max width)
  - Nature Vancouver logo with transparent PNG format for email client compatibility
  - Green color scheme matching organizational branding (#2e8b57 primary, #f0fff0 background)
  - Horizontal header layout with logo and organization name
  - Optimized content flow: header → dashboard button → salutation → status → roster → emails → tasks → statistics
  - Simplified email copying via text selection (removed JavaScript for better Gmail compatibility)
  - Enhanced typography with larger, bold salutation text

### Pending Production Features
❌ **Cloud Scheduler Setup**: Automated email triggers
❌ **Gmail API Integration**: Alternative to SMTP for better reliability
❌ **Monitoring & Alerting**: Email delivery failure detection
❌ **Performance Optimization**: Email generation efficiency for large datasets

## Testing Strategy

### Test Mode Validation
1. **Email Redirection**: Verify all emails redirect to `TEST_RECIPIENT` from `config/organization.py`
2. **Subject Preservation**: Confirm test emails maintain original date-prefixed format
3. **Template Rendering**: Test HTML templates with realistic data including table format and email copy functionality
4. **Change Detection**: Verify change detection logic with test data
5. **Configuration Loading**: Verify all organization values loaded from `config/organization.py` (no hardcoded values)
6. **Email Copy Functionality**: Test text selection-based email copying in various email clients

### Integration Testing
1. **Single-Table Queries**: Test leadership resolution from participant records
2. **Email Generation**: End-to-end email generation with realistic datasets
3. **Error Handling**: Test graceful failure scenarios
4. **Performance**: Test email generation time with large participant counts

### Production Readiness
1. **SMTP Credentials**: Verify email service configuration
2. **Template Links**: Test environment-specific URL generation
3. **Admin Dashboard**: Test manual email triggers
4. **Monitoring**: Verify logging and error reporting

---

This email system specification provides a comprehensive foundation for migrating email functionality from the dual-table email branch to the single-table main branch architecture.