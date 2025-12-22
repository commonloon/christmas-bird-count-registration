# CBC Registration System - Deployment Guide
<!-- Updated by Claude AI on 2025-11-30 -->

## About This Guide

This guide helps you deploy and maintain the Christmas Bird Count registration system. It's written for volunteers with basic computer skills who may not have cloud engineering experience.

**If you're starting a new registration season**, jump to [Annual Season Start](#annual-season-start) below.

**If this is your first time deploying the system**:
1. Complete the [Deployment Planning Worksheet](DEPLOYMENT_WORKSHEET.md) to organize all configuration values
2. Follow the [Initial Setup](#initial-setup-first-time-only) steps below

**For technical details and troubleshooting**, see [DEPLOYMENT_TECHNICAL_REFERENCE.md](DEPLOYMENT_TECHNICAL_REFERENCE.md).

---

## Annual Season Start

**When to do this**: At the beginning of each registration season (typically October/November)

**What you need**:
- Access to a computer with command line
- Google Cloud login credentials
- 15 minutes

**Steps:**

### 1. Verify Database Indexes

Database indexes ensure the registration system runs quickly. Each year, new collections are created automatically, and indexes must be set up for these collections.

```bash
# Make sure you're logged in to Google Cloud
gcloud auth login
gcloud auth application-default login

# Run the index verification script for the test environment
python utils/verify_indexes.py <TEST-DATABASE>  # Example: my-club-test

# If test looks good, run for production
python utils/verify_indexes.py <PROD-DATABASE>  # Example: my-club-register
```

**What you'll see:**
- The script checks if this year's collections exist
- If collections don't exist yet, you'll be prompted to register yourself first
- The script will create any missing indexes automatically
- Index creation takes a few minutes (happens in the background)

**Expected output:**
```
[OK] participants_2025 exists
[OK] removal_log_2025 exists
[OK] Identity-based queries
[NEW] New indexes created: 5
SUCCESS: All indexes are ready!
```

### 2. Test the Registration Form

Visit your test site and register yourself:
- **Test site**: `https://<TEST-DOMAIN>`  (Example: `https://cbc-test.myclub.org`)
- Fill out the registration form
- Verify you receive a confirmation
- Check that you appear in the admin interface


### 3. Update Count Date

The count date displayed on the registration form must be updated each year:

1. Edit `config/organization.py`
2. Update the `YEARLY_COUNT_DATES` dictionary with your count's date for the current year
   - Format: `YYYY-MM-DD` (e.g., `'2025': '2025-12-20'`)
   - The system will automatically format it as "Saturday, December 20, 2025" on the registration page
3. Deploy the updated code (see [Deploying Updates](#deploying-updates))

**Example:**
```python
YEARLY_COUNT_DATES = {
    2024: '2024-12-14',
    2025: '2025-12-20',  # Add the current year's count date here
}
```

### 4. Update Admin Accounts (if needed)

If your coordinators have changed, update the admin list:

1. Edit `config/admins.py`
2. Update the `PRODUCTION_ADMIN_EMAILS` list
3. Deploy the updated code (see [Deploying Updates](#deploying-updates))

### 5. Deploy to Production

Once testing is complete:

```bash
# Deploy to production
./deploy.sh production
```

Wait 2-3 minutes for deployment to complete, then test the production registration form.

### 3. Configure Area Signup Types

By default, all count areas allow participant self-registration. However, you may need to restrict some areas to admin-only assignment (for example, areas accessible only by boat or requiring special permits like airports).

**To configure areas:**

1. Log in to the admin interface using an admin account
2. Go to the **Open/Close Areas** page (found in Quick Actions on the Dashboard, or in the Admin Navigation)
3. On this page you'll see:
   - An interactive map showing area status (green = open, yellow = admin-only)
   - A table with all areas and radio buttons to set their registration status
4. For each area:
   - Select **Open** if participants can register directly for this area
   - Select **Admin Only** if only admins should assign participants to this area
5. Changes take effect immediately - no deployment required

**Common scenarios:**
- **Boat-based areas** (like marine boundary surveys): Set to "Admin Only"
- **Airport areas** (requiring special access): Set to "Admin Only"
- **Areas with limited volunteer capacity**: Set to "Admin Only" to manage assignments manually
- **Area Leader doesn't want more volunteers**: Set to "Admin Only" to manage assignments manually
- **Regular areas**: Leave as "Open"

### 6. Share Registration URL

Send participants to:
- **Production**: `https://<PROD-DOMAIN>`  (Example: `https://cbc-registration.myclub.org`)

---

## Deploying Updates

**When to do this**: When you need to deploy code changes or configuration updates

```bash
# Deploy to test environment (always test first!)
./deploy.sh test

# After testing, deploy to production
./deploy.sh production

# Or deploy to both at once
./deploy.sh both
```

**Deployment takes 2-3 minutes**. You'll see build progress and a success message with the service URL.

---

## Common Tasks

### Viewing Application Logs

If you need to troubleshoot issues:

```bash
# View recent logs (test)
gcloud run services logs read <TEST-SERVICE> --region=us-west1 --limit=50

# View recent logs (production)
gcloud run services logs read <PROD-SERVICE> --region=us-west1 --limit=50

# Watch logs in real-time (test)
gcloud run services logs tail <TEST-SERVICE> --region=us-west1
```

### Checking Service Status

```bash
# Check test service
gcloud run services describe <TEST-SERVICE> --region=us-west1

# Check production service
gcloud run services describe <PROD-SERVICE> --region=us-west1
```

### Exporting Participant Data

Use the admin interface at `/admin` to export CSV files of:
- All participants
- Area leaders
- Participants by area

---

## Initial Setup (First Time Only)

**When to do this**: Only when deploying the system for the first time

**What you need**:
- Google Cloud account with billing enabled
- Domain name for your organization
- 2-3 hours for complete setup

> [!CAUTION]
> The macOS and Linux instructions were generated by Claude.ai and are completely untested. 
> Development and testing were done on Windows.
> 
### 1. Install Google Cloud CLI

#### Windows
1. Download from https://cloud.google.com/sdk/docs/install
2. Run the installer
3. Restart PowerShell

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

### 2. Authenticate with Google Cloud

```bash
# Log in to Google Cloud
gcloud auth login
```

### 3. Create Your Google Cloud Project

You need to create a new project for your bird count registration system.

#### Using Google Cloud Console (Recommended for beginners)

1. Go to https://console.cloud.google.com
2. Click the project dropdown at the top (or "Select a project")
3. Click "New Project"
4. Enter project details:
   - **Project name**: A descriptive name (e.g., "My Club CBC Registration")
   - **Project ID**: A unique identifier (e.g., `my-club-cbc-registration`)
     - This ID must be globally unique across all Google Cloud
     - Use lowercase letters, numbers, and hyphens only
     - Cannot be changed after creation
   - **Organization/Billing**: Select your billing account
5. Click "Create"
6. Wait for the project to be created (takes a few seconds)



### 4. Set Your Active Project

```bash
# Set your project ID (use the Project ID from step 3)
gcloud config set project <YOUR-PROJECT-ID>  # Example: my-club-cbc-registration

# Verify the configuration
gcloud config list
```

You should see output showing your project ID and account.

**Update Application Default Credentials:**

If you see a warning about quota project mismatch, update your Application Default Credentials:

```bash
# Update ADC quota project to match your active project
gcloud auth application-default set-quota-project <YOUR-PROJECT-ID>
```

This ensures that local development tools (like the database setup scripts) use the correct project for billing and quotas.

### 5. Enable Required Services
Enable services for the current google cloud project:
```bash
gcloud services enable run.googleapis.com
gcloud services enable firestore.googleapis.com
gcloud services enable cloudbuild.googleapis.com
gcloud services enable secretmanager.googleapis.com
gcloud services enable cloudscheduler.googleapis.com
```

### 6. Configure Your Organization

Edit `config/organization.py` with your club's details:
- Organization name
- Contact emails
- Domain names
- Timezone

See [DEPLOYMENT_TECHNICAL_REFERENCE.md](DEPLOYMENT_TECHNICAL_REFERENCE.md) for detailed configuration instructions.

### 7. Create Firestore Databases

Edit `config/cloud.py` and make the appropriate changes.  
See [DEPLOYMENT_WORKSHEET.md](DEPLOYMENT_WORKSHEET.md) and 
[DEPLOYMENT_TECHNICAL_REFERENCE.md](DEPLOYMENT_TECHNICAL_REFERENCE.md) for more details.

```bash
# Install Python dependencies
pip install -r utils/requirements.txt

# Create databases (names configured in config/database.py)
python utils/setup_databases.py
```

This creates two databases with names you configured (e.g., `my-club-test` and `my-club-register`).

### 8. Set Up SMTP2GO Email Secrets

**IMPORTANT:** This step must be completed before OAuth setup and deployment.

The application uses SMTP2GO for sending email notifications to area leaders and participants.

```bash
# Run the SMTP secrets setup script
./utils/setup_smtp_secrets.sh
```

The script will prompt you for:
- SMTP2GO username  (Note: this is the smtp user set up under "SMTP Users" in the smtp2go account, not the username used to log in to smtp2go.  That's a bit confusing, sorry.)
- SMTP2GO password (entered securely, not displayed)

**To get SMTP2GO credentials:**
1. Sign up for a free account at https://www.smtp2go.com
2. Verify your sending domain
3. Set up your SMTP username and password from the SMTP2GO dashboard (or find the values there under "SMTP Users" if you've already created the user)

**Notes:**
- If you don't have SMTP2GO credentials yet, you can use placeholder values for initial testing
- Email functionality won't work until real credentials are configured
- The system currently supports SMTP2GO only (other providers can be added in future)

### 9. Set Up OAuth Authentication

OAuth allows admins and area leaders to log in with Google accounts.

**IMPORTANT:** SMTP secrets (step 8) must be created before proceeding with OAuth setup and deployment.

**Detailed instructions**: See [OAUTH-SETUP.md](OAUTH-SETUP.md)

**Quick steps:**
1. Create OAuth client in Google Cloud Console
2. Download `client_secret.json`
3. Run `./utils/setup_oauth_secrets.sh`
4. Delete `client_secret.json`
5. Deploy application (Step 10)
6. Publish OAuth consent screen

### 10. Configure Admin Accounts

Edit `config/admins.py` and add admin email addresses:

```python
PRODUCTION_ADMIN_EMAILS = [
    'admin@myclub.org',         # Replace with your admin emails
    'coordinator@myclub.org'
]
```

### 11. Initial Deployment

```bash
# Deploy to test first
./deploy.sh test

# Test thoroughly, then deploy to production
./deploy.sh production
```

### 12. Configure Custom Domains

**Map domains using Google Cloud Console:**

1. Go to [Cloud Run Console](https://console.cloud.google.com/run)
2. Click on your **test service** (configured in `config/cloud.py`)
3. Click the **"MANAGE CUSTOM DOMAINS"** tab at the top
4. Click **"ADD MAPPING"**
5. Select your service from the dropdown
6. Enter your test domain (from `config/cloud.py`)
7. Click **"CONTINUE"**
8. Follow DNS verification instructions (add CNAME record shown)
9. Click **"DONE"**

Repeat for your **production service** with the production domain.

**Example DNS CNAME records** (add to your domain provider):
```
Name: cbc-test             # Or your test subdomain
Type: CNAME
Value: ghs.googlehosted.com

Name: cbc-registration     # Or your production subdomain
Type: CNAME
Value: ghs.googlehosted.com
```

**Notes:**
- Domain names are configured in `config/cloud.py`
- SSL certificates are automatically provisioned (takes up to 24 hours)
- You must have control of the DNS for your domain

### 13. Configure Email Scheduler (Optional)

For automated email notifications to area leaders:

```bash
# Create service account (one time)
gcloud iam service-accounts create cloud-scheduler-invoker \
    --display-name="Cloud Scheduler Email Invoker"

# Grant permissions to test service
# Replace <TEST-SERVICE> with the value from config/cloud.py
gcloud run services add-iam-policy-binding <TEST-SERVICE> \
    --region=us-west1 \
    --member="serviceAccount:cloud-scheduler-invoker@<YOUR-PROJECT-ID>.iam.gserviceaccount.com" \
    --role="roles/run.invoker"

# Grant permissions to production service
# Replace <PROD-SERVICE> with the value of PRODUCTION_SERVICE from config/cloud.py
gcloud run services add-iam-policy-binding <PROD-SERVICE> \
    --region=us-west1 \
    --member="serviceAccount:cloud-scheduler-invoker@<YOUR-PROJECT-ID>.iam.gserviceaccount.com" \
    --role="roles/run.invoker"

# Create scheduler jobs
./utils/setup_email_scheduler.sh test
./utils/setup_email_scheduler.sh production
```

### 14. Validate Installation

After completing initial setup, validate your configuration and infrastructure:

```bash
# Run all installation validation tests (37 tests)
pytest tests/installation/ -v

# Or run phases separately:
# Phase 1: Configuration only (21 tests, no GCP required)
pytest tests/installation/test_configuration.py -v

# Phase 2: Infrastructure (16 tests, requires GCP auth)
pytest tests/installation/test_infrastructure.py -v
```

**Expected result**: All 37 tests should pass.

**Phase 1 validates:**
- Configuration files in `config/`
- Area code consistency
- Email and URL formats
- Map configuration

**Phase 2 validates:**
- Firestore database access
- Secret Manager secrets exist
- Cloud Run services deployed
- Database indexes ready

**If tests fail**: Error messages will guide you to fix issues. Common problems include:
- Missing or misconfigured files in `config/`
- Area code mismatches between files
- Missing OAuth or SMTP secrets
- Services not deployed

**For detailed documentation**, see the [Installation Validation Tests](TESTING.md#installation-validation-tests) section in TESTING.md.

---

## Getting Help

### Error Messages

**"Database does not exist"**
- Run `python utils/setup_databases.py` to create databases

**"OAuth client not found"**
- Follow steps in [OAUTH-SETUP.md](OAUTH-SETUP.md)
- Verify OAuth consent screen is published

**"Permission denied"**
- Run `gcloud auth login`
- Verify you have correct project permissions

**"Index creation required" in logs**
- Run `python utils/verify_indexes.py <TEST-DATABASE>` (or `<PROD-DATABASE>`)

### Where to Find More Information

- **Deployment planning**: [DEPLOYMENT_WORKSHEET.md](DEPLOYMENT_WORKSHEET.md)
- **Technical details**: [DEPLOYMENT_TECHNICAL_REFERENCE.md](DEPLOYMENT_TECHNICAL_REFERENCE.md)
- **OAuth setup**: [OAUTH-SETUP.md](OAUTH-SETUP.md)
- **Email system**: [EMAIL_SCHEDULER_TESTING.md](EMAIL_SCHEDULER_TESTING.md)
- **Application features**: [SPECIFICATION.md](SPECIFICATION.md)
- **Development guide**: [CLAUDE.md](CLAUDE.md)

### Support Resources

- **Cloud Run Documentation**: https://cloud.google.com/run/docs
- **Firestore Documentation**: https://cloud.google.com/firestore/docs
- **Google Cloud Console**: https://console.cloud.google.com

---

## Adapting for Another Bird Count Club

This system is designed to be portable. To use it for your club:

### Configuration Files to Update

1. **`config/cloud.py`** - GCP project, databases, services, region, and domain
2. **`config/organization.py`** - Organization name, contact emails, and timezone
3. **`config/admins.py`** - Admin email addresses
4. **`config/areas.py`** - Count area definitions
5. **`static/data/area_boundaries.json`** - Geographic boundaries

### Domain and Email Setup

1. Update `config/cloud.py` with:
   - `GCP_PROJECT_ID` - Your Google Cloud project ID
   - `BASE_DOMAIN` - Your organization's domain (e.g., `myclub.org`)
   - `TEST_SERVICE` and `PRODUCTION_SERVICE` - Cloud Run service names
   - `TEST_DATABASE` and `PRODUCTION_DATABASE` - Firestore database names
   - `GCP_LOCATION` - Region (default: `us-west1`)
2. Update domain references in `config/organization.py`
3. Configure OAuth consent screen with your domain
4. Update DNS records for your domain
5. Configure SMTP settings in `config/email_settings.py`

### Deployment

Follow the [Initial Setup](#initial-setup-first-time-only) steps using your:
- Google Cloud project ID
- Custom database names
- Custom Cloud Run service names
- Custom domain names
- Organization email addresses

**No code changes should be required** - everything is configuration-based.

---

## Maintenance Tips

### During Registration Season

1. **Monitor daily**: Check logs for errors
2. **Export regularly**: Download participant lists weekly
3. **Test changes**: Always deploy to test environment first
4. **Back up data**: Firestore backs up automatically (see [BACKUPS.md](BACKUPS.md))

### Off-Season

1. **Keep services running**: Data persists year-to-year
2. **Cloud Run scales to zero**: Minimal costs during low-traffic periods
3. **Review billing**: Monitor at https://console.cloud.google.com/billing

### Before Next Season

1. **Run annual season start procedure** (see top of this document)
2. **Update admin accounts** if coordinators changed
3. **Test thoroughly** before opening registration
4. **Review and update count areas** if boundaries changed
