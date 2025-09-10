# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

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
- `static/js/map.js` - Leaflet.js interactive map with area selection
- `static/js/leaders-map.js` - Leaders page map showing areas needing leaders
- `static/js/registration.js` - Form validation and interactions
- `static/css/main.css` - Bootstrap-based responsive styling
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
1. Edit `config/admins.py` email list
2. Redeploy application: `./deploy.sh both`
3. Test authentication with new admin account at `/admin`

### Year Transition Setup
1. Models automatically create new year collections
2. Admin interface includes year selector
3. Historical data remains accessible read-only
4. Update admin whitelist if coordinators change

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

**Email Automation System (In Development):**
- **Three Email Types**: 
  1. Twice-daily team updates to area leaders when team composition changes
  2. Weekly summaries for areas with no changes (Fridays at 11pm)
  3. Daily admin digest listing unassigned participants
- **Test Environment**: Admin dashboard includes manual email trigger buttons (test server only)
- **Environment Detection**: Uses `TEST_MODE=true` or domain contains 'test' for test server identification
- **Test Mode Behavior**: All emails redirect to birdcount@naturevancouver.ca on test server
- **Race Condition Prevention**: Timestamp selection before queries, update after successful send
- **Production Scheduling**: Cloud Scheduler integration planned for automated triggers

**Email and Access Requirements:**
- Leaders can have non-Google emails (for notifications only)
- Only Google email leaders can access leader UI at `/leader`
- Required leader fields: first_name, last_name, email, cell_phone
- Automated email notifications for team updates and weekly summaries

### Email Automation Development
1. **Test Email Triggers (Test Server Only)**:
   - Access admin dashboard on `cbc-test.naturevancouver.ca/admin`
   - Use email trigger buttons to test each email type on demand
   - All test emails redirect to `birdcount@naturevancouver.ca`
   - Check logs: `gcloud run services logs read cbc-test --region=us-west1 --limit=50`

2. **Email System Components**:
   - **Email Generation**: `utils/email_generator.py` - Core logic for all email types
   - **Email Templates**: `templates/emails/` - HTML templates for team updates, weekly summaries, admin digest
   - **Environment Detection**: `is_test_server()` helper function for test mode behavior
   - **SMTP Configuration**: `config/email_settings.py` - Email service configuration

3. **Production Email Scheduling**:
   - **Cloud Scheduler**: Configure cron jobs for twice-daily and weekly triggers
   - **Pub/Sub Integration**: Consider message queuing for reliable email delivery
   - **Monitoring**: Set up alerts for email delivery failures and processing errors

### Debugging Deployment Issues
1. **Check service configuration**: `gcloud run services describe SERVICE --region=us-west1`
2. **Monitor logs in real-time**: `gcloud run services logs tail SERVICE --region=us-west1`
3. **Verify secrets access**: Check that service account has `secretmanager.secretAccessor` role
4. **Test Firestore connection**: Verify `GOOGLE_CLOUD_PROJECT` and service account permissions