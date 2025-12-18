#!/bin/bash
date

# Deployment script for Christmas Bird Count Registration App
# Usage: ./deploy.sh [test|production|registration|both] [--coverage]
# Default: both (without coverage)
# --coverage flag: Enable coverage measurement on test server only

# Read configuration from config files
echo "Reading configuration from config/cloud.py and config/organization.py..."

# Capture both stdout and stderr
PYTHON_OUTPUT=$(python -c "
import sys
sys.path.insert(0, '.')
from config.cloud import GCP_PROJECT_ID, GCP_LOCATION, TEST_SERVICE, PRODUCTION_SERVICE, TEST_BASE_URL, PRODUCTION_BASE_URL
from config.organization import DISPLAY_TIMEZONE, FROM_EMAIL
print(f'{GCP_PROJECT_ID}|{GCP_LOCATION}|{TEST_SERVICE}|{PRODUCTION_SERVICE}|{TEST_BASE_URL}|{PRODUCTION_BASE_URL}|{DISPLAY_TIMEZONE}|{FROM_EMAIL}')
" 2>&1)

# Check if the command succeeded by looking for the expected format
PYTHON_CONFIG=$(echo "$PYTHON_OUTPUT" | grep '|' | head -1)

if [ -z "$PYTHON_CONFIG" ]; then
    echo "ERROR: Failed to read configuration from config files"
    echo ""

    # Check if it's a module import error
    if echo "$PYTHON_OUTPUT" | grep -q "ModuleNotFoundError\|ImportError"; then
        echo "This appears to be a missing Python dependency issue."
        echo ""
        echo "Possible solutions:"
        echo "  1. Activate the virtual environment:"
        echo "     source .venv/Scripts/activate  (Windows Git Bash)"
        echo "     source .venv/bin/activate      (Linux/Mac)"
        echo ""
        echo "  2. Install dependencies:"
        echo "     pip install -r requirements.txt"
        echo ""
        echo "Error details:"
        echo "$PYTHON_OUTPUT" | head -5
    else
        echo "Please ensure config/cloud.py and config/organization.py are properly configured"
        echo ""
        echo "Error details:"
        echo "$PYTHON_OUTPUT"
    fi
    exit 1
fi

# Parse configuration
IFS='|' read -r GCP_PROJECT_ID GCP_LOCATION TEST_SERVICE PRODUCTION_SERVICE TEST_BASE_URL PRODUCTION_BASE_URL DISPLAY_TIMEZONE FROM_EMAIL <<< "$PYTHON_CONFIG"

echo "Configuration loaded:"
echo "  GCP Project: $GCP_PROJECT_ID"
echo "  Region: $GCP_LOCATION"
echo "  Test Service: $TEST_SERVICE"
echo "  Production Service: $PRODUCTION_SERVICE"
echo "  Test URL: $TEST_BASE_URL"
echo "  Production URL: $PRODUCTION_BASE_URL"
echo "  Display Timezone: $DISPLAY_TIMEZONE"
echo "  From Email: $FROM_EMAIL"
echo ""

# Safety check: Verify gcloud is configured for the correct project
echo "Checking gcloud project configuration..."
CURRENT_PROJECT=$(gcloud config get-value project 2>/dev/null || echo "")

if [ -z "$CURRENT_PROJECT" ]; then
    echo "ERROR: gcloud is not configured with a project"
    echo "Please run: gcloud config set project <PROJECT_ID>"
    exit 1
fi

if [ "$CURRENT_PROJECT" != "$GCP_PROJECT_ID" ]; then
    echo ""
    echo "⚠️  PROJECT MISMATCH DETECTED!"
    echo ""
    echo "  Config file expects: $GCP_PROJECT_ID"
    echo "  gcloud is set to:    $CURRENT_PROJECT"
    echo ""
    echo "This could deploy code to the WRONG project. To fix:"
    echo "  gcloud config set project $GCP_PROJECT_ID"
    echo ""
    read -p "Continue anyway? (type 'yes' to confirm): " CONFIRM
    if [ "$CONFIRM" != "yes" ]; then
        echo "Deployment cancelled."
        exit 1
    fi
    echo ""
fi

# Parse arguments
DEPLOY_TARGET=${1:-both}
ENABLE_COVERAGE=false

# Check for --coverage flag in any position
for arg in "$@"; do
    if [ "$arg" == "--coverage" ]; then
        ENABLE_COVERAGE=true
        echo "Coverage measurement will be ENABLED on test server"
        echo ""
    fi
done

deploy() {
    local service=$1
    local env_vars=$2
    local enable_coverage=$3
    local service_url=$4

    echo "Deploying to $service environment..."

    # Build environment variables string
    local full_env_vars="$env_vars,GOOGLE_CLOUD_PROJECT=$GCP_PROJECT_ID,EMAIL_PROVIDER=smtp2go,FROM_EMAIL=$FROM_EMAIL"

    # Only add ENABLE_COVERAGE for test server when --coverage flag is used
    if [ "$service" == "$TEST_SERVICE" ] && [ "$enable_coverage" == "true" ]; then
        full_env_vars="$full_env_vars,ENABLE_COVERAGE=true"
        echo "⚠️  Coverage measurement ENABLED for test server"
    fi

    if gcloud run deploy $service \
        --source . \
        --platform managed \
        --region $GCP_LOCATION \
        --allow-unauthenticated \
        --set-env-vars="$full_env_vars" \
        --set-secrets="GOOGLE_CLIENT_ID=google-oauth-client-id:latest,GOOGLE_CLIENT_SECRET=google-oauth-client-secret:latest,SECRET_KEY=flask-secret-key:latest,SMTP2GO_USERNAME=smtp2go-username:latest,SMTP2GO_PASSWORD=smtp2go-password:latest"; then

        echo "$service deployment complete!"
        echo "URL: $service_url"
        echo "Logs: gcloud run services logs read $service --region=$GCP_LOCATION --limit=50"
        echo ""
        return 0
    else
        echo "ERROR: Deployment failed for $service"
        return 1
    fi
}

case $DEPLOY_TARGET in
    test)
        deploy "$TEST_SERVICE" "FLASK_ENV=development,TEST_MODE=true,DISPLAY_TIMEZONE=$DISPLAY_TIMEZONE" "$ENABLE_COVERAGE" "$TEST_BASE_URL"
        exit $?
        ;;
    production|registration)
        deploy "$PRODUCTION_SERVICE" "FLASK_ENV=production,DISPLAY_TIMEZONE=$DISPLAY_TIMEZONE" "false" "$PRODUCTION_BASE_URL"
        exit $?
        ;;
    both)
        deploy "$TEST_SERVICE" "FLASK_ENV=development,TEST_MODE=true,DISPLAY_TIMEZONE=$DISPLAY_TIMEZONE" "$ENABLE_COVERAGE" "$TEST_BASE_URL"
        TEST_RESULT=$?
        deploy "$PRODUCTION_SERVICE" "FLASK_ENV=production,DISPLAY_TIMEZONE=$DISPLAY_TIMEZONE" "false" "$PRODUCTION_BASE_URL"
        PROD_RESULT=$?
        if [ $TEST_RESULT -eq 0 ] && [ $PROD_RESULT -eq 0 ]; then
            echo "Both deployments complete!"
            exit 0
        else
            echo "ERROR: One or more deployments failed"
            exit 1
        fi
        ;;
    *)
        echo "Invalid deployment target: $DEPLOY_TARGET"
        echo "Usage: $0 [test|production|registration|both] [--coverage]"
        echo "  test        - Deploy to $TEST_SERVICE only"
        echo "  production  - Deploy to $PRODUCTION_SERVICE only"
        echo "  registration- Deploy to $PRODUCTION_SERVICE only (synonym for production)"
        echo "  both        - Deploy to both environments (default)"
        echo ""
        echo "Options:"
        echo "  --coverage  - Enable coverage measurement on test server (test/both targets only)"
        exit 1
        ;;
esac
