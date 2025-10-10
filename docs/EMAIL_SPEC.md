# Email System Specification
<!-- Updated by Claude AI on 2025-10-06 -->

This document specifies the automated email notification system for the Christmas Bird Count registration application using the single-table architecture where participant and leadership data is unified in `participants_YYYY` collections.

## Overview

The email system provides automated notifications to area leaders and administrators about registration activity, team changes, and administrative tasks.

**System Characteristics**:
- **Seasonal usage patterns**: Active September-December, dormant January-August
- **Single-table architecture**: Leadership data integrated into participant records with `is_leader` flag
- **Test mode safety**: All emails redirect to admin in test environments
- **Change detection**: Sends emails when changes occur

## Email Types

### 1. Twice-Daily Team Updates

**Purpose**: Notify area leaders when their team composition changes

**Recipients**:
- All leaders for the area (from `participants_YYYY` where `is_leader=True` and `assigned_area_leader=area_code`)
- Not sent for areas without assigned leaders

**Trigger Conditions**:
- New participant registrations in the area
- Participant information updates (contact info, equipment, skill level, experience)
- Participants reassigned to/from the area
- Participant deletions from the area

**Content**:
- **Subject**: "{date} Vancouver CBC Area {area_code} Update" (date prefix format: YYYY-MM-DD)
- **New team members**: Added or reassigned to area since last update
- **Participant info updates**: Contact info, equipment, or other field changes
- **Removed team members**: Deleted or reassigned from area since last update
- **Email Summary Section**: Team email addresses in copy-friendly format
- **Complete current roster**: Table format should match what's displayed for the area in the admin/participants UI (Name, Email, Cell Phone, Skill Level, Experience, Equipment, Leader Interest, Scribe Interest).  Table should be sorted by participant type, then by first name.
- **Leader dashboard link**: Environment-appropriate URL

**Frequency**: Intent is to automatically run the check for changes twice daily (5am and 5pm) and email all leaders for areas whose team membership has changed since the last update.  Manual triggers available on test server via admin dashboard.

### 2. Weekly Team Summary

**Purpose**: Provide consistent weekly communication to all area leaders

**Recipients**:
- All leaders for all areas (from `participants_YYYY` where `is_leader=True`)
- Sent to every area leader regardless of whether team changes occurred

**Trigger Conditions**:
- Intended schedule: Every Friday at 11pm Pacific Time.  Time zone should be configurable in config.py to support use by other clubs.
- sent to all leaders for consistent communication
- Includes a summary of all team changes (additions/removals/contact info changed) since the previous weekly update

**Content**:
- **Subject**: "{date} Vancouver CBC Area {area_code} Weekly Summary" (date prefix format: YYYY-MM-DD)
- **Team status**: Visual badge indicating "Changes this week" or "No changes this week". 
- **New team members**: Added or reassigned to area since last weekly update
- **Participant info updates**: Contact info, equipment, or other field changes since last weekly update
- **Removed team members**: Deleted or reassigned from area since last weekly update- **Email Summary Section**: Team email addresses in copy-friendly format
- **Complete team roster**: Table format (Name, Email, Cell Phone, Skill Level, Experience, Equipment, Leader Interest, Scribe Interest)
- **Leader dashboard link**: Environment-appropriate URL
- **Team statistics**: Grid layout showing total members, skill level breakdown, experience distribution

**Frequency**: Manual triggers available on test server via admin dashboard (automated scheduling pending)

### 3. Daily Admin Digest

**Purpose**: Notify administrators of participants needing area assignment

**Recipients**:
- All admin emails from `config/admins.py`

**Trigger Conditions**:
- Intended schedule daily at 5pm local time (use timezone from config.py)
- Participants exist with `preferred_area="UNASSIGNED"`
- Only sent when unassigned participants are present

**Content**:
- **Subject**: "{date} Vancouver CBC Unassigned Participants" (date prefix format: YYYY-MM-DD)
- **Unassigned participant list**: Names, contact info, registration details
- **Statistics**: Count, leadership interest, average days waiting
- **Admin interface link**: Direct link to unassigned management page

**Frequency**: Manual triggers available on test server via admin dashboard (automated scheduling pending)

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
- **Email Generator**: `test/email_generator.py` - Logic for all email types
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
- `templates/emails/registration_confirmation.html` - Registration confirmation

**Template Features**:
- **Table Format**: Participant roster in table format
  - Columns: Name, Email, Cell Phone, Skill Level, Experience, Equipment, Leader Interest, Scribe Interest
  - FEEDER participants: light blue row background
  - Equipment: text display (Binoculars, Scope)
  - Interest badges for leadership and scribe roles
  - Sorted: Regular participants alphabetically, then FEEDER participants alphabetically
- **Email Summary Section**: Copy-friendly email list
  - Text selection interface for copying team email addresses
  - Comma-separated format
- **Statistics Display** (Weekly Summary): Grid layout with team composition breakdown
- **Date-Prefixed Subjects**: YYYY-MM-DD prefix to prevent Gmail threading issues
- **Responsive HTML**: 800px max width for mobile compatibility
- **Environment-aware links**: Test vs production URL generation
- **Leader Dashboard Button**: Inline styled button with white text on green background
- **Secondary phone display**: Both primary and secondary phone numbers
- **Test mode indicators**: Visual indicators for test email mode
- **Timezone display**: Pacific Time formatting
- **Security**: All user input escaped with `|e` filter

**Template Styling**:
- **Header**: Logo with 25px spacer div, organization name, event title
- **Headings**: Black text (h4 elements, 18px, bold)
- **Footer**: Light background matching content
- **Buttons**: Inline styles to override email client defaults (`color: #ffffff !important`)
- **Salutation spacing**: `margin-right: auto` for proper button positioning

**Template Context Variables**:
```python
{
    'area_code': str,
    'leader_names': List[str],          # Full names of area leaders
    'new_participants': List[Dict],     # Recently added participants (team updates only)
    'updated_participants': List[Dict], # Recently updated participants (team updates only)
    'removed_participants': List[Dict], # Recently removed participants (team updates only)
    'current_team': List[Dict],         # Complete current team roster
    'has_changes': bool,                # Whether team had changes this week (weekly summary)
    'skill_breakdown': Dict[str, int],  # Skill level statistics
    'experience_breakdown': Dict[str, int], # CBC experience statistics
    'leadership_interest_count': int,   # Count interested in leadership
    'current_date': datetime,           # Email generation timestamp
    'leader_dashboard_url': str,        # Environment-appropriate URL
    'admin_unassigned_url': str,        # Admin interface URL
    'test_mode': bool,                  # Test mode indicator
    'branding': Dict[str, str]          # Organizational branding configuration
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
    'text_color': '#333',            # Body text color
    'badge_warning': '#ffc107',      # Yellow badge color
}

def get_email_branding() -> dict:
    """Get email branding with environment-specific logo URL."""
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
- **Email Validation**: Centralized validation in `services/security.py::validate_email_format()`
  - RFC 5322 compliance with plus sign (+) support
  - Security restrictions rejecting percent signs (%) and exclamation marks (!)
  - Consistent validation across Python backend and JavaScript frontend
- **Input Sanitization**: All user input sanitized with dedicated functions in `services/security.py`
- **Template Security**: All user input escaped with `|e` filter in Jinja2 templates
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

### Methods

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
    """Get participants added/updated/removed since timestamp."""
    current_participants = participant_model.get_participants_by_area(area_code)

    new_participants = []
    updated_participants = []

    for participant in current_participants:
        created_at = participant.get('created_at', datetime.min)
        updated_at = participant.get('updated_at', datetime.min)

        if created_at > since_timestamp:
            # New participant
            new_participants.append(participant)
        elif updated_at > since_timestamp and created_at <= since_timestamp:
            # Existing participant with updates
            updated_participants.append(participant)

    # Removed participants: from removal_log since timestamp
    removal_model = RemovalLogModel(participant_model.db, participant_model.year)
    removed_participants = removal_model.get_removals_since(area_code, since_timestamp)

    return new_participants, updated_participants, removed_participants
```

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
- Times are examples.  Timezone should be specified in config.py
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

## Current Implementation

### Email Generation
- Single-table migration from dual-table email branch architecture
- Email generation logic with timezone support and change detection using participant-based leadership
- Participant info update detection for team update emails
- Weekly summary logic:
  - Sends to ALL area leaders (not just unchanged areas)
  - Tracks changes since last weekly summary (separate from team update timestamps)
  - Includes new/updated/removed participant sections in email template
- Date-prefixed subjects (YYYY-MM-DD) to prevent Gmail threading issues
- Registration confirmation with year prefix in subject line

### Email Templates
- HTML templates for all email types
- Table format matching admin interface
- Equipment and interest badge displays
- FEEDER participant visual distinction
- Mobile-responsive design (800px max width)
- Nature Vancouver logo (transparent PNG format)
- Green color scheme (#2e8b57 primary, #f0fff0 background, #ffc107 warning)
- Horizontal header with logo spacer div (25px)
- Email summary section with copy-friendly format
- Inline button styling for email client compatibility
- Black heading text (h4 elements)
- Participant sorting: regular participants alphabetically, then FEEDER participants alphabetically

### Security & Configuration
- Test-only routes with production isolation
- Input escaping with `|e` filter in templates
- Email validation with RFC 5322 compliance and plus sign (+) support
- Security restrictions rejecting percent (%) and exclamation (!) in emails
- Matching validation in Python and JavaScript
- Organization-specific values from `config/organization.py` including:
  - `DISPLAY_TIMEZONE` for email timestamps and scheduled tasks
  - `TEST_RECIPIENT` for test mode email redirection
  - All organization names, contact emails, and URLs
- CSRF protection for admin triggers with informative error messages

### Testing & Deployment
- Admin dashboard integration with manual triggers (test server only)
- Informative error handling for trigger failures (CSRF, permissions, server errors)
- Timezone support (configurable via `DISPLAY_TIMEZONE` in `config/organization.py`)
- Provider-agnostic email service (SMTP2GO, Gmail, SendGrid, Mailgun)
- Firestore composite index for removal_log queries (area_code + removed_at)
- Email branding configuration with environment-specific logo URLs

### Pending Features
- Cloud Scheduler setup for automated email triggers
- Gmail API integration as alternative to SMTP
- Monitoring and alerting for email delivery failures
- Performance optimization for large datasets

## Testing Strategy

### Test Mode Validation
1. **Email Redirection**: Verify all emails redirect to `TEST_RECIPIENT` from `config/organization.py`
2. **Subject Preservation**: Confirm test emails maintain original date-prefixed format
3. **Template Rendering**: Test HTML templates with realistic data including table format and email copy functionality
4. **Change Detection**: Verify change detection logic with test data including participant info updates
5. **Configuration Loading**: Verify all organization values loaded from `config/organization.py` (no hardcoded values)
6. **Email Copy Functionality**: Test text selection-based email copying in various email clients
7. **Email Validation**: Verify plus sign support and security restrictions (percent/exclamation rejection)
8. **Table Sorting**: Verify participant tables sort regular participants alphabetically, then FEEDER participants alphabetically
9. **Button Styling**: Verify inline button styles render with white text on green background in Gmail and other email clients
10. **Header Spacing**: Verify logo spacer div (25px) renders correctly across email clients
11. **Error Handling**: Test trigger button error messages for CSRF failures (expired tokens), permission errors, and server failures
12. **Weekly Summary Changes**: Verify weekly summaries include change sections (new/updated/removed participants) and track timestamps separately from team updates

### Integration Testing
1. **Single-Table Queries**: Test leadership resolution from participant records
2. **Email Generation**: End-to-end email generation with realistic datasets
3. **Error Handling**: Test graceful failure scenarios
4. **Performance**: Test email generation time with large participant counts

### Production Readiness
1. **SMTP Credentials**: Verify email service configuration
2. **Template Links**: Test environment-specific URL generation
3. **Admin Dashboard**: Test manual email triggers (test server only - not available in production)
4. **Monitoring**: Verify logging and error reporting
5. **Route Isolation**: Verify test email routes absent from production deployment

---

This specification documents the email notification system for the Christmas Bird Count registration application using single-table architecture.