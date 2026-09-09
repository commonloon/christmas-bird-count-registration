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
# PRODUCTION_BASE_URL points at the pre-FullHost-migration Cloud Run host. Nothing
# should ever navigate a browser here - tests/conftest.py's pytest_sessionstart
# guard refuses to run at all if TEST_TARGET=production - this constant is kept
# only for tests/installation/test_configuration.py's config-value sanity checks
# (it asserts this string differs from TEST_BASE_URL/contains BASE_DOMAIN, etc.),
# never dereferenced over the network.
PRODUCTION_BASE_URL = f'https://{PRODUCTION_SERVICE}.{BASE_DOMAIN}'

# Local dev server (FLASK_APP=app.py flask run --host 127.0.0.1 --port 8080), reached
# via the dedicated 'test' circle over the IANA-reserved .test TLD rather than a raw
# IP (see .env.example for the required hosts-file entry) - this is a multi-circle
# platform and the app requires a real Host-header-resolvable circle for every
# request, with no default/fallback circle (see app.py's resolve_circle()).
#
# TEST_BASE_URL used to be derived from TEST_SERVICE/BASE_DOMAIN
# (cbc-test.naturevancouver.ca) on the assumption that host was a dead, decommissioned
# Cloud Run placeholder - it turned out to still be live (confirmed reachable,
# returning HTTP 200), so tests/installation/*.py were silently sending real browser
# traffic to a real, separate, external system every run. Both constants now point at
# the same safe local target so there is only one place real Selenium traffic can go.
LOCAL_BASE_URL = 'http://test.cbc.test:8080'
TEST_BASE_URL = LOCAL_BASE_URL

# Secret Manager Secret Names (standard across all installations)
SECRET_OAUTH_CLIENT_ID = 'google-oauth-client-id'
SECRET_OAUTH_CLIENT_SECRET = 'google-oauth-client-secret'
SECRET_FLASK_KEY = 'flask-secret-key'
SECRET_SMTP2GO_USERNAME = 'smtp2go-username'
SECRET_SMTP2GO_PASSWORD = 'smtp2go-password'
