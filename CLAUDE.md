# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## ⚠️ CRITICAL DOCUMENTATION RULES ⚠️

**NEVER describe this system as "production ready", "feature complete", "finished", "functionally complete", or similar completion claims unless explicitly instructed to do so.** This is iterative development with ongoing spec updates even after initial deployment. This instruction has been given multiple times and must be remembered for ALL future sessions.

- Do not add completion claims to documentation .md files or code comments
- Do not suggest the development work is finished
- Always treat this as work-in-progress requiring ongoing development

## ⚠️ CRITICAL DEPLOYMENT CONSTRAINT ⚠️

**NEVER place application code in the `utils/` directory.** The `utils/` directory contains development-time utilities that run on the development computer and are NOT deployed to Google Cloud Run. Any code needed by the live application must be placed in directories that are included in the deployment (e.g., `services/`, `models/`, `config/`, or the root directory). This constraint must be remembered for ALL future sessions.

## ⚠️ CRITICAL SECURITY REQUIREMENTS ⚠️

**NEVER, EVER include passwords, API keys, or any credentials in files that could be checked into version control and published on GitHub.** This includes:
- Code files (.py, .js, .html, etc.)
- Documentation files (.md files)
- Configuration files (.json, .yaml, .ini, etc.)
- ANY file that gets committed to the repository

**If credentials are needed for new chat sessions:**
- Tell the user the information needs to be passed by a different method
- Suggest using environment variables, Google Secret Manager, or secure communication channels
- NEVER write credentials in documentation even if "needed for resuming work"

## ⚠️ CRITICAL CONFIGURATION MANAGEMENT ⚠️

**NEVER hardcode organization-specific values that should be obtained from configuration files.** This application is designed to be portable for other Christmas Bird Count clubs.

### **Configuration Sources (USE THESE)**
- **Organization settings**: `config/organization.py` - Organization name, contact emails, URLs, event names
- **Email settings**: `config/email_settings.py` - Email provider configuration, branding, test mode settings
- **Area definitions**: `config/areas.py` - Count area codes and descriptions
- **Admin configuration**: `config/admins.py` - Admin email whitelist

### **Organization Variables (from `config/organization.py`)**
```python
from config.organization import get_organization_variables

# Get all organization variables
org_vars = get_organization_variables()
# Returns: organization_name, organization_website, organization_contact,
#          count_contact, count_event_name, count_info_url,
#          registration_url, admin_url, test_recipient
```

### **Common Hardcoding Mistakes to AVOID**
- ❌ Hardcoding "Nature Vancouver" - use `org_vars['organization_name']`
- ❌ Hardcoding email addresses like "cbc@naturevancouver.ca" - use `org_vars['count_contact']`
- ❌ Hardcoding "birdcount@naturevancouver.ca" - use `org_vars['test_recipient']` or `COUNT_CONTACT`
- ❌ Hardcoding "Vancouver Christmas Bird Count" - use `org_vars['count_event_name']`
- ❌ Hardcoding URLs like "https://cbc-registration.naturevancouver.ca" - use `org_vars['registration_url']` or `org_vars['admin_url']`
- ❌ Hardcoding "info@naturevancouver.ca" - use `org_vars['organization_contact']`

### **Where to Check for Hardcoded Values**
When writing or modifying code that mentions organization details:
1. **Email generation** (`services/email_service.py`, `test/email_generator.py`)
2. **Email templates** (`templates/emails/*.html`)
3. **Registration routes** (`routes/main.py`)
4. **Admin interfaces** (`routes/admin.py`)
5. **Public templates** (`templates/index.html`, etc.)

### **Testing Configuration Portability**
- All organization-specific values should be changeable by editing `config/organization.py` only
- No code changes should be required to adapt this system for another bird count club
- Search codebase for club-specific strings before committing: `grep -r "Nature Vancouver" --exclude-dir=.git`

**ALL form inputs MUST be properly sanitized and validated.** This application has comprehensive security protections that must be maintained:

### **Input Sanitization (MANDATORY)**
- **ALL user inputs** must use functions from `services/security.py`
- **Names**: Use `sanitize_name()` - max 100 chars, letters/spaces/hyphens/apostrophes only
- **Emails**: Use `sanitize_email()` - max 254 chars, lowercase, valid email chars only  
- **Phone numbers**: Use `sanitize_phone()` - max 20 chars, digits/spaces/hyphens/parentheses/plus only
- **Notes/text**: Use `sanitize_notes()` - max 1000 chars, allows newlines
- **NEVER accept raw form input** without sanitization

### **Template Security (MANDATORY)**
- **ALL user input displays** must use `|e` filter for HTML escaping: `{{ user_input|e }}`
- **Required for**: names, emails, phone numbers, notes, any user-generated content
- **XSS Prevention**: This prevents script injection attacks

### **Template Output Escaping Rules (CRITICAL)**

**ALWAYS escape user-controlled data in templates, even though Jinja2 auto-escape is enabled.** Explicit escaping provides defense-in-depth and makes security intent clear.

#### **HTML Context Escaping:**
```html
<!-- CORRECT - Always use |e filter for user data -->
{{ participant.first_name|e }} {{ participant.last_name|e }}
{{ participant.email|e }}
{{ participant.phone|e or 'N/A' }}
{{ participant.notes_to_organizers|e }}

<!-- INCORRECT - Missing explicit escaping (relies only on auto-escape) -->
{{ participant.first_name }} {{ participant.last_name }}
{{ participant.email }}
```

#### **JavaScript Context Escaping:**
```html
<!-- CORRECT - Use |tojson for JavaScript variables -->
<script>
const userName = {{ participant.first_name|tojson }};
const userEmail = {{ participant.email|tojson }};
const areaCode = {{ leader.assigned_area_leader|tojson }};
</script>

<!-- INCORRECT - Direct interpolation causes XSS vulnerability -->
<script>
const userName = "{{ participant.first_name }}";  // DANGEROUS!
var email = "{{ participant.email }}";            // DANGEROUS!
</script>
```

#### **HTML Attribute Escaping:**
```html
<!-- CORRECT - Escape in attributes too -->
<input type="text" value="{{ participant.first_name|e }}">
<div title="{{ participant.notes|e }}">...</div>
<a href="mailto:{{ participant.email|e }}">{{ participant.email|e }}</a>

<!-- INCORRECT - Missing escaping in attributes -->
<input type="text" value="{{ participant.first_name }}">
```

#### **URL Context Safety:**
```html
<!-- SAFE - url_for() generates safe URLs -->
<a href="{{ url_for('admin.dashboard', year=selected_year) }}">Dashboard</a>

<!-- SAFE - mailto: with escaped email -->
<a href="mailto:{{ participant.email|e }}">{{ participant.email|e }}</a>

<!-- DANGEROUS - Never put user data directly in URLs without validation -->
<a href="/search?q={{ user_query }}">  <!-- Missing escaping! -->
```

#### **Dangerous Patterns to AVOID:**
```html
<!-- NEVER use |safe on user data -->
{{ participant.notes|safe }}  <!-- DANGEROUS! Bypasses all escaping -->

<!-- NEVER disable auto-escape for user data -->
{% autoescape false %}
{{ user_content }}  <!-- DANGEROUS! -->
{% endautoescape %}

<!-- NEVER trust "sanitized" data in JavaScript context -->
<script>
var note = "{{ sanitized_note }}";  <!-- Still vulnerable! Use |tojson -->
</script>
```

#### **Code Review Checklist for Templates:**
When creating or modifying templates, verify:
- [ ] All `{{ participant.* }}` variables use `|e` filter
- [ ] All `{{ leader.* }}` variables use `|e` filter
- [ ] JavaScript context uses `|tojson`, never direct interpolation
- [ ] HTML attributes containing user data are escaped
- [ ] No `|safe` filters on user-controlled data
- [ ] No `{% autoescape false %}` blocks with user data
- [ ] Email template variables are escaped (even for trusted recipients)

#### **Common User Data Fields Requiring Escaping:**
- `first_name`, `last_name` - ALWAYS escape
- `email` - ALWAYS escape
- `phone`, `phone2` - ALWAYS escape
- `notes_to_organizers`, `notes` - ALWAYS escape
- `skill_level`, `experience` - Usually safe (enum), but escape anyway
- `assigned_area_leader`, `preferred_area` - Usually safe (validated), but escape for consistency

#### **Testing for XSS:**
Test templates with malicious input during development:
```python
# Test data examples
first_name = "<script>alert('XSS')</script>"
last_name = "O'Brien"  # Tests quote handling
email = "test+<img src=x onerror=alert(1)>@example.com"
notes = '"; alert("XSS"); //'
```

Expected behavior: All displayed as literal text, no JavaScript execution

### **CSRF Protection (MANDATORY)**
- **ALL POST forms** must include `{{ csrf_token() }}` in templates
- **AJAX requests** must include `csrf_token: '{{ csrf_token() }}'` in JSON payload
- **Already configured**: Flask-WTF automatically validates tokens

### **Rate Limiting (CONFIGURED)**
- **Current limits**: 10/minute registration (production), 50/minute (TEST_MODE)
- **DO NOT modify** rate limits without considering cost implications for Cloud Run
- **Located in**: `config/rate_limits.py` with TEST_MODE detection

### **Security Validation Functions**
Always use these validation functions from `services/security.py`:
- `validate_area_code()`, `validate_skill_level()`, `validate_experience()`, `validate_participation_type()`
- `is_suspicious_input()` - flags potential attack patterns  
- `log_security_event()` - logs security events for monitoring

### **Testing Security**
- **Test script updated**: `utils/generate_test_participants.py` tests all security features
- **Rate limit testing**: Use `--test-rate-limit` flag to validate rate limiting works
- **CSRF testing**: Script automatically tests CSRF token validation

## ⚠️ CRITICAL TEST SELECTOR ORDERING ⚠️

**ALWAYS order UI element selectors from MOST LIKELY to LEAST LIKELY to succeed.** This is fundamental QA best practice and prevents unnecessary timeout delays that can add 30+ seconds per test.

### Selector Ordering Rules:
1. **Put the most specific, reliable selector FIRST** (e.g., exact ID, data attribute, href match)
2. **Put generic fallbacks LAST** (e.g., partial text, contains, class-based)
3. **Test actual page HTML** to determine which selector will work
4. **Remove selectors that will never work** (e.g., invalid CSS like `button:contains()`)

### Bad Example (causes 3-6 second delays):
```python
export_selectors = [
    'non-existent-id',  # ❌ Doesn't exist - wastes 3 seconds on timeout
    (By.PARTIAL_LINK_TEXT, 'Wrong Text'),  # ❌ Wrong text - wastes 3 more seconds
    (By.CSS_SELECTOR, 'a[href*="export_csv"]'),  # ✅ THIS WORKS but tried last after 6 seconds!
    (By.CSS_SELECTOR, 'button:contains("Export")')  # ❌ Invalid CSS syntax
]
```

### Good Example (instant success):
```python
export_selectors = [
    (By.CSS_SELECTOR, 'a[href*="export_csv"]'),  # ✅ WORKS - try first! (instant)
    (By.PARTIAL_LINK_TEXT, 'Export CSV'),  # Fallback with correct text
    (By.ID, 'export-csv-button'),  # Additional fallback
    (By.XPATH, '//button[contains(text(), "Export")]')  # Last resort (use XPath not invalid CSS)
]
```

### Impact:
- **Bad ordering**: Each failed selector wastes 3+ seconds waiting for timeout
- **Good ordering**: Instant success on first try
- **On tests with many elements**: Bad ordering adds 30+ seconds per test execution!

### Technical Note:
- CSS does NOT support `:contains()` pseudo-selector - use XPath `[contains(text(), ...)]` instead
- Always prefer CSS selectors over XPath when both work (CSS is faster)
- Test your selectors in browser DevTools before adding to code

## ⚠️ CRITICAL DATA INTEGRITY REQUIREMENTS ⚠️

**ALWAYS use identity-based matching for participant/leader operations.** This application supports family members sharing email addresses, making email-only matching unreliable and potentially destructive.

### **Identity-Based Operations (MANDATORY)**
- **NEVER use email-only matching** for any participant or leader operations
- **ALWAYS use identity tuple**: `(first_name, last_name, email)` for unique identification
- **Family email support**: Multiple family members may share one email address
- **Email alone is NOT unique** - this is a critical design constraint

### **Required Methods (USE THESE)**
When working with leader operations, use these identity-based methods from `AreaLeaderModel`:
```python
# CORRECT - Identity-based methods
get_leaders_by_identity(first_name, last_name, email)
deactivate_leaders_by_identity(first_name, last_name, email, removed_by)
get_areas_by_identity(first_name, last_name, email)

# AVOID - Email-only methods (legacy, family-unsafe)
get_leaders_by_email(email)  # Use only for non-critical operations
```

### **Bidirectional Synchronization (MANDATORY)**
- **Participant deletion** MUST deactivate corresponding leader records using identity matching
- **Leader deletion** MUST reset participant `is_leader` flag (already implemented)
- **Test synchronization** with family email scenarios during development

### **Validation Rules**
- Duplicate prevention: Use identity-based checks, not email-only
- Display logic: Use identity matching for participant/leader deduplication
- Authentication: Email-based sharing of privileges among family members (by design)

### **Critical Testing**
- ALWAYS test with shared family email addresses
- Verify synchronization works correctly with identity matching
- Test duplicate prevention allows different family members with same email

## About This Project

This is a Flask web application for Nature Vancouver's annual Christmas Bird Count registration system. Users can register for count areas using an interactive map or dropdown, with automatic assignment to areas needing volunteers.

## Core Architecture

### Annual Event Structure
- **Year-based data collections**: Each year's data is stored separately (e.g., `participants_2025`, `area_leaders_2025`)
- **Cross-year access**: Historical queries merge results from multiple yearly collections with email deduplication
- **Three access levels**: Public (no auth), Area Leader (Google OAuth), Admin (OAuth + whitelist)

### Key Components
- **Backend**: Flask with Blueprint routing architecture
- **Database**: Google Firestore with environment-specific databases (`cbc-test`, `cbc-register`) and year-aware models
- **Authentication**: Google OAuth with role-based access control
- **Frontend**: Bootstrap 5 + Leaflet.js interactive map with context-aware navigation
- **Deployment**: Google Cloud Run + Firestore

## Essential Commands

### Development
```bash
# Install dependencies
pip install -r requirements.txt

# Run development server
python app.py
# Serves on http://localhost:8080 with debug=True

# Test Firestore connection (requires GCP credentials)
python -c "from google.cloud import firestore; print('Firestore OK' if firestore.Client() else 'Failed')"
```

### Deployment
```bash
# Deploy to test environment only
./deploy.sh test

# Deploy to production only  
./deploy.sh production

# Deploy to both environments (default)
./deploy.sh both

# View logs
gcloud run services logs read cbc-test --region=us-west1 --limit=50
gcloud run services logs read cbc-registration --region=us-west1 --limit=50
```

### OAuth Setup (First-time only)
```bash
# 1. Create OAuth client in Google Console (see OAUTH-SETUP.md)
# 2. Download client_secret.json to project root
# 3. Run setup script
./utils/setup_oauth_secrets.sh

# 4. Delete client_secret.json after setup completes
rm client_secret.json
```

### Utility Scripts
```bash
# Install utility dependencies (one-time setup)
pip install -r utils/requirements.txt

# Set up Firestore databases (run once per project setup)
python utils/setup_databases.py --dry-run       # Preview what would be created
python utils/setup_databases.py                # Create missing databases with indexes
python utils/setup_databases.py --skip-indexes # Create databases only (faster, but may have runtime delays)
python utils/setup_databases.py --force        # Recreate all databases (with confirmation)

# Generate test participants for development/testing
python utils/generate_test_participants.py                    # 20 regular + 5 leadership
python utils/generate_test_participants.py 50                # 50 regular + 5 leadership  
python utils/generate_test_participants.py 10 --seq 100      # 10 regular + 5 leadership, start at email 0100
python utils/generate_test_participants.py 0 --seq 5000      # 0 regular + 5 leadership, start at email 5000
```

## Project Structure

### Core Files
- `app.py` - Flask application entry point with blueprint registration
- `requirements.txt` - Python dependencies (Flask, google-cloud-firestore, gunicorn)
- `Dockerfile` - Container configuration for Cloud Run deployment

### Configuration
- `config/areas.py` - Static area definitions (A-X, 24 areas)
- `config/admins.py` - Admin email whitelist
- `config/settings.py` - Environment configuration
- `config/colors.py` - Color palette definitions with 20 distinct accessibility colors

### Models (Year-Aware)
- `models/participant.py` - Year-specific participant operations with Firestore
- `models/area_leader.py` - Year-specific leader management
- `models/removal_log.py` - Year-specific removal tracking

### Routes (Blueprints)
- `routes/main.py` - Public registration routes
- `routes/admin.py` - Admin interface with year selector  
- `routes/auth.py` - OAuth and authorization handling
- `routes/api.py` - JSON endpoints for map data and leadership information

### Frontend
- `static/js/map.js` - Leaflet.js interactive map with registration count-based coloring
- `static/js/leaders-map.js` - Leaders page map showing areas needing leaders
- `static/js/registration.js` - Form validation and interactions
- `static/css/main.css` - Bootstrap-based responsive styling with CSS custom properties for colors
- `static/data/area_boundaries.json` - GeoJSON area polygons for map

### Templates
- `templates/base.html` - Base template with context-aware navigation (admin vs public)
- `templates/index.html` - Registration form with interactive map
- `templates/auth/login.html` - Google OAuth login page
- `templates/admin/dashboard.html` - Admin overview with statistics and year selection
- `templates/admin/leaders.html` - Leader management interface with interactive map and inline editing
- `templates/admin/participants.html` - Participant management interface
- `templates/admin/unassigned.html` - Unassigned participant management interface (streamlined)
- `templates/admin/area_detail.html` - Area-specific views interface
- `templates/errors/` - 404/500 error pages

## Key Implementation Patterns

### Database Configuration
```python
# Environment-specific database selection
from config.database import get_firestore_client

# Automatically uses appropriate database based on environment
db, database_id = get_firestore_client()
# Test: FLASK_ENV=development OR TEST_MODE=true → cbc-test
# Prod: FLASK_ENV=production AND TEST_MODE≠true → cbc-register
```

### Year-Based Data Access
```python
# Models automatically use current year unless specified
participant_model = ParticipantModel(db)  # Uses current year
historical_model = ParticipantModel(db, 2024)  # Specific year

# Cross-year queries for historical data
historical_participants = participant_model.get_historical_participants('A', years_back=3)
```

### Firestore Query Syntax (MANDATORY)
**Always use the modern `FieldFilter` syntax to avoid deprecation warnings:**

```python
from google.cloud.firestore_v1.base_query import FieldFilter

# CORRECT - Modern syntax (no warnings)
query = collection.where(filter=FieldFilter('field_name', '==', value))

# INCORRECT - Deprecated positional arguments (causes warnings)
query = collection.where('field_name', '==', value)
```

**Key Points:**
- **Import required**: `from google.cloud.firestore_v1.base_query import FieldFilter`
- **Use `filter` keyword**: Always pass `filter=FieldFilter(...)` to `.where()` calls
- **Applies to all queries**: Single filters, chained filters, and complex queries
- **Reference**: See [Google Cloud PR #10407](https://github.com/GoogleCloudPlatform/python-docs-samples/pull/10407/files)

**Examples:**
```python
# Single filter
query = db.collection('participants_2025').where(filter=FieldFilter('is_leader', '==', True))

# Multiple filters (chained)
query = (db.collection('participants_2025')
         .where(filter=FieldFilter('email', '==', email.lower()))
         .where(filter=FieldFilter('is_leader', '==', True)))

# Conditional filter
if area_code:
    query = query.where(filter=FieldFilter('assigned_area_leader', '==', area_code))

# Comparison operators
query = db.collection('removal_log_2025').where(filter=FieldFilter('removed_at', '>=', cutoff_date))
```

### Authentication Flow
1. **Google Identity Services OAuth** for protected routes using client credentials stored in Google Secret Manager
2. **Role determination**:
   - Admin: Email in `config/admins.py` → full access to all years and functions
   - Area Leader: Email in `area_leaders_YYYY` → area-specific access for assigned areas
   - Public: Unauthenticated → registration only
3. **OAuth implementation**:
   - Login via `/auth/login` with Google Sign-In button
   - Token verification and session creation in `/auth/oauth/callback`
   - Role-based redirects: admins → `/admin/dashboard`, leaders → `/leader/dashboard`
   - Authentication required decorators: `@require_admin`, `@require_leader`, `@require_auth`

### Area Management
- 24 count areas (A-X, no Y) with static configuration
- Interactive map with clickable polygons synced to dropdown
- Auto-assignment to areas needing volunteers ("UNASSIGNED" preference)
- No capacity limits - areas accommodate varying numbers

## Important Constraints

### Data Integrity
- Current year: full read/write access
- Historical years: read-only access (UI enforced + validation)
- Email deduplication across years (most recent data wins)
- Explicit year field in all records for data integrity

### Security
- **OAuth credentials** stored in Google Secret Manager (never in version control)
- **Admin whitelist** in version control (`config/admins.py`)
- **No public admin links** - admins access `/admin` directly or via login redirect
- **Role-based access control** with authentication decorators
- **Area leaders** scoped to assigned areas only
- **Historical data protection** (read-only via UI, enforced by validation)
- **HTTPS enforcement** for all OAuth callbacks and sensitive operations
- **CSRF protection** on authenticated forms

### Mobile-First Design
- Primary usage via mobile devices
- Responsive Bootstrap layout
- Touch-optimized map interactions
- Graceful degradation if map fails

## Environment Setup

### Required Environment Variables
- `GOOGLE_CLOUD_PROJECT=vancouver-cbc-registration` (for Cloud Run)
- `SECRET_KEY` (Flask sessions, defaults to dev key)

### Google Cloud Services
- Cloud Run (application hosting)
- Firestore (data persistence)
- OAuth 2.0 (authentication)

## Testing and Validation

The application uses production Firestore - test carefully:
- Use test deployment: `cbc-test.naturevancouver.ca`
- Production deployment: `cbc-registration.naturevancouver.ca`
- Monitor with: `gcloud run services logs read SERVICE_NAME --region=us-west1`

## Common Development Tasks

### OAuth Authentication Issues
1. **"OAuth client not found" errors**:
   - Check client ID for trailing newlines: `gcloud secrets versions access latest --secret="google-oauth-client-id"`
   - Verify OAuth consent screen is **published** (not in testing mode)
   - Ensure JavaScript origins configured correctly (no redirect URIs needed)

2. **"Google OAuth not configured" errors**:
   - Verify `init_auth(app)` is called in `app.py`
   - Check Secret Manager permissions: `gcloud projects get-iam-policy PROJECT_ID`
   - Confirm secrets are mounted in Cloud Run deployment

3. **Database connection errors in OAuth callback**:
   - Ensure Firestore client initialization in auth routes
   - Verify `GOOGLE_CLOUD_PROJECT` environment variable
   - Check Firestore indexes (click URL in error logs to create)

### Adding New Areas
1. Update `config/areas.py` with new area definition
2. Update `static/data/area_boundaries.json` with polygon coordinates  
3. Test map rendering and form dropdown

### Managing Admin Access
Admin access is automatically managed based on environment:

**Production Admin Changes:**
1. Edit `PRODUCTION_ADMIN_EMAILS` list in `config/admins.py`
2. Redeploy application: `./deploy.sh both`
3. Test authentication with new admin account at `/admin`

**Test Admin Access:**
- Test accounts (`cbc-test-admin1@`, `cbc-test-admin2@naturevancouver.ca`) are automatically active in test environments
- No manual configuration required for test deployments
- Environment detection: `TEST_MODE=true`, `FLASK_ENV=development`, or project name contains 'test'

**Security Features:**
- Runtime validation prevents test accounts in production
- Automatic environment detection eliminates manual deployment errors
- Separate admin lists for production vs test accounts

### Year Transition Setup
1. Models automatically create new year collections
2. Admin interface includes year selector
3. Historical data remains accessible read-only
4. Update production admin list in `config/admins.py` if coordinators change

### Map Color Management
The application uses a centralized color system based on 20 distinct accessibility colors from sashamaps.net:

**Modifying Map Colors:**
1. **Color Palette**: All available colors defined in `config/colors.py` with `DISTINCT_COLOURS` dictionary
2. **Map Color Assignment**: Update `MAP_COLORS` in `config/colors.py` to change which colors represent different registration count ranges
3. **CSS Variables**: Colors automatically propagate through CSS custom properties in `:root` 
4. **JavaScript Integration**: Map rendering uses `getComputedStyle()` to read CSS variables dynamically

**Current Color Scheme:**
- **Orange** `#f58231`: 0-3 registered participants
- **Maroon** `#800000`: 4-8 registered participants  
- **Navy** `#000075`: 8+ registered participants
- **Yellow** `#ffe119`: Selected area highlighting

**To Change Colors:** Modify only `config/colors.py` - CSS and JavaScript automatically adapt through the centralized system.

### Leader Management System
**Completed Features:**
- Interactive map display showing areas needing leaders vs areas with leaders
- Inline edit/delete functionality with real-time validation and map updates
- Manual leader entry form with validation and business rule enforcement
- Participant-to-leader promotion from "Potential Leaders" list
- Area dropdowns properly populated with area codes and names
- Leader information displayed in map tooltips on hover

**Area-Leader Relationships:**
- Multiple leaders allowed per area
- One area maximum per leader (enforced in backend)
- Manual leader entry creates records only in `area_leaders_YYYY` collection
- Participant-to-leader promotion updates both collections

**Registration Integration:**
- If leader registers as participant → auto-assign to their led area
- If participant promoted to leader → update their area assignment to match led area
- Leader status tracked in both participant.is_leader and area_leaders collection

**Map Functionality:**
- Red areas indicate areas needing leaders (interactive, clickable)
- Green areas indicate areas with leaders (shows leader names on hover)
- Map legend shows count of areas with/without leaders
- Areas needing leaders have enhanced hover and click interactions

**Inline Edit/Delete Functionality:**
- Direct table editing with pencil and trash icons (Bootstrap Icons)
- Simultaneous editing of all leader fields (area, names, email, phone)
- Real-time validation and business rule enforcement
- Client-side data management for instant map updates without server round-trips
- AJAX operations with comprehensive error handling and user feedback

**Email Automation System (Core Complete, API Pending):**
- **Three Email Types**: 
  1. Twice-daily team updates to area leaders when team composition changes
  2. Weekly summaries for areas with no changes (Fridays at 11pm)  
  3. Daily admin digest listing unassigned participants
- **Test Environment**: Admin dashboard includes manual email trigger buttons (test server only)
- **Environment-Based Security**: Test email routes only registered when `TEST_MODE=true`
- **Test Mode Behavior**: All emails redirect to `birdcount@naturevancouver.ca` on test server
- **Timezone Support**: Configurable display timezone via `DISPLAY_TIMEZONE` environment variable
- **Race Condition Prevention**: Timestamp selection before queries, update after successful send
- **Change Detection**: Participant diff tracking with detailed logging
- **Production Scheduling**: Cloud Scheduler integration planned for automated triggers

**Current Implementation Status:**
- ✅ **Email Generation Logic**: Core functionality implemented in `test/email_generator.py`
- ✅ **Email Templates**: HTML templates in `templates/emails/` for all three types
- ✅ **Test UI**: Admin dashboard buttons for manual triggering (test server only)
- ✅ **Security**: Production servers do not expose test email routes
- ✅ **Timezone Handling**: UTC storage with configurable display timezone
- ✅ **Package Structure**: Proper Python imports and deployment safety
- ❌ **Email Service**: Currently uses SMTP, needs Google Cloud Email API
- ❌ **API Integration**: Email delivery fails due to missing API credentials

**Email and Access Requirements:**
- Leaders can have non-Google emails (for notifications only)
- Only Google email leaders can access leader UI at `/leader`
- Required leader fields: first_name, last_name, email, cell_phone
- Automated email notifications for team updates and weekly summaries

### Email System Architecture
1. **Test Email Triggers (Test Server Only)**:
   - Access admin dashboard on `cbc-test.naturevancouver.ca/admin`
   - Use email trigger buttons to test each email type on demand
   - All test emails redirect to `birdcount@naturevancouver.ca`
   - Routes only exist when `TEST_MODE=true` (production security)
   - Check logs: `gcloud run services logs read cbc-test --region=us-west1 --limit=50`

2. **Email System Components**:
   - **Email Generation**: `test/email_generator.py` - Core logic for all email types with timezone support
   - **Email Service**: `services/email_service.py` - Email delivery with test mode support
   - **Email Templates**: `templates/emails/` - HTML templates for team updates, weekly summaries, admin digest
   - **Environment Detection**: `is_test_server()` helper function for test mode behavior
   - **Email Configuration**: `config/email_settings.py` - Email service configuration
   - **Timezone Helpers**: `config/settings.py` - UTC storage with local display conversion

3. **Deployment Configuration**:
   - **Timezone Setting**: `DISPLAY_TIMEZONE` variable in `deploy.sh` (default: America/Vancouver)
   - **Environment Variables**: `TEST_MODE`, `DISPLAY_TIMEZONE` passed to Cloud Run
   - **Deployment Output**: Shows configured timezone during deployment for verification
   - **Security**: Test routes only registered in test mode, completely absent from production

4. **Next Steps for Completion**:
   - **Configure Google Cloud Email API**: Enable API and set up service account authentication
   - **Add Email API Credentials**: Store in Google Secret Manager
   - **Update Email Service**: Replace SMTP with Google Cloud Email API
   - **Production Scheduling**: Configure Cloud Scheduler for automated triggers
   - **Monitoring**: Set up alerts for email delivery failures and processing errors

### Debugging Deployment Issues
1. **Check service configuration**: `gcloud run services describe SERVICE --region=us-west1`
2. **Monitor logs in real-time**: `gcloud run services logs tail SERVICE --region=us-west1`
3. **Verify secrets access**: Check that service account has `secretmanager.secretAccessor` role
4. **Test Firestore connection**: Verify `GOOGLE_CLOUD_PROJECT` and service account permissions
- we can't test locally because the app uses google cloud services that are not configured on the local windows 11 host where we're doing development.  All testing has to be done on the cbc-test version of the app, accessible on the web as cbc-test.naturevancouver.ca
- remember that the project files are stored in a git repository, so it may be necessary to use git commands when removing or moving a file

## File Modification Guidelines

### Timestamp Comments
When modifying files, add timestamp comments using date only (not specific times):
- **Python files**: `# Updated by Claude AI on YYYY-MM-DD` 
- **HTML templates (Jinja2)**: `{# Updated by Claude AI on YYYY-MM-DD #}`
- **JavaScript/CSS**: `/* Updated by Claude AI on YYYY-MM-DD */`

Use the current date from the environment context, not specific times since Claude doesn't have access to precise timestamps.
- Do not update SPECIFICATION.md with information from DEVELOPMENT_NOTES.md.  The latter is for recording plans for future work, whereas SPECIFICATION.md is intended to reflect the current state of the project.  We will update SPECIFICATION.md with features as they are implemented and specification updates should be based on the actual implementation, not on planning info found in DEVELOPMENT_NOTES.md, unless I explicitly request otherwise.

## Test Suite Development Status (As of 2025-09-22)

**COMPLETED:**
- ✅ **Test Suite Architecture**: Complete framework design documented in TEST_SUITE_SPEC.md
- ✅ **Configuration Files**: tests/config.py, tests/conftest.py, tests/pytest.ini, tests/requirements.txt
- ✅ **Test Utilities**: auth_utils.py (OAuth automation), database_utils.py (state management)
- ✅ **Google Secret Manager**: Test account passwords stored securely (test-admin1-password, test-admin2-password, test-leader1-password)
- ✅ **Documentation**: TEST_SETUP.md (complete setup), TESTING.md (execution guide), TEST_SUITE_SPEC.md (requirements)
- ✅ **Test Accounts**: Google Workspace accounts created (cbc-test-admin1@, cbc-test-admin2@, cbc-test-leader1@naturevancouver.ca)

**NEXT STEPS FOR RESUMING TEST SUITE DEVELOPMENT:**
1. **Bug Fixing Session**: Fix known data consistency issues (leader management, Clive Roberts scenario)
2. **First Test Implementation**: Create basic registration test to validate framework
3. **Test Data Generation**: Extend utils/generate_test_participants.py for test datasets
4. **Critical Tests**: Implement Phase 1 tests (registration, authentication, data consistency)
5. **CSV Export Validation**: Implement comprehensive export testing

**KEY TEST PRIORITIES:**
- Leader promotion → deletion → re-addition workflow (Clive Roberts bug)
- Participant/leader data synchronization across collections
- Registration flow with FEEDER constraints
- CSV export validation (primary validation mechanism)
- Admin authentication and role-based access

**IMPORTANT NOTES:**
- Test suite must run against cloud environments (cbc-test.naturevancouver.ca)
- Current year used for functional testing, year 2000 for isolation testing
- Test accounts passwords in Secret Manager, usernames documented in config files
- Framework designed for incremental implementation (start with working example, build utilities as needed)
- put all throwaway scripts in the debug/ directory so they can easily be discarded later.
- put python imports at the top of the file, not inline in the code
- **CRITICAL: NEVER begin replies with agreement phrases like "You're right", "You're absolutely correct", "You're absolutely right", or similar validation statements.** These phrases before analysis are sycophantic and unhelpful. Instead, begin directly with analysis, investigation, or solution work. If analysis confirms a user statement, acknowledge it AFTER presenting evidence.
- never use the word "comprehensive" unless specifically instructed to do so.  You should probably mostly avoid its synonyms as well.