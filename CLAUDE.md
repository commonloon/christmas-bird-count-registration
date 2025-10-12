# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## ⚠️ CRITICAL RULES ⚠️

### Documentation Standards
- **NEVER** describe as "production ready", "feature complete", "finished", or "functionally complete"
- Always treat as work-in-progress requiring ongoing development
- Do not add completion claims to .md files or code comments

### Deployment Constraints
- **NEVER** place application code in `utils/` directory (not deployed to Cloud Run)
- Application code belongs in `services/`, `models/`, `config/`, or root directory

### Security Requirements
**NEVER include credentials in version-controlled files:**
- No passwords, API keys, tokens in .py, .js, .html, .md, .json, .yaml, .ini files
- Tell user to use environment variables, Google Secret Manager, or secure channels
- NEVER write credentials in documentation "for resuming work"

### Configuration Management
**NEVER hardcode organization-specific values** - use `config/organization.py`:

```python
from config.organization import get_organization_variables
org_vars = get_organization_variables()
# Returns: organization_name, organization_website, organization_contact,
#          count_contact, count_event_name, count_info_url,
#          registration_url, admin_url, test_recipient
```

**Common mistakes to avoid:**
- ❌ Hardcoding "Nature Vancouver" → use `org_vars['organization_name']`
- ❌ Hardcoding "cbc@naturevancouver.ca" → use `org_vars['count_contact']`
- ❌ Hardcoding URLs → use `org_vars['registration_url']` or `org_vars['admin_url']`

**Check these files:** `services/email_service.py`, `test/email_generator.py`, `templates/emails/*.html`, `routes/*.py`, `templates/*.html`

### Input Sanitization (MANDATORY)
**ALL user inputs** must use `services/security.py` functions:
- Names: `sanitize_name()` - max 100 chars, letters/spaces/hyphens/apostrophes
- Emails: `sanitize_email()` - max 254 chars, lowercase, valid chars
- Phones: `sanitize_phone()` - max 20 chars, digits/spaces/hyphens/parens/plus
- Notes: `sanitize_notes()` - max 1000 chars, allows newlines
- Validation: `validate_area_code()`, `validate_skill_level()`, `validate_experience()`, `validate_participation_type()`

### Template Security (MANDATORY)
**ALWAYS escape user-controlled data in templates:**

```html
<!-- HTML Context - Use |e filter -->
{{ participant.first_name|e }} {{ participant.last_name|e }}
{{ participant.email|e }}

<!-- JavaScript Context - Use |tojson -->
<script>
const userName = {{ participant.first_name|tojson }};
</script>

<!-- NEVER use |safe or disable autoescape on user data -->
```

**Checklist for templates:**
- [ ] All `{{ participant.* }}` and `{{ leader.* }}` variables use `|e` filter
- [ ] JavaScript uses `|tojson`, never direct interpolation
- [ ] HTML attributes are escaped
- [ ] No `|safe` or `{% autoescape false %}` on user data

**CSRF Protection:** All POST forms need `{{ csrf_token() }}`, AJAX needs `csrf_token: '{{ csrf_token() }}'`

**Rate Limiting:** 10/min production, 50/min test - DO NOT modify without cost consideration

### Test Selector Ordering
**Order selectors from MOST to LEAST likely to succeed** to avoid timeout delays:

```python
# GOOD - Try most reliable first
selectors = [
    (By.CSS_SELECTOR, 'a[href*="export_csv"]'),  # ✅ Specific, works instantly
    (By.PARTIAL_LINK_TEXT, 'Export CSV'),        # Fallback
    (By.XPATH, '//button[contains(text(), "Export")]')  # Last resort
]

# BAD - Wastes 3+ seconds per failed selector
selectors = [
    'non-existent-id',  # ❌ Doesn't exist, wastes 3 sec
    (By.CSS_SELECTOR, 'button:contains("Export")')  # ❌ Invalid CSS
]
```

**Note:** CSS doesn't support `:contains()` - use XPath `[contains(text(), ...)]` instead

### Data Integrity (MANDATORY)
**ALWAYS use identity-based matching:** `(first_name, last_name, email)` tuple

**Family email support:** Multiple family members may share one email address - email alone is NOT unique

```python
# CORRECT - Identity-based methods from AreaLeaderModel
get_leaders_by_identity(first_name, last_name, email)
deactivate_leaders_by_identity(first_name, last_name, email, removed_by)
get_areas_by_identity(first_name, last_name, email)

# AVOID - Email-only (legacy, family-unsafe)
get_leaders_by_email(email)  # Use only for non-critical operations
```

**Bidirectional Synchronization:**
- Participant deletion MUST deactivate leader records (identity-based)
- Leader deletion MUST reset participant `is_leader` flag
- Test with shared family emails

## About This Project

Flask web application for Nature Vancouver's Christmas Bird Count registration. Interactive map/dropdown selection with automatic assignment to areas needing volunteers.

### Core Architecture
- **Year-based collections**: Separate data per year (`participants_2025`, `area_leaders_2025`)
- **Backend**: Flask + Blueprints, Firestore (environment-specific: `cbc-test`, `cbc-register`)
- **Authentication**: Google OAuth with role-based access (Public/Leader/Admin)
- **Frontend**: Bootstrap 5 + Leaflet.js interactive map
- **Deployment**: Google Cloud Run + Firestore

## Essential Commands

```bash
# Development
pip install -r requirements.txt
python app.py  # Serves on localhost:8080

# Deployment
./deploy.sh test        # Test only
./deploy.sh production  # Production only
./deploy.sh both        # Both (default)

# Logs
gcloud run services logs read cbc-test --region=us-west1 --limit=50

# OAuth Setup (first-time)
./utils/setup_oauth_secrets.sh
rm client_secret.json  # Delete after setup

# Annual Season Start (CRITICAL - run each season)
python utils/verify_indexes.py cbc-test        # Test
python utils/verify_indexes.py cbc-register    # Production

# Utilities
python utils/setup_databases.py --dry-run  # Preview
python utils/generate_test_participants.py 50  # Generate test data
```

## Project Structure

**Config:** `config/areas.py` (24 areas A-X), `config/admins.py` (whitelist), `config/settings.py`, `config/colors.py`, `config/organization.py`, `config/email_settings.py`

**Models (year-aware):** `models/participant.py`, `models/area_leader.py`, `models/removal_log.py`

**Routes:** `routes/main.py` (public), `routes/admin.py` (admin), `routes/auth.py` (OAuth), `routes/api.py` (JSON endpoints)

**Frontend:** `static/js/map.js`, `static/js/leaders-map.js`, `static/js/registration.js`, `static/css/main.css`, `static/data/area_boundaries.json`

**Templates:** `templates/base.html`, `templates/index.html`, `templates/auth/login.html`, `templates/admin/*.html`, `templates/errors/*.html`

## Key Implementation Patterns

### Database Configuration
```python
from config.database import get_firestore_client
db, database_id = get_firestore_client()
# Auto-selects: cbc-test (dev/test) or cbc-register (prod)
```

### Year-Based Data
```python
participant_model = ParticipantModel(db)  # Current year
historical_model = ParticipantModel(db, 2024)  # Specific year
historical = participant_model.get_historical_participants('A', years_back=3)
```

### Firestore Query Syntax (MANDATORY)
**Always use modern `FieldFilter` syntax:**

```python
from google.cloud.firestore_v1.base_query import FieldFilter

# CORRECT
query = collection.where(filter=FieldFilter('field_name', '==', value))

# INCORRECT (deprecated)
query = collection.where('field_name', '==', value)
```

### Authentication Flow
1. Google OAuth via `/auth/login` (credentials in Secret Manager)
2. Role determination: Admin (whitelist) → full access, Leader (area-specific), Public (registration only)
3. Decorators: `@require_admin`, `@require_leader`, `@require_auth`

### Area Management
- 24 areas (A-X, no Y), interactive map with clickable polygons
- Auto-assignment for "UNASSIGNED" preference
- No capacity limits

## Important Constraints

### Data Integrity
- Current year: read/write; Historical: read-only (UI enforced)
- Email deduplication across years (most recent wins)
- Explicit year field in all records

### Security
- OAuth credentials in Secret Manager
- Admin whitelist in `config/admins.py`
- No public admin links
- Historical data read-only

### Mobile-First Design
- Primary usage via mobile devices
- Responsive Bootstrap layout
- Touch-optimized map

## Environment

**Required Variables:**
- `GOOGLE_CLOUD_PROJECT=vancouver-cbc-registration`
- `SECRET_KEY` (Flask sessions)

**GCP Services:** Cloud Run, Firestore, OAuth 2.0

**Testing:** `cbc-test.naturevancouver.ca` (test), `cbc-registration.naturevancouver.ca` (prod)

## Common Development Tasks

### OAuth Issues
1. **"OAuth client not found"**: Check for trailing newlines, verify consent screen published
2. **"Google OAuth not configured"**: Verify `init_auth(app)` called, check Secret Manager permissions
3. **Database connection errors**: Check Firestore client init, verify `GOOGLE_CLOUD_PROJECT`

### Managing Admin Access
**Production:** Edit `PRODUCTION_ADMIN_EMAILS` in `config/admins.py`, redeploy

**Test:** Accounts (`cbc-test-admin1@`, `cbc-test-admin2@naturevancouver.ca`) auto-active in test

### Year Transition
Models auto-create new year collections, admin has year selector, historical data read-only

### Map Colors
Centralized in `config/colors.py`:
- Orange `#f58231`: 0-3 registrations
- Maroon `#800000`: 4-8 registrations
- Navy `#000075`: 8+ registrations
- Yellow `#ffe119`: Selected area

### Leader Management
- Interactive map (red=needs leaders, green=has leaders)
- Inline edit/delete with real-time validation
- Manual entry and participant-to-leader promotion
- Multiple leaders per area, one area per leader
- Email automation: twice-daily updates, weekly summaries, admin digest

**Email System Status:**
- ✅ Email generation (`test/email_generator.py`), templates, test UI, timezone handling
- ❌ Needs Google Cloud Email API (currently SMTP)

**Email Components:**
- Generation: `test/email_generator.py`
- Service: `services/email_service.py`
- Templates: `templates/emails/`
- Config: `config/email_settings.py`

### Debugging Deployment
```bash
gcloud run services describe SERVICE --region=us-west1
gcloud run services logs tail SERVICE --region=us-west1
```

**Notes:**
- Can't test locally - use `cbc-test.naturevancouver.ca`
- Project uses git - may need git commands for file operations

## File Modification Guidelines

**Timestamp comments (date only):**
- Python: `# Updated by Claude AI on YYYY-MM-DD`
- Jinja2: `{# Updated by Claude AI on YYYY-MM-DD #}`
- JS/CSS: `/* Updated by Claude AI on YYYY-MM-DD */`

**Important:**
- Don't update SPECIFICATION.md from DEVELOPMENT_NOTES.md (planning vs implementation)
- Throwaway scripts go in `debug/` directory
- Python imports at top of file, not inline
- **NEVER begin replies with "You're right", "You're absolutely correct", etc.** - start directly with analysis
- Avoid "comprehensive" unless specifically instructed

## Test Suite Status (as of 2025-09-22)

**Completed:** Framework architecture, config files, utilities, test accounts, documentation

**Next Steps:** Fix data consistency bugs, implement first test, extend test data generation, Phase 1 tests

**Priorities:** Leader workflows, participant/leader sync, registration flow, CSV export, authentication

**Notes:** Tests run against cloud (cbc-test.naturevancouver.ca), current year for functional tests, year 2000 for isolation

## Documentation Structure (as of 2025-10-12)

**For Volunteers:** `docs/DEPLOYMENT.md` (step-by-step), `README.md` (overview)

**For Developers:** `docs/DEPLOYMENT_TECHNICAL_REFERENCE.md` (technical details), `docs/SPECIFICATION.md` (architecture), `CLAUDE.md` (this file)

**For End Users:** `docs/ADMIN_GUIDE.md`, `docs/LEADER_GUIDE.md` (if exist)

**Utilities:** `utils/verify_indexes.py` (annual season start), `utils/setup_databases.py`, `utils/generate_test_participants.py`, `utils/setup_email_scheduler.sh`
