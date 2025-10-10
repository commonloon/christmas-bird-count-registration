# Deployment Guide - Christmas Bird Count Registration App
<!-- Updated by Claude AI on 2025-10-07 -->

This guide covers deploying the CBC Registration application to Google Cloud Run. The system is designed to be portable for other bird count clubs.

## Overview

**Architecture:**
- **Platform**: Google Cloud Run (serverless containers)
- **Database**: Google Firestore (two databases: `cbc-test` and `cbc-register`)
- **Authentication**: Google OAuth with role-based access (admin/leader/public)
- **Email**: SMTP2GO for automated notifications
- **Scheduling**: Google Cloud Scheduler for automated email triggers

**Environments:**
- **Test**: `cbc-test.naturevancouver.ca` - Uses `cbc-test` database, TEST_MODE=true
- **Production**: `cbc-registration.naturevancouver.ca` - Uses `cbc-register` database

## Prerequisites

Before deployment, ensure you have:

1. **Google Cloud Account**: Access to a Google Cloud project
2. **Domain Access**: Ability to configure DNS records for your custom domain
3. **Google Cloud CLI**: Installed and authenticated
4. **Organization Configuration**: Update `config/organization.py` with your club's information

### Install Google Cloud CLI

#### Windows
```powershell
# Download from https://cloud.google.com/sdk/docs/install
# Run installer and restart PowerShell
gcloud version
```

#### macOS
```bash
brew install google-cloud-sdk
```

#### Linux (Ubuntu/Debian)
```bash
echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main" | sudo tee -a /etc/apt/sources.list.d/google-cloud-sdk.list
curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | sudo apt-key --keyring /usr/share/keyrings/cloud.google.gpg add -
sudo apt-get update && sudo apt-get install google-cloud-cli
```

### Authenticate with Google Cloud

```bash
# Authenticate
gcloud auth login

# Set your project ID (replace with your project)
gcloud config set project YOUR-PROJECT-ID

# Verify
gcloud config list
```

## Initial Setup (One-Time)

### 1. Configure Your Organization

Edit `config/organization.py` with your club's information:

```python
ORGANIZATION_NAME = "Your Bird Club Name"
ORGANIZATION_WEBSITE = "https://yourclub.org"
ORGANIZATION_CONTACT = "info@yourclub.org"
COUNT_CONTACT = "cbc@yourclub.org"
COUNT_EVENT_NAME = "Your Christmas Bird Count"
COUNT_INFO_URL = "https://yourclub.org/cbc-info"
DISPLAY_TIMEZONE = "America/Your_City"  # See https://en.wikipedia.org/wiki/List_of_tz_database_time_zones
TEST_RECIPIENT = "your-test-email@yourclub.org"
```

Update `get_registration_url()` and `get_admin_url()` functions with your domain names.

### 2. Enable Required Google Cloud APIs

```bash
gcloud services enable run.googleapis.com
gcloud services enable firestore.googleapis.com
gcloud services enable cloudbuild.googleapis.com
gcloud services enable secretmanager.googleapis.com
gcloud services enable cloudscheduler.googleapis.com
```

### 3. Create Firestore Databases

The application uses separate databases for test and production:

```bash
# Install Python dependencies for setup script
pip install -r utils/requirements.txt

# Preview what will be created
python utils/setup_databases.py --dry-run

# Create databases and indexes
python utils/setup_databases.py

# Or skip index creation (faster, but may have runtime delays initially)
python utils/setup_databases.py --skip-indexes
```

This creates:
- **cbc-test**: Test environment database
- **cbc-register**: Production environment database

Both databases use identical schema with year-based collections (e.g., `participants_2025`, `area_leaders_2025`).

### 4. Configure OAuth Authentication

OAuth is required for admin and area leader access. See **[OAUTH-SETUP.md](OAUTH-SETUP.md)** for complete setup instructions.

**Quick summary:**
1. Create OAuth consent screen and client credentials in Google Cloud Console
2. Download `client_secret.json`
3. Run `./utils/setup_oauth_secrets.sh` to store credentials in Secret Manager
4. Delete `client_secret.json`
5. Publish OAuth consent screen (required for production use)

### 5. Update Admin Whitelist

Edit `config/admins.py` to add admin email addresses:

```python
PRODUCTION_ADMIN_EMAILS = [
    'your-admin@yourclub.org',
    'another-admin@yourclub.org'
]
```

## Deployment

### Using the Deployment Script

The `deploy.sh` script handles deployment with proper environment configuration:

```bash
# Deploy to test environment only
./deploy.sh test

# Deploy to production environment only
./deploy.sh production

# Deploy to both environments (default)
./deploy.sh both
```

The script automatically:
- Reads `DISPLAY_TIMEZONE` from `config/organization.py`
- Sets appropriate environment variables for each environment
- Builds and deploys Docker containers to Cloud Run
- Displays deployment URLs and log commands

### What Gets Deployed

Each deployment:
- Builds a Docker container from `Dockerfile`
- Deploys to Google Cloud Run in `us-west1` region
- Configures environment variables:
  - **Test**: `FLASK_ENV=development`, `TEST_MODE=true`, `DISPLAY_TIMEZONE`
  - **Production**: `FLASK_ENV=production`, `DISPLAY_TIMEZONE`
- Mounts secrets from Google Secret Manager (OAuth credentials, Flask secret key)
- Enables unauthenticated access (authentication handled by application)

### Manual Deployment (if needed)

If you need to deploy manually:

```bash
# Test environment
gcloud run deploy cbc-test \
    --source . \
    --platform managed \
    --region us-west1 \
    --allow-unauthenticated \
    --set-env-vars FLASK_ENV=development,TEST_MODE=true,DISPLAY_TIMEZONE=America/Vancouver

# Production environment
gcloud run deploy cbc-registration \
    --source . \
    --platform managed \
    --region us-west1 \
    --allow-unauthenticated \
    --set-env-vars FLASK_ENV=production,DISPLAY_TIMEZONE=America/Vancouver
```

## Custom Domain Configuration

### 1. Map Domains to Services

```bash
# Test environment
gcloud run domain-mappings create \
    --service cbc-test \
    --domain cbc-test.yourclub.org \
    --region us-west1

# Production environment
gcloud run domain-mappings create \
    --service cbc-registration \
    --domain cbc-registration.yourclub.org \
    --region us-west1
```

### 2. Configure DNS Records

Add CNAME records to your DNS provider:

```
Name: cbc-test
Type: CNAME
Value: ghs.googlehosted.com

Name: cbc-registration
Type: CNAME
Value: ghs.googlehosted.com
```

SSL certificates are automatically provisioned once DNS propagates (up to 24 hours).

### 3. Update OAuth JavaScript Origins

After custom domains are configured, update your OAuth client in Google Cloud Console:
- Go to [APIs & Services > Credentials](https://console.cloud.google.com/apis/credentials)
- Edit your OAuth client
- Update Authorized JavaScript origins with your custom domain URLs

## Email Scheduler Setup

Automated email notifications require Google Cloud Scheduler configuration. This is **optional** but recommended for production use.

### Prerequisites

- Application deployed to Cloud Run
- Custom domains configured (or Cloud Run URLs available)
- `DISPLAY_TIMEZONE` configured in `config/organization.py`

### Setup Process

See the **Automated Email Scheduler Setup** section below for detailed instructions.

**Quick summary:**
1. Create service account: `cloud-scheduler-invoker`
2. Grant Cloud Run Invoker permissions
3. Run `./utils/setup_email_scheduler.sh test` (or `production`)
4. Verify jobs are created and test one manually

## Post-Deployment Verification

### 1. Check Service Status

```bash
# Test environment
gcloud run services describe cbc-test --region=us-west1 --format='value(status.url)'

# Production environment
gcloud run services describe cbc-registration --region=us-west1 --format='value(status.url)'
```

### 2. Test Application Features

Visit your deployed URLs and verify:
- ✅ Registration form loads with interactive map
- ✅ Form submission works (check Firestore for data)
- ✅ Admin login works (`/auth/login` then `/admin`)
- ✅ Area leader interface accessible (if you have leaders configured)

### 3. Monitor Logs

```bash
# View recent logs for test environment
gcloud run services logs read cbc-test --region=us-west1 --limit=50

# Tail logs in real-time
gcloud run services logs tail cbc-test --region=us-west1

# Production logs
gcloud run services logs read cbc-registration --region=us-west1 --limit=50
```

### 4. Verify Database Access

Check Firestore in the web console:
```bash
gcloud firestore databases list
```

Or visit: https://console.cloud.google.com/firestore

You should see both `cbc-test` and `cbc-register` databases.

## Automated Email Scheduler Setup

### Overview

The application includes automated email notifications for area leaders and admins. Emails are triggered via Google Cloud Scheduler jobs that invoke secure OIDC-protected routes.

**Email Types:**
- **Team Updates**: Twice daily (6am, 6pm) when team composition changes
- **Weekly Summaries**: Fridays at 11pm to all area leaders
- **Admin Digest**: Daily at 6pm when there are unassigned participants

### Prerequisites

Before setting up the email scheduler:

1. **Service Account Created**: The `cloud-scheduler-invoker` service account must exist with Cloud Run Invoker permissions (see Phase 1 below)
2. **Application Deployed**: The application must be deployed to Cloud Run with OIDC-enabled scheduler routes
3. **Timezone Configured**: Set `DISPLAY_TIMEZONE` in `config/organization.py` (e.g., `America/Vancouver`)

### Phase 1: Create Service Account (One-Time Setup)

This service account authenticates Cloud Scheduler requests to the application.

```bash
# Authenticate to GCP
gcloud auth login
gcloud config set project YOUR-PROJECT-ID

# Create dedicated service account for Cloud Scheduler
gcloud iam service-accounts create cloud-scheduler-invoker \
    --display-name="Cloud Scheduler Email Invoker" \
    --description="Service account for Cloud Scheduler to invoke email routes" \
    --project=YOUR-PROJECT-ID

# Grant Cloud Run Invoker role to TEST service
gcloud run services add-iam-policy-binding cbc-test \
    --region=us-west1 \
    --member="serviceAccount:cloud-scheduler-invoker@YOUR-PROJECT-ID.iam.gserviceaccount.com" \
    --role="roles/run.invoker" \
    --project=YOUR-PROJECT-ID

# Grant Cloud Run Invoker role to PRODUCTION service
gcloud run services add-iam-policy-binding cbc-registration \
    --region=us-west1 \
    --member="serviceAccount:cloud-scheduler-invoker@YOUR-PROJECT-ID.iam.gserviceaccount.com" \
    --role="roles/run.invoker" \
    --project=YOUR-PROJECT-ID
```

### Phase 2: Create Scheduler Jobs

Use the automated setup script to create scheduler jobs for test and/or production environments.

```bash
# Create jobs for test environment only (recommended first step)
./utils/setup_email_scheduler.sh test

# Create jobs for production environment only
./utils/setup_email_scheduler.sh production

# Create jobs for both environments
./utils/setup_email_scheduler.sh both
```

The script automatically:
- Reads timezone from `config/organization.py`
- Configures OIDC authentication with the service account
- Creates 4 scheduler jobs per environment:
  - `cbc-{env}-team-updates-morning` (6am daily)
  - `cbc-{env}-team-updates-afternoon` (6pm daily)
  - `cbc-{env}-weekly-summaries` (Fridays 11pm)
  - `cbc-{env}-admin-digest` (6pm daily)

### Phase 3: Verify Scheduler Jobs

```bash
# List all scheduler jobs
gcloud scheduler jobs list --location=us-west1 --project=YOUR-PROJECT-ID

# Manually trigger a job to test
gcloud scheduler jobs run cbc-test-team-updates-morning \
    --location=us-west1 \
    --project=YOUR-PROJECT-ID

# Check application logs for successful execution
gcloud run services logs read cbc-test --region=us-west1 --limit=50 | grep "Authenticated Cloud Scheduler"
```

Expected log output:
```
INFO:routes.scheduler:Authenticated Cloud Scheduler request from cloud-scheduler-invoker@YOUR-PROJECT-ID.iam.gserviceaccount.com
INFO:routes.scheduler:Team updates completed: X emails sent to Y areas
```

### Managing Scheduler Jobs

**Pause jobs during off-season:**
```bash
# Pause all test jobs
for job in cbc-test-team-updates-morning cbc-test-team-updates-afternoon cbc-test-weekly-summaries cbc-test-admin-digest; do
    gcloud scheduler jobs pause $job --location=us-west1 --project=YOUR-PROJECT-ID
done

# Resume when needed
for job in cbc-test-team-updates-morning cbc-test-team-updates-afternoon cbc-test-weekly-summaries cbc-test-admin-digest; do
    gcloud scheduler jobs resume $job --location=us-west1 --project=YOUR-PROJECT-ID
done
```

**Delete and recreate jobs (e.g., after schedule changes):**
```bash
# Delete test environment jobs
./utils/setup_email_scheduler.sh delete-test

# Recreate with updated settings
./utils/setup_email_scheduler.sh test
```

**List available commands:**
```bash
./utils/setup_email_scheduler.sh
```

### Troubleshooting Scheduler Issues

**Jobs not triggering:**
```bash
# Check job state (should be ENABLED)
gcloud scheduler jobs describe cbc-test-team-updates-morning \
    --location=us-west1 \
    --project=YOUR-PROJECT-ID

# View scheduler execution logs
gcloud logging read "resource.type=cloud_scheduler_job" \
    --limit=20 \
    --project=YOUR-PROJECT-ID
```

**Authentication failures (403 errors):**
```bash
# Verify OIDC configuration
gcloud scheduler jobs describe cbc-test-team-updates-morning \
    --location=us-west1 \
    --format="value(httpTarget.oidcToken)"

# Check Cloud Run IAM permissions
gcloud run services get-iam-policy cbc-test --region=us-west1 | grep cloud-scheduler-invoker
```

**Timezone issues:**
- Verify `DISPLAY_TIMEZONE` in `config/organization.py`
- Delete and recreate jobs to apply timezone changes
- Check job timezone: `gcloud scheduler jobs describe JOB_NAME --location=us-west1 --format="value(timeZone)"`

### Email Configuration

All email content and scheduling is controlled by:
- `config/organization.py` - Organization details and timezone
- `config/email_settings.py` - SMTP provider configuration
- `templates/emails/` - Email HTML templates

Test mode (TEST_MODE=true) redirects all emails to the address specified in `config/organization.py` (`TEST_RECIPIENT`).

## Updates and Maintenance

### Deploy Updated Code

Use the deployment script for consistency:

```bash
# Deploy to test
./deploy.sh test

# Deploy to production
./deploy.sh production

# Deploy to both
./deploy.sh both
```

### Scale Services

```bash
# Increase capacity during registration periods
gcloud run services update cbc-test --region=us-west1 --max-instances=20 --memory=1Gi

# Scale back to save costs
gcloud run services update cbc-test --region=us-west1 --max-instances=5 --memory=512Mi
```

### Update Environment Variables

```bash
gcloud run services update cbc-test --region=us-west1 --set-env-vars NEW_VAR=value
```

### Database Maintenance

**Note**: The application uses year-based collections. Historical data is read-only through the UI.

```bash
# View database structure
# Visit https://console.cloud.google.com/firestore

# Backup databases (if needed)
gcloud firestore export gs://YOUR-BUCKET/backup-$(date +%Y%m%d)
```

## Troubleshooting

### Common Issues

**Build failures:**
- Check that all files are present in repository
- Verify `requirements.txt` is valid
- Check `Dockerfile` for errors

**Authentication errors:**
- Run `gcloud auth list` and re-authenticate if needed
- Verify OAuth setup (see [OAUTH-SETUP.md](OAUTH-SETUP.md))
- Check Secret Manager permissions

**Domain mapping issues:**
- Verify DNS records are correct
- Allow time for DNS propagation (up to 24 hours)
- Check SSL certificate status in Cloud Run console

**Firestore connection errors:**
- Verify `GOOGLE_CLOUD_PROJECT` environment variable
- Check service account has Firestore permissions
- Ensure databases exist: `gcloud firestore databases list`

**Database not found errors:**
- Run `python utils/setup_databases.py` to create databases
- Verify correct database is selected based on environment (`TEST_MODE`)

### Debug Commands

```bash
# Check service configuration
gcloud run services describe cbc-test --region=us-west1

# View detailed logs
gcloud run services logs read cbc-test --region=us-west1 --limit=100

# Check enabled APIs
gcloud services list --enabled

# Check secret values (without revealing secrets)
gcloud secrets versions list google-oauth-client-id
gcloud secrets versions list google-oauth-client-secret
gcloud secrets versions list flask-secret-key
```

### Emergency Rollback

```bash
# List revisions
gcloud run revisions list --service=cbc-test --region=us-west1

# Rollback to previous revision
gcloud run services update-traffic cbc-test \
    --to-revisions=REVISION-NAME=100 \
    --region=us-west1
```

## Security Considerations

- ✅ Credentials stored in Google Secret Manager (never in code)
- ✅ OIDC authentication for Cloud Scheduler routes
- ✅ CSRF protection on all authenticated forms
- ✅ Rate limiting on registration endpoints
- ✅ Input sanitization on all user inputs
- ✅ Admin whitelist in version control
- ✅ OAuth consent screen published for production
- ⚠️ Regularly review IAM permissions
- ⚠️ Monitor billing usage
- ⚠️ Enable audit logging for production
- ⚠️ Keep admin account credentials secure

## Cost Management

Cloud Run charges based on:
- **CPU**: Only during request processing
- **Memory**: Only during request processing
- **Requests**: Per million requests

Scale-to-zero functionality means minimal costs during low-traffic periods.

**Typical costs:**
- Test environment: ~$5-10/month (low traffic)
- Production environment: Varies with usage

Monitor usage: https://console.cloud.google.com/billing

## Adapting for Another Bird Count Club

To deploy this system for a different club:

### 1. Configuration Files
Edit the following files with your organization's information:
- `config/organization.py` - All organization-specific settings
- `config/admins.py` - Admin email addresses
- `config/areas.py` - Count area definitions (codes and names)
- `static/data/area_boundaries.json` - Geographic boundaries for your areas

### 2. Custom Domains
Update domain references in:
- `config/organization.py` - `get_registration_url()` and `get_admin_url()`
- OAuth consent screen configuration
- DNS records for your domain

### 3. Email Provider
Configure SMTP settings in `config/email_settings.py` for your email provider (currently SMTP2GO).

### 4. Area Boundaries
Create or update `static/data/area_boundaries.json` with GeoJSON polygon coordinates for your count areas.

### 5. Branding
Update templates in `templates/` directory:
- `base.html` - Site title and footer
- `index.html` - Registration form header
- Email templates in `templates/emails/`

### 6. Deployment
Follow this guide using your:
- Google Cloud project ID
- Custom domain names
- Organization email addresses

**No code changes should be required** - all customization is configuration-based.

## Support Resources

- **Application Documentation**: See `CLAUDE.md` and `SPECIFICATION.md`
- **OAuth Setup**: See `OAUTH-SETUP.md`
- **Email System**: See `EMAIL_SPEC.md`
- **Cloud Run Documentation**: https://cloud.google.com/run/docs
- **Firestore Documentation**: https://cloud.google.com/firestore/docs
- **Cloud Scheduler Documentation**: https://cloud.google.com/scheduler/docs
- **Google Cloud Console**: https://console.cloud.google.com
