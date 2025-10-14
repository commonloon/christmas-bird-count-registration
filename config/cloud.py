# Updated by Claude AI on 2025-10-14
# Google Cloud Platform configuration
#
# IMPORTANT: Update these values when deploying for a different organization or GCP project

# GCP Project Configuration
GCP_PROJECT_ID = 'vancouver-cbc-registration'
GCP_LOCATION = 'us-west1'  # Oregon region

# Firestore Database identifiers
TEST_DATABASE = 'cbc-test'
PRODUCTION_DATABASE = 'cbc-register'

# Cloud Run Service Names (subdomain names)
TEST_SERVICE = 'cbc-test'
PRODUCTION_SERVICE = 'cbc-registration'

# Base domain for URL construction
BASE_DOMAIN = 'naturevancouver.ca'

# Deployment URLs (constructed from service + domain)
TEST_BASE_URL = f'https://{TEST_SERVICE}.{BASE_DOMAIN}'
PRODUCTION_BASE_URL = f'https://{PRODUCTION_SERVICE}.{BASE_DOMAIN}'

# Secret Manager Secret Names (standard across all installations)
SECRET_OAUTH_CLIENT_ID = 'google-oauth-client-id'
SECRET_OAUTH_CLIENT_SECRET = 'google-oauth-client-secret'
SECRET_FLASK_KEY = 'flask-secret-key'
SECRET_SMTP2GO_USERNAME = 'smtp2go-username'
SECRET_SMTP2GO_PASSWORD = 'smtp2go-password'
