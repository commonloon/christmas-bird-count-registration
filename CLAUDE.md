# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## ⚠️ CRITICAL RULES ⚠️

### Documentation Standards
- **NEVER** describe as "production ready", "feature complete", "finished", or "functionally complete"
- Always treat as work-in-progress requiring ongoing development
- Do not add completion claims to .md files or code comments

### Deployment Constraints
- **NEVER** place application code in `utils/` directory (not deployed to the FullHost app node)
- Application code belongs in `services/`, `models/`, `config/`, or root directory
- **NEVER commit/push/deploy/restart production** without asking first - the user pulls, migrates, and restarts the production server themselves, every time

### Security Requirements
**NEVER include credentials in version-controlled files:**
- No passwords, API keys, tokens in .py, .js, .html, .md, .json, .yaml, .ini files
- Tell user to use environment variables (set via FullHost's app-node "Variables" panel in production, or a local `.env` for dev) or secure channels
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
# CORRECT - Identity-based methods on ParticipantModel (single-table design -
# leadership is is_leader/assigned_area_leader flags on the participant row,
# there is no separate leader model/table)
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

Flask web application for Christmas Bird Count registration - a multi-circle platform (Vancouver, Nanaimo, Comox Spring, and others) rather than a single organization's app. Interactive map/dropdown selection with automatic assignment to areas needing volunteers. Every circle's data is scoped by `circle_slug`; the circle is always resolved from the request's Host header subdomain, with no default/fallback circle (see `app.py`'s `resolve_circle()`, `models/db.py`'s `resolve_default_circle_slug()`).

### Core Architecture
- **Multi-circle, year-scoped data**: shared Postgres tables (`participants`, `removal_log`, etc.) scoped by `(circle_slug, year)`, not per-circle/per-year collections
- **Backend**: Flask + Blueprints, PostgreSQL (SQLAlchemy)
- **Authentication**: magic-link email (signed session cookie), role-based access (Public/Leader/Admin/Super-Admin)
- **Frontend**: Bootstrap 5 + Leaflet.js interactive map
- **Hosting**: FullHost PaaS (migrated off Google Cloud Run/Firestore) - deploy is `git pull` + a manual restart on the production server, not a scripted push

## Essential Commands

```bash
# Development
pip install -r requirements.txt
python app.py  # Serves on localhost:8080 - requires a circle hostname, see docs/TEST_SETUP.md

# Testing
pip install -r tests/requirements.txt
pytest tests/ -v                 # Full suite - see docs/TESTING.md
pytest tests/unit/ -v            # Unit tests only, no server/browser needed

# Utilities
python utils/setup_databases.py --dry-run  # Preview
python utils/generate_test_participants.py 50  # Generate test data
```

Production deployment is `git pull` followed by a manual restart directly on the FullHost app node - there is no deploy script, and the user handles this themselves. Never commit, push, deploy, or restart production without asking first.

## Project Structure

**Config:** `config/areas.py` (static fallback area data), `config/admins.py` (global admin whitelist), `config/colors.py`, `config/organization.py`, `config/email_settings.py`, `config/database.py`, `config/rate_limits.py`

**Models (circle- and year-aware):** `models/participant.py` (single-table participant + leadership flags), `models/removal_log.py`, `models/circle.py` (circle/area/circle-admin management), `models/db.py` (SQLAlchemy table definitions)

**Routes:** `routes/main.py` (public), `routes/admin.py` (admin, mounted at `/bigbird`), `routes/leader.py` (area leader, mounted at `/leader`), `routes/auth.py` (magic-link auth), `routes/api.py` (JSON endpoints), `routes/scheduler.py` (Task Scheduler email triggers)

**Frontend:** `static/js/map.js`, `static/js/leaders-map.js`, `static/js/registration.js`, `static/css/main.css`

**Templates:** `templates/base.html`, `templates/index.html`, `templates/auth/*.html`, `templates/admin/*.html`, `templates/errors/*.html`

## Key Implementation Patterns

### Database Configuration
```python
from config.database import get_db_session
db = get_db_session()
```

### Circle- and Year-Aware Data
```python
participant_model = ParticipantModel(db, year, circle_slug)  # circle_slug required - no default
historical_model = ParticipantModel(db, 2024, circle_slug)
historical = participant_model.get_historical_participants('A', years_back=3)
```

### Authentication Flow
1. Magic-link email to `/auth/login` - no password, no OAuth
2. Role determination (`routes/auth.py`'s `get_user_role()`), most to least privileged: `super_admin` (global whitelist, `config/admins.py`, full access to every circle) → `admin` (circle-admin for this circle only) → `leader` (area leader for this circle) → `public`
3. Decorators: `@require_super_admin`, `@require_admin`, `@require_leader`

### Area Management
- Areas are circle-specific and DB-backed (`models/circle.py`'s `CircleAreaModel`), imported per circle from a KML file via the admin UI - `config/areas.py`'s `AREA_CONFIG` is a static fallback only, not the live source of truth
- Auto-assignment for "UNASSIGNED" preference
- No capacity limits

## Important Constraints

### Data Integrity
- Current year: read/write; Historical: read-only (UI enforced)
- Email deduplication across years (most recent wins)
- Explicit `circle_slug` and year field in every record - never assume/default a circle

### Security
- No OAuth/Secret Manager - the only secrets are env vars (`SECRET_KEY`, `SMTP2GO_USERNAME`/`PASSWORD`, `SCHEDULER_SECRET`), set via FullHost's app-node "Variables" panel in production or `.env` locally
- Admin whitelist in `config/admins.py`; per-circle admins in the `circle_admins` table
- No public admin links
- Historical data read-only

### Mobile-First Design
- Primary usage via mobile devices
- Responsive Bootstrap layout
- Touch-optimized map

## Environment

**Required Variables:**
- `DATABASE_URL` (Postgres connection string)
- `SECRET_KEY` (Flask sessions)
- `SMTP2GO_USERNAME` / `SMTP2GO_PASSWORD` (email sending - silently no-ops without these)
- `SCHEDULER_SECRET` (bearer token for `routes/scheduler.py`'s Task Scheduler-triggered email routes)

**Hosting:** FullHost PaaS (app node) + PostgreSQL

**Local dev/testing:** dedicated `test` circle via a `.test`-TLD hostname - see `docs/TEST_SETUP.md`

## Common Development Tasks

### Managing Admin Access
**Global/production:** Edit `PRODUCTION_ADMIN_EMAILS` in `config/admins.py`, ask before deploying

**Per-circle:** managed via the `circle_admins` table (admin UI), not a code change

**Test:** Accounts (`cbc-test-admin1@`, `cbc-test-admin2@naturevancouver.ca`) auto-active whenever `config/admins.py`'s `is_test_environment()` is true

### Year Transition
Models auto-create new year data on first write, admin has year selector, historical data read-only

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

**Email Components:**
- Generation: `test/email_generator.py` (real production code despite the directory name - the digest generators)
- Service: `services/email_service.py` (SMTP via SMTP2GO)
- Templates: `templates/emails/`
- Config: `config/email_settings.py`
- Triggers: `routes/scheduler.py`, called by FullHost's Task Scheduler; runs once per circle

### Debugging Production
Log/service inspection is via the FullHost dashboard, not `gcloud` - there's no CLI equivalent confirmed yet. Ask the user to check dashboard logs rather than guessing at a command.

**Notes:**
- Can test locally now - see `docs/TEST_SETUP.md` (dedicated `.test`-TLD circle hostname, local Postgres)
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

## Test Suite

353 pytest tests (`tests/`) run entirely locally against a dedicated `test` circle and local Postgres - no cloud dependency. See `docs/TEST_SETUP.md` (setup), `docs/TESTING.md` (running tests), `docs/TEST_SUITE_SPEC.md` (what each part covers).

## Documentation Structure

**Current and accurate:** `docs/TEST_SETUP.md`, `docs/TESTING.md`, `docs/TEST_SUITE_SPEC.md`, `CLAUDE.md` (this file)

**Known stale (pre-FullHost-migration, GCP/Cloud Run/OAuth-era) - a rewrite is planned but not yet done, so verify against the live code before trusting these:** `docs/DEPLOYMENT.md`, `docs/DEPLOYMENT_TECHNICAL_REFERENCE.md`, `docs/DEPLOYMENT_WORKSHEET.md`, `docs/DEVELOPER_GUIDE.md`, `docs/SPECIFICATION.md`, `docs/TEST_COVERAGE.md`, `README.md`

**Utilities:** `utils/setup_databases.py`, `utils/generate_test_participants.py`, `utils/setup_email_scheduler.sh` - most documents are in the docs/ directory