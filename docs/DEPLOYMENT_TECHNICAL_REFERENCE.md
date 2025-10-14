# CBC Registration - Technical Deployment Reference
<!-- Updated by Claude AI on 2025-10-14 -->

This document provides technical details for developers and system administrators working with the CBC Registration system.

**Before starting**, complete the [Deployment Planning Worksheet](DEPLOYMENT_WORKSHEET.md) to organize all configuration values for your installation.

**For volunteer-friendly deployment procedures**, see [DEPLOYMENT.md](DEPLOYMENT.md).

---

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Environment Configuration](#environment-configuration)
- [Firestore Database Architecture](#firestore-database-architecture)
- [Index Management](#index-management)
- [OAuth Implementation](#oauth-implementation)
- [Cloud Run Deployment](#cloud-run-deployment)
- [Email Scheduler System](#email-scheduler-system)
- [Security Configuration](#security-configuration)
- [Troubleshooting Guide](#troubleshooting-guide)

---

## Architecture Overview

### Technology Stack

- **Application**: Python 3.13, Flask with Blueprint routing
- **Database**: Google Firestore (multi-database architecture)
- **Authentication**: Google Identity Services OAuth
- **Hosting**: Google Cloud Run (serverless containers)
- **Email**: SMTP2GO (configurable provider)
- **Scheduling**: Google Cloud Scheduler
- **Region**: Configurable via `GCP_LOCATION` in `config/cloud.py` (default: `us-west1` Oregon)

### Service Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    User Browser                         │
└────────────┬────────────────────────────────────────────┘
             │
             ├─── Public Routes (/register, /area-leader-info)
             │
             ├─── OAuth Routes (/auth/login, /auth/callback)
             │
             └─── Protected Routes
                  ├─── Admin (/admin/*)
                  └─── Leader (/leader/*)
                       │
                       ▼
         ┌──────────────────────────────────────┐
         │   Google Cloud Run Service           │
         │   (TEST_SERVICE / PRODUCTION_SERVICE)│
         └──────┬───────────────────────────────┘
                │
                ├──── Google Firestore (TEST_DATABASE / PRODUCTION_DATABASE)
                │     └─── Year-based collections (participants_YYYY)
                │
                ├──── Google Secret Manager (OAuth credentials)
                │
                └──── SMTP Email Provider (configurable)
```

### Two-Environment Strategy

**Configuration**: All environment-specific values defined in `config/cloud.py`

**Test Environment**:
- Service: `TEST_SERVICE` (configured in `config/cloud.py`)
- Domain: `TEST_BASE_URL` (e.g., `https://cbc-test.myclub.org`)
- Database: `TEST_DATABASE` (configured in `config/cloud.py`)
- Purpose: Development, testing, training
- `TEST_MODE=true`: Redirects all emails to test recipient

**Production Environment**:
- Service: `PRODUCTION_SERVICE` (configured in `config/cloud.py`)
- Domain: `PRODUCTION_BASE_URL` (e.g., `https://cbc-registration.myclub.org`)
- Database: `PRODUCTION_DATABASE` (configured in `config/cloud.py`)
- Purpose: Live registration
- `TEST_MODE=false`: Normal email delivery

---

## Environment Configuration

### Environment Variables

Both Cloud Run services use these environment variables (set by `deploy.sh` from config files):

```bash
# Application environment
FLASK_ENV=production|development
TEST_MODE=true|false
GOOGLE_CLOUD_PROJECT=<YOUR-PROJECT-ID>    # From config/cloud.py: GCP_PROJECT_ID
DISPLAY_TIMEZONE=<YOUR-TIMEZONE>          # From config/organization.py: DISPLAY_TIMEZONE
FROM_EMAIL=<YOUR-EMAIL>                   # From config/organization.py: FROM_EMAIL

# Secrets (mounted from Secret Manager - standard names across all installations)
GOOGLE_CLIENT_ID=/secrets/google-oauth-client-id
GOOGLE_CLIENT_SECRET=/secrets/google-oauth-client-secret
SECRET_KEY=/secrets/flask-secret-key
SMTP2GO_USERNAME=/secrets/smtp2go-username          # Or other provider
SMTP2GO_PASSWORD=/secrets/smtp2go-password          # Or other provider
```

### Configuration Files

**Cloud Platform Settings** (`config/cloud.py`):
- GCP project ID and region
- Cloud Run service names (test and production)
- Firestore database names (test and production)
- Base domain for URL construction
- Secret Manager secret names (standard across installations)

**Organization Settings** (`config/organization.py`):
- Organization name and contact info
- Count event details and URLs
- Display timezone for email timestamps
- Test recipient email address
- Email sender configuration

**Admin Configuration** (`config/admins.py`):
- Production admin email whitelist
- Test admin accounts (automatically added in test mode)
- Environment-based admin resolution

**Database Configuration** (`config/database.py`):
- Automatic database selection based on environment
- Reads `TEST_DATABASE` and `PRODUCTION_DATABASE` from `config/cloud.py`
- `TEST_MODE` or `FLASK_ENV=development` → test database
- Otherwise → production database

**Area Definitions** (`config/areas.py`):
- Static area configuration (no year dependency)
- Admin-assignment-only flags
- Dynamic area code validation
- Supports any naming scheme (letters, numbers, custom codes)

---

## Firestore Database Architecture

### Multi-Database Design

The application uses **named databases** (not the default database), configured in `config/cloud.py`:

```python
from config.database import get_firestore_client

db, database_id = get_firestore_client()
# Returns: (firestore.Client(database=TEST_DATABASE), TEST_DATABASE)
# or:      (firestore.Client(database=PRODUCTION_DATABASE), PRODUCTION_DATABASE)
# Database names from config/cloud.py: TEST_DATABASE and PRODUCTION_DATABASE
```

**Critical**: Always use `firestore.Client(database=database_name)`, never `firestore.Client()` (which uses the default database).

### Year-Based Collections

Data is organized by year to support multi-year historical access:

```
<TEST-DATABASE>/                    # e.g., my-club-test
├── participants_2025/
│   ├── doc1 (first_name, last_name, email, is_leader, ...)
│   ├── doc2
│   └── ...
├── participants_2024/
├── removal_log_2025/
│   ├── doc1 (participant_name, area_code, removed_at, ...)
│   └── ...
└── removal_log_2024/
```

**Key Design Principles**:
- Each document includes explicit `year` field for data integrity
- Collections auto-create on first write
- Historical data is read-only (UI enforced)
- Email deduplication across years (most recent wins)

### Data Models

**Participant Schema** (`participants_YYYY`):
```python
{
    'id': auto_generated,
    'first_name': str,
    'last_name': str,
    'email': str,  # Normalized to lowercase
    'phone': str,  # Primary phone
    'phone2': str,  # Secondary phone
    'skill_level': 'Newbie|Beginner|Intermediate|Expert',
    'experience': 'None|1-2 counts|3+ counts',
    'preferred_area': 'A-X|UNASSIGNED',
    'participation_type': 'regular|FEEDER',
    'has_binoculars': bool,
    'spotting_scope': bool,
    'notes_to_organizers': str,
    'interested_in_leadership': bool,
    'interested_in_scribe': bool,

    # Leadership fields (unified model)
    'is_leader': bool,
    'assigned_area_leader': str | None,
    'leadership_assigned_by': str | None,
    'leadership_assigned_at': timestamp | None,
    'leadership_removed_by': str | None,
    'leadership_removed_at': timestamp | None,

    # Metadata
    'auto_assigned': bool,
    'assigned_by': str | None,
    'assigned_at': timestamp | None,
    'created_at': timestamp,
    'updated_at': timestamp,
    'year': int
}
```

**Removal Log Schema** (`removal_log_YYYY`):
```python
{
    'participant_name': str,
    'participant_email': str,
    'area_code': str,
    'removed_by': str,  # Admin email
    'reason': str,
    'removed_at': timestamp,
    'year': int,
    'emailed': bool,
    'emailed_at': timestamp | None
}
```

---

## Index Management

### Why Indexes Are Required

Firestore requires composite indexes for queries with multiple filters or ordering:

```python
# This query requires a composite index:
query = (collection
    .where(filter=FieldFilter('email', '==', email))
    .where(filter=FieldFilter('is_leader', '==', True)))
```

Without the index, Firestore returns an error with a URL to create it manually.

### Required Indexes

**Participants Collection** (`participants_YYYY`):

1. **Identity-based queries**: `(email, first_name, last_name)`
   - Used for family email support
   - Duplicate prevention

2. **Leadership assignment**: `(is_leader, assigned_area_leader)`
   - Get leaders by area
   - Leadership management

3. **Leadership interest**: `(interested_in_leadership, is_leader)`
   - Find potential leaders
   - Filter non-leaders who want to lead

4. **Email-based verification**: `(email, is_leader)`
   - Verify leader status by email
   - Authentication checks

5. **Area-specific verification**: `(email, is_leader, assigned_area_leader)`
   - Verify leader for specific area
   - Scoped authentication

**Removal Log Collection** (`removal_log_YYYY`):

1. **Email notification tracking**: `(emailed, area_code)`
   - Find pending notifications
   - Group by area

2. **Area history (ascending)**: `(area_code, removed_at ASC)`
   - Change detection queries
   - Historical lookups

3. **Area history (descending)**: `(area_code, removed_at DESC)`
   - Recent removals first
   - Admin interface sorting

### Index Creation Process

**Automated via `verify_indexes.py`**:
```bash
python utils/verify_indexes.py <TEST-DATABASE>      # Example: my-club-test
python utils/verify_indexes.py <PROD-DATABASE>      # Example: my-club-register
```

The script:
1. Checks if year collections exist
2. Creates dummy data if `removal_log_YYYY` doesn't exist
3. Compares required indexes with existing indexes
4. Creates missing indexes via Firestore Admin API
5. Indexes build in background (takes minutes)

**Manual Fallback**:
If the script fails, Firestore error messages include URLs like:
```
https://console.firebase.google.com/project/PROJECT/firestore/indexes?create_composite=...
```
Click the URL to create the index manually.

### Index Lifecycle

- **Creation**: Admin API starts build process
- **Building**: Index state = `CREATING` (minutes to hours)
- **Ready**: Index state = `READY` (queries work)
- **Persistence**: Indexes persist across deployments

**Note**: Application works during `CREATING` state, but queries may be slower or fail temporarily.

---

## OAuth Implementation

### Google Identity Services

The application uses **Google Identity Services** (not traditional OAuth redirect flow):

```javascript
// Client-side: Google Sign-In button triggers POST
google.accounts.id.initialize({
    client_id: 'YOUR_CLIENT_ID',
    callback: handleCredentialResponse
});

// Callback POSTs JWT to server
function handleCredentialResponse(response) {
    fetch('/auth/oauth/callback', {
        method: 'POST',
        body: JSON.stringify({ credential: response.credential })
    });
}
```

### Authentication Flow

1. **User clicks login** → Redirected to `/auth/login`
2. **Google Sign-In rendered** → User chooses Google account
3. **JWT token generated** → Posted to `/auth/oauth/callback`
4. **Server verifies token** → Validates with Google API
5. **Role determination**:
   - Email in `PRODUCTION_ADMIN_EMAILS` → **admin**
   - Has `is_leader=True` in current year → **leader**
   - Otherwise → **public**
6. **Session created** → Flask session stores user info
7. **Redirect** → Admin/leader dashboard or registration page

### OAuth Client Configuration

**Required Setup** (Google Cloud Console):

1. **Application Type**: Web application
2. **Authorized JavaScript Origins**:
   - `<TEST_BASE_URL>` (e.g., `https://cbc-test.myclub.org`)
   - `<PRODUCTION_BASE_URL>` (e.g., `https://cbc-registration.myclub.org`)
3. **Authorized Redirect URIs**: **None** (not used with Identity Services)
4. **OAuth Consent Screen**: Must be **published** (not in testing mode)

**Note**: URLs are automatically constructed from `SERVICE_*` + `BASE_DOMAIN` in `config/cloud.py`

### Secret Manager Storage

OAuth credentials stored as secrets:

```bash
# Client ID
gcloud secrets create google-oauth-client-id --data-file=client_id.txt

# Client secret
gcloud secrets create google-oauth-client-secret --data-file=client_secret.txt

# Flask session key
gcloud secrets create flask-secret-key --data-file=secret_key.txt
```

**Security**: Service account needs `secretmanager.secretAccessor` role.

### Common OAuth Issues

**"OAuth client not found"**:
- Trailing newlines in secret values → Use `.strip()` when reading
- Wrong project → Verify `GOOGLE_CLOUD_PROJECT`

**"Consent screen not published"**:
- OAuth consent screen in "Testing" mode → Publish it
- Only test users can log in when in testing mode

**"Invalid redirect URI"**:
- Using Identity Services → No redirect URIs needed
- Remove all redirect URIs from OAuth client config

---

## Cloud Run Deployment

### Dockerfile Configuration

```dockerfile
FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 app:app
```

**Key Settings**:
- **Workers**: 1 (Cloud Run handles concurrency)
- **Threads**: 8 (handles multiple requests per instance)
- **Timeout**: 0 (Cloud Run manages timeouts)
- **Port**: `$PORT` (Cloud Run provides dynamically)

### Deployment via `deploy.sh`

```bash
#!/bin/bash
# Reads configuration from config/cloud.py and config/organization.py
# Deploys to specified environment(s)

./deploy.sh test        # Test only
./deploy.sh production  # Production only
./deploy.sh both        # Both environments
```

**What the script does**:
1. Reads configuration from `config/cloud.py` and `config/organization.py`
2. Displays loaded configuration (project, region, services, domains)
3. Builds Docker image via Cloud Build
4. Deploys to Cloud Run with environment variables
5. Mounts secrets from Secret Manager (standard names)
6. Enables unauthenticated access (app handles auth)
7. Uses region from `GCP_LOCATION` in config

### Manual Deployment

```bash
gcloud run deploy <SERVICE-NAME> \
    --source . \
    --platform managed \
    --region <GCP-LOCATION> \
    --allow-unauthenticated \
    --set-env-vars FLASK_ENV=development,TEST_MODE=true,DISPLAY_TIMEZONE=<YOUR-TIMEZONE>,GOOGLE_CLOUD_PROJECT=<YOUR-PROJECT-ID> \
    --update-secrets GOOGLE_CLIENT_ID=google-oauth-client-id:latest \
    --update-secrets GOOGLE_CLIENT_SECRET=google-oauth-client-secret:latest \
    --update-secrets SECRET_KEY=flask-secret-key:latest
```

**Note**: Replace `<SERVICE-NAME>`, `<GCP-LOCATION>`, `<YOUR-TIMEZONE>`, and `<YOUR-PROJECT-ID>` with values from your `config/cloud.py` and `config/organization.py` files.

### Service Configuration

**Scaling**:
- Min instances: 0 (scale to zero during low traffic)
- Max instances: 100 (automatically scales based on load)
- Concurrency: 80 requests per instance

**Resources**:
- CPU: 1 vCPU
- Memory: 512 MB (adjustable via `--memory` flag)
- Timeout: 300 seconds (5 minutes)

**Networking**:
- Ingress: All traffic allowed
- VPC: Not required (uses public internet)

---

## Email Scheduler System

### Cloud Scheduler Architecture

Automated emails triggered by Cloud Scheduler via HTTP POST to OIDC-protected routes:

```
Cloud Scheduler Job → OIDC Token → Cloud Run Route
                      (service account)   (verified)
```

### Email Types & Schedules

1. **Team Updates** (twice daily):
   - Morning: 6:00 AM (when new registrations likely)
   - Afternoon: 6:00 PM (after day's registrations)
   - Triggers: Participant added, removed, reassigned, email changed

2. **Weekly Summaries** (Fridays 11:00 PM):
   - Areas with no changes in past week
   - Provides full team roster

3. **Admin Digest** (daily 6:00 PM):
   - Lists unassigned participants
   - Only sent if unassigned participants exist

### Service Account Setup

```bash
# Create dedicated service account
gcloud iam service-accounts create cloud-scheduler-invoker \
    --display-name="Cloud Scheduler Email Invoker"

# Grant Cloud Run Invoker role (for each service)
gcloud run services add-iam-policy-binding <TEST-SERVICE> \
    --region=<GCP-LOCATION> \
    --member="serviceAccount:cloud-scheduler-invoker@<YOUR-PROJECT-ID>.iam.gserviceaccount.com" \
    --role="roles/run.invoker"

gcloud run services add-iam-policy-binding <PROD-SERVICE> \
    --region=<GCP-LOCATION> \
    --member="serviceAccount:cloud-scheduler-invoker@<YOUR-PROJECT-ID>.iam.gserviceaccount.com" \
    --role="roles/run.invoker"
```

### Scheduler Job Creation

**Automated via `setup_email_scheduler.sh`**:
```bash
./utils/setup_email_scheduler.sh test
./utils/setup_email_scheduler.sh production
./utils/setup_email_scheduler.sh delete-test  # Cleanup
```

**Manual Job Creation**:
```bash
gcloud scheduler jobs create http <SERVICE-NAME>-team-updates-morning \
    --location=<GCP-LOCATION> \
    --schedule="0 6 * * *" \
    --time-zone="<YOUR-TIMEZONE>" \
    --uri="<TEST_BASE_URL>/scheduler/team-updates" \
    --http-method=POST \
    --oidc-service-account-email="cloud-scheduler-invoker@<YOUR-PROJECT-ID>.iam.gserviceaccount.com" \
    --oidc-token-audience="<TEST_BASE_URL>"
```

### OIDC Authentication

Routes verify OIDC tokens to prevent unauthorized access:

```python
def verify_cloud_scheduler_request():
    """Verify request came from Cloud Scheduler via OIDC token."""
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return False

    token = auth_header[7:]  # Remove "Bearer " prefix

    try:
        # Verify JWT token with Google's public keys
        request_obj = google.auth.transport.requests.Request()
        id_info = id_token.verify_oauth2_token(
            token, request_obj,
            audience=url_for('scheduler.team_updates', _external=True)
        )

        # Check service account email
        email = id_info.get('email', '')
        return 'cloud-scheduler-invoker' in email
    except Exception as e:
        logger.error(f"Token verification failed: {e}")
        return False
```

### Email Generation Logic

**Change Detection**:
- Queries participants since last email timestamp
- Compares current roster with previous roster
- Generates diff (additions, removals, changes)

**Timestamp Management**:
1. Select timestamp **before** querying (prevents race conditions)
2. Execute queries with that timestamp
3. Generate emails
4. Update last_email_sent timestamp **after** successful send

**Test Mode Behavior**:
- All emails redirect to `TEST_RECIPIENT` from config
- Subject line prefixed with `[TEST]`
- Service URL adjusted to test domain

---

## Security Configuration

### Input Sanitization

All user inputs sanitized via `services/security.py`:

```python
from services.security import sanitize_name, sanitize_email, sanitize_phone

# Sanitizers limit length and strip dangerous characters
name = sanitize_name(user_input)        # Max 100 chars, letters/spaces/hyphens
email = sanitize_email(user_input)      # Max 254 chars, lowercase, valid email chars
phone = sanitize_phone(user_input)      # Max 20 chars, digits/spaces/hyphens/parens
notes = sanitize_notes(user_input)      # Max 1000 chars, allows newlines
```

### CSRF Protection

Flask-WTF CSRFProtect enabled globally:

```python
# All POST forms include token
<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">

# AJAX requests include token
fetch('/api/endpoint', {
    method: 'POST',
    headers: {'X-CSRFToken': '{{ csrf_token() }}'},
    body: JSON.stringify(data)
});
```

**Exempt routes**: OAuth callback (JWT verification provides security)

### Rate Limiting

Flask-Limiter protects against abuse:

```python
from services.limiter import limiter

# Production limits
@limiter.limit("10/minute")  # Registration
@limiter.limit("20/minute")  # API calls
@limiter.limit("5/minute")   # Authentication

# Test mode: 50/minute (higher limits for testing)
```

### Template Security

Jinja2 auto-escaping enabled + explicit escaping:

```html
<!-- Always use |e filter for user data -->
{{ participant.first_name|e }} {{ participant.last_name|e }}

<!-- JavaScript context: use |tojson -->
<script>
const userName = {{ participant.first_name|tojson }};
</script>
```

---

## Troubleshooting Guide

### Database Connection Errors

**Error**: `Database '<DATABASE-NAME>' does not exist`

**Solution**:
```bash
# Ensure config/cloud.py has correct database names
python utils/setup_databases.py
```

**Cause**: Databases not created or wrong database name in `config/cloud.py`.

**Prevention**:
- Always use `get_firestore_client()` helper function
- Verify `TEST_DATABASE` and `PRODUCTION_DATABASE` in `config/cloud.py`

---

### Index Creation Errors

**Error**: `FAILED_PRECONDITION: The query requires an index`

**Solution**:
```bash
# Automated (use your database name from config/cloud.py)
python utils/verify_indexes.py <TEST-DATABASE>
python utils/verify_indexes.py <PROD-DATABASE>

# Manual (click URL in error message)
https://console.firebase.google.com/project/.../indexes?create_composite=...
```

**Cause**: Missing composite index for multi-field query.

**Prevention**: Run `verify_indexes.py` for both databases at season start.

---

### OAuth Authentication Failures

**Error**: `invalid_client` or `OAuth client not found`

**Possible Causes**:
1. Trailing newlines in secrets
2. Wrong client ID
3. Consent screen not published

**Solution**:
```bash
# Check secret values (without revealing content)
gcloud secrets versions access latest --secret=google-oauth-client-id | wc -c

# Should match expected length (typically 72 chars for client ID)
# If longer, secret has trailing newline

# Fix by recreating secret with .strip()
echo -n "YOUR_CLIENT_ID" | gcloud secrets versions add google-oauth-client-id --data-file=-
```

---

### Deployment Failures

**Error**: `Build failed` or `Image not found`

**Diagnosis**:
```bash
# Check build logs
gcloud builds list --limit=5
gcloud builds log BUILD_ID
```

**Common Causes**:
1. Syntax error in Python code
2. Missing dependency in `requirements.txt`
3. Dockerfile misconfiguration
4. Insufficient Cloud Build permissions

**Solution**: Fix code/config, redeploy.

---

### Email Delivery Issues

**Error**: Emails not sending

**Diagnosis**:
```bash
# Check scheduler job status (use your values from config)
gcloud scheduler jobs describe <SERVICE-NAME>-team-updates-morning --location=<GCP-LOCATION>

# Check recent executions
gcloud scheduler jobs describe <JOB-NAME> --location=<GCP-LOCATION> | grep "lastAttemptTime\|status"

# Check application logs
gcloud run services logs read <SERVICE-NAME> --region=<GCP-LOCATION> --limit=100 | grep "email\|scheduler"
```

**Common Causes**:
1. OIDC token verification fails → Check service account permissions
2. SMTP credentials invalid → Verify email settings in config
3. Routes not registered → Check `TEST_MODE` environment variable
4. Scheduler job paused → Resume with `gcloud scheduler jobs resume`

---

### Performance Issues

**Symptom**: Slow queries, timeouts

**Diagnosis**:
```bash
# Check if indexes are building (use your database name)
gcloud firestore indexes composite list --database=<TEST-DATABASE>

# Look for STATE=CREATING (indexes still building)
```

**Solutions**:
1. Wait for indexes to finish building (check STATE=READY)
2. Add missing indexes via `verify_indexes.py`
3. Optimize queries to use existing indexes
4. Increase Cloud Run memory/CPU if needed

---

## Advanced Topics

### Custom Area Codes

The system supports any area naming scheme (letters, numbers, custom codes):

```python
# config/areas.py
AREA_CONFIG = {
    '101': {'name': 'North Region', ...},    # Numbers
    'ALPHA': {'name': 'Alpha Sector', ...},  # Words
    'A': {'name': 'Area A', ...}             # Letters
}
```

Dynamic validation adapts to configured areas.

### Multi-Year Data Migration

To migrate data from previous years:

```python
# Example: Copy 2024 participants to 2025 as a starting point
from models.participant import ParticipantModel

db, _ = get_firestore_client()
model_2024 = ParticipantModel(db, 2024)
model_2025 = ParticipantModel(db, 2025)

participants = model_2024.get_all_participants()
for p in participants:
    # Modify as needed
    p['year'] = 2025
    p['created_at'] = datetime.now()
    del p['id']  # Generate new ID
    model_2025.add_participant(p)
```

### Database Backups

Firestore backups configured via `BACKUPS.md`:

```bash
# Manual backup (use your database name from config/cloud.py)
gcloud firestore export gs://<YOUR-BUCKET>/backup-$(date +%Y%m%d) \
    --database=<TEST-DATABASE>

# Automated daily backups via Cloud Scheduler
# See BACKUPS.md for setup instructions
```

### Monitoring & Alerts

**Cloud Monitoring Setup**:
1. Create uptime checks for both services
2. Configure alerts for:
   - Service downtime
   - High error rates (>5% of requests)
   - Slow response times (>2 seconds)
   - Database connection failures

**Log-Based Metrics**:
- Track registrations per day
- Monitor authentication failures
- Alert on CSRF token failures (potential attack)

---

## Development Workflow

### Local Development

**Note**: Cannot run locally due to Google Cloud service dependencies (Firestore, Secret Manager). All development must be done on test deployment.

**Workflow**:
1. Make code changes locally
2. Deploy to test: `./deploy.sh test`
3. Test at `<TEST_BASE_URL>` (your test domain from `config/cloud.py`)
4. View logs: `gcloud run services logs tail <TEST-SERVICE> --region=<GCP-LOCATION>`
5. Iterate until working
6. Deploy to production: `./deploy.sh production`

**Configuration**: Update `config/cloud.py` with your project and service names before deploying.

### Testing Strategy

**Unit Tests** (`tests/unit/`):
- Model operations (Firestore mocked)
- Security functions
- Configuration helpers

**Integration Tests** (`tests/integration/`):
- Full workflows against live `cbc-test` database
- OAuth authentication flows
- Email generation logic

**Run Tests**:
```bash
pytest tests/unit/ -v              # Fast, mocked
pytest tests/integration/ -v       # Slow, real cloud services
pytest tests/ -m identity -v       # Identity-based tests only
```

### Code Organization

```
app.py                  # Flask app entry point
config/                 # All configuration
models/                 # Database operations
routes/                 # URL handlers (Blueprints)
services/               # Business logic
templates/              # Jinja2 HTML templates
static/                 # CSS, JS, images
utils/                  # Deployment scripts (not deployed)
tests/                  # Test suite
docs/                   # Documentation
```

---

## Additional Resources

- **Deployment Planning Worksheet**: [DEPLOYMENT_WORKSHEET.md](DEPLOYMENT_WORKSHEET.md)
- **Main Deployment Guide**: [DEPLOYMENT.md](DEPLOYMENT.md)
- **OAuth Setup**: [OAUTH-SETUP.md](OAUTH-SETUP.md)
- **Email Testing**: [EMAIL_SCHEDULER_TESTING.md](EMAIL_SCHEDULER_TESTING.md)
- **Application Spec**: [SPECIFICATION.md](SPECIFICATION.md)
- **Development Guide**: [CLAUDE.md](CLAUDE.md)
- **Backup Setup**: [BACKUPS.md](BACKUPS.md)

**Cloud Documentation**:
- Cloud Run: https://cloud.google.com/run/docs
- Firestore: https://cloud.google.com/firestore/docs
- Secret Manager: https://cloud.google.com/secret-manager/docs
- Cloud Scheduler: https://cloud.google.com/scheduler/docs
