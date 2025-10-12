# Created by Claude AI on 2025-10-12
# Google Cloud Platform configuration
#
# IMPORTANT: Update these values when deploying for a different organization or GCP project

# GCP Project Configuration
GCP_PROJECT_ID = 'vancouver-cbc-registration'
GCP_LOCATION = 'us-west1'  # Oregon region

# Firestore Database identifiers
DATABASE_TEST = 'cbc-test'
DATABASE_PRODUCTION = 'cbc-register'

# Deployment URLs (base URLs without trailing slashes)
BASE_URL_TEST = 'https://cbc-test.naturevancouver.ca'
BASE_URL_PRODUCTION = 'https://cbc-registration.naturevancouver.ca'
