#!/bin/bash
date

# Deployment script for Christmas Bird Count Registration App
# Usage: ./deploy.sh [test|production|registration|both] [--coverage]
# Default: both (without coverage)
# --coverage flag: Enable coverage measurement on test server only

# Read configuration from config files
echo "Reading configuration from config/cloud.py and config/organization.py..."
PYTHON_CONFIG=$(python3 -c "
import sys
sys.path.insert(0, '.')
from config.cloud import GCP_PROJECT_ID, GCP_LOCATION, TEST_SERVICE, PRODUCTION_SERVICE, TEST_BASE_URL, PRODUCTION_BASE_URL
from config.organization import DISPLAY_TIMEZONE, FROM_EMAIL
print(f'{GCP_PROJECT_ID}|{GCP_LOCATION}|{TEST_SERVICE}|{PRODUCTION_SERVICE}|{TEST_BASE_URL}|{PRODUCTION_BASE_URL}|{DISPLAY_TIMEZONE}|{FROM_EMAIL}')
" 2>/dev/null)

if [ -z "$PYTHON_CONFIG" ]; then
    echo "ERROR: Failed to read configuration from config files"
    echo "Please ensure config/cloud.py and config/organization.py are properly configured"
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
