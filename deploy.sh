#!/bin/bash
date

# Deployment script for Christmas Bird Count Registration App
# Usage: ./deploy.sh [test|production|registration|both]
# Default: both

# Get timezone from config/organization.py
DISPLAY_TIMEZONE=$(python3 -c "import sys; sys.path.insert(0, '.'); from config.organization import DISPLAY_TIMEZONE; print(DISPLAY_TIMEZONE)" 2>/dev/null || echo "America/Vancouver")

echo "Deploying with display timezone: $DISPLAY_TIMEZONE"
echo "If this timezone is incorrect for your location, update DISPLAY_TIMEZONE in config/organization.py"
echo ""

DEPLOY_TARGET=${1:-both}

deploy() {
    local service=$1
    local env_vars=$2

    echo "Deploying to $service environment..."

    if gcloud run deploy $service \
        --source . \
        --platform managed \
        --region us-west1 \
        --allow-unauthenticated \
        --set-env-vars="$env_vars,GOOGLE_CLOUD_PROJECT=vancouver-cbc-registration,EMAIL_PROVIDER=smtp2go,FROM_EMAIL=cbc@naturevancouver.ca" \
        --set-secrets="GOOGLE_CLIENT_ID=google-oauth-client-id:latest,GOOGLE_CLIENT_SECRET=google-oauth-client-secret:latest,SECRET_KEY=flask-secret-key:latest,SMTP2GO_USERNAME=smtp2go-username:latest,SMTP2GO_PASSWORD=smtp2go-password:latest"; then

        echo "$service deployment complete!"
        echo "URL: https://$service.naturevancouver.ca"
        echo "Logs: gcloud run services logs read $service --region=us-west1 --limit=50"
        echo ""
        return 0
    else
        echo "ERROR: Deployment failed for $service"
        return 1
    fi
}

case $DEPLOY_TARGET in
    test)
        deploy "cbc-test" "FLASK_ENV=development,TEST_MODE=true,DISPLAY_TIMEZONE=$DISPLAY_TIMEZONE"
        exit $?
        ;;
    production|registration)
        deploy "cbc-registration" "FLASK_ENV=production,DISPLAY_TIMEZONE=$DISPLAY_TIMEZONE"
        exit $?
        ;;
    both)
        deploy "cbc-test" "FLASK_ENV=development,TEST_MODE=true,DISPLAY_TIMEZONE=$DISPLAY_TIMEZONE"
        TEST_RESULT=$?
        deploy "cbc-registration" "FLASK_ENV=production,DISPLAY_TIMEZONE=$DISPLAY_TIMEZONE"
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
        echo "Usage: $0 [test|production|registration|both]"
        echo "  test        - Deploy to cbc-test only"
        echo "  production  - Deploy to cbc-registration only"
        echo "  registration- Deploy to cbc-registration only (synonym for production)"
        echo "  both        - Deploy to both environments (default)"
        exit 1
        ;;
esac
