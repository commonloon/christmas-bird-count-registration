# Deployment Guide - Vancouver CBC Registration App

## Prerequisites

- Google Cloud CLI installed and authenticated
- Access to `birdcount@naturevancouver.ca` Google account
- DNS control for `naturevancouver.ca` domain
- Local copy of the project repository

## Pre-Deployment Setup

### 1. Install Google Cloud CLI

#### Windows 11
1. Download the installer from https://cloud.google.com/sdk/docs/install
2. Run the installer and follow the prompts
3. Restart PowerShell to ensure `gcloud` is in your PATH
4. Verify installation: `gcloud version`

#### macOS
```bash
# Using Homebrew (recommended)
brew install google-cloud-sdk

# Or download installer from Google Cloud website
# https://cloud.google.com/sdk/docs/install
```

#### Linux (Ubuntu/Debian)
```bash
# Add Google Cloud SDK repository
echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main" | sudo tee -a /etc/apt/sources.list.d/google-cloud-sdk.list

# Import Google Cloud public key
curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | sudo apt-key --keyring /usr/share/keyrings/cloud.google.gpg add -

# Update package list and install
sudo apt-get update && sudo apt-get install google-cloud-cli
```

### 2. Authenticate and Configure

All platforms:
```bash
# Authenticate with Google Cloud
gcloud auth login

# Set default project
gcloud config set project vancouver-cbc-registration

# Verify configuration
gcloud config list
```

## Environment Setup

### 1. Enable Required APIs

```bash
gcloud services enable run.googleapis.com
gcloud services enable firestore.googleapis.com
gcloud services enable cloudbuild.googleapis.com
gcloud services enable iam.googleapis.com
```

### 2. Create Firestore Database (if not exists)

```bash
# Check if database exists
gcloud firestore databases list

# Create database if needed
gcloud firestore databases create --location=us-west1 --type=firestore-native
```

## Deployment Process

### 1. Prepare Application

Navigate to your project directory:

#### Windows 11 (PowerShell)
```powershell
cd C:\path\to\christmas-bird-count-registration
```

#### macOS/Linux
```bash
cd /path/to/christmas-bird-count-registration
```

### 2. Create Missing Templates (if needed)

Check if error templates exist:

#### Windows 11
```powershell
if (!(Test-Path "templates\errors")) { mkdir templates\errors }
```

#### macOS/Linux
```bash
mkdir -p templates/errors
```

Create `templates/errors/404.html`:
```html
{% extends "base.html" %}
{% block content %}
<div class="text-center">
    <h1>Page Not Found</h1>
    <p>The page you're looking for doesn't exist.</p>
    <a href="{{ url_for('main.index') }}" class="btn btn-primary">Return Home</a>
</div>
{% endblock %}
```

Create `templates/errors/500.html`:
```html
{% extends "base.html" %}
{% block content %}
<div class="text-center">
    <h1>Server Error</h1>
    <p>Something went wrong. Please try again later.</p>
    <a href="{{ url_for('main.index') }}" class="btn btn-primary">Return Home</a>
</div>
{% endblock %}
```

### 3. Deploy to Cloud Run

#### Test Server Deployment
```bash
gcloud run deploy cbc-test --source . --platform managed --region us-west1 --allow-unauthenticated --set-env-vars GOOGLE_CLOUD_PROJECT=vancouver-cbc-registration
```

#### Production Server Deployment
```bash
gcloud run deploy cbc-registration --source . --platform managed --region us-west1 --allow-unauthenticated --set-env-vars GOOGLE_CLOUD_PROJECT=vancouver-cbc-registration
```

### 4. Verify Deployment

Get service URLs:
```bash
# Test server
gcloud run services describe cbc-test --region=us-west1 --format='value(status.url)'

# Production server  
gcloud run services describe cbc-registration --region=us-west1 --format='value(status.url)'
```

Test the generated URLs in your browser to verify the application loads correctly.

## Custom Domain Configuration

### 1. Map Domains to Services

#### Test Server
```bash
gcloud run domain-mappings create --service cbc-test --domain cbc-test.naturevancouver.ca --region us-west1
```

#### Production Server
```bash
gcloud run domain-mappings create --service cbc-registration --domain cbc-registration.naturevancouver.ca --region us-west1
```

### 2. Configure DNS

After running domain mapping commands, Google Cloud will display DNS instructions. Add CNAME records to your DNS provider:

```
Name: cbc-test
Type: CNAME
Value: ghs.googlehosted.com

Name: cbc-registration
Type: CNAME  
Value: ghs.googlehosted.com
```

SSL certificates are automatically provisioned once DNS propagates (can take up to 24 hours).

## Post-Deployment Verification

### 1. Test Application Features

Visit your deployed URLs and verify:
- Registration form loads correctly
- Interactive map displays area boundaries
- Form submission works and saves to Firestore
- Admin interface is accessible (basic functionality)

### 2. Check Firestore Data

```bash
# View Firestore in web console
gcloud firestore databases list
```

Or visit: https://console.cloud.google.com/firestore

### 3. Monitor Logs

```bash
# View logs for test server
gcloud run services logs read cbc-test --region=us-west1 --limit=50

# View logs for production server
gcloud run services logs read cbc-registration --region=us-west1 --limit=50
```

## Updates and Maintenance

### Deploy Updated Code

```bash
# Deploy changes to test server
gcloud run deploy cbc-test --source . --region us-west1

# Deploy changes to production server
gcloud run deploy cbc-registration --source . --region us-west1
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

## Troubleshooting

### Common Issues

**Build failures**: Check that all required files are present and requirements.txt is valid.

**Authentication errors**: Run `gcloud auth list` and re-authenticate if needed.

**Domain mapping issues**: Verify DNS records are correct and allow time for propagation.

**Firestore connection errors**: Check that the service account has proper permissions.

### Debug Commands

```bash
# Check service status
gcloud run services describe cbc-test --region=us-west1

# View detailed error information
gcloud run services logs read cbc-test --region=us-west1 --limit=100

# Check API enablement
gcloud services list --enabled
```

### Emergency Rollback

```bash
# List revisions
gcloud run revisions list --service=cbc-test --region=us-west1

# Rollback to previous revision
gcloud run services update-traffic cbc-test --to-revisions=REVISION-NAME=100 --region=us-west1
```

## Security Considerations

- Regularly review IAM permissions
- Monitor billing usage
- Enable audit logging for production
- Keep the `birdcount@naturevancouver.ca` credentials secure
- Consider enabling VPC Service Controls for production

## Cost Management

Cloud Run charges based on usage. During low-traffic periods, costs should be minimal due to scale-to-zero functionality. Monitor usage at: https://console.cloud.google.com/billing

## Support Resources

- Cloud Run Documentation: https://cloud.google.com/run/docs
- Firestore Documentation: https://cloud.google.com/firestore/docs  
- Google Cloud Console: https://console.cloud.google.com
- Project-specific settings: Select `vancouver-cbc-registration` project