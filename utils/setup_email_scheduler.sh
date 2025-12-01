#!/bin/bash
# Updated by Claude AI on 2025-10-26
#
# Setup Google Cloud Scheduler jobs for automated email delivery
#
# Usage:
#   ./utils/setup_email_scheduler.sh test        # Create jobs for test environment
#   ./utils/setup_email_scheduler.sh production  # Create jobs for production environment
#   ./utils/setup_email_scheduler.sh both        # Create jobs for both environments

set -e

# Get configuration from config/cloud.py and config/organization.py
PROJECT_ID=$(python -c "import sys; sys.path.insert(0, '.'); from config.cloud import GCP_PROJECT_ID; print(GCP_PROJECT_ID)" 2>/dev/null || echo "")
REGION=$(python -c "import sys; sys.path.insert(0, '.'); from config.cloud import GCP_LOCATION; print(GCP_LOCATION)" 2>/dev/null || echo "us-west1")
SERVICE_ACCOUNT="cloud-scheduler-invoker@${PROJECT_ID}.iam.gserviceaccount.com"
TIMEZONE=$(python -c "import sys; sys.path.insert(0, '.'); from config.organization import DISPLAY_TIMEZONE; print(DISPLAY_TIMEZONE)" 2>/dev/null || echo "America/Vancouver")
TEST_SERVICE=$(python -c "import sys; sys.path.insert(0, '.'); from config.cloud import TEST_SERVICE, BASE_DOMAIN; print(f'https://{TEST_SERVICE}.{BASE_DOMAIN}')" 2>/dev/null || echo "")
PROD_SERVICE=$(python -c "import sys; sys.path.insert(0, '.'); from config.cloud import PRODUCTION_SERVICE, BASE_DOMAIN; print(f'https://{PRODUCTION_SERVICE}.{BASE_DOMAIN}')" 2>/dev/null || echo "")

# Validate configuration
if [ -z "$PROJECT_ID" ] || [ -z "$TEST_SERVICE" ] || [ -z "$PROD_SERVICE" ]; then
    echo "ERROR: Failed to load configuration from config/cloud.py"
    echo "Make sure config/cloud.py exists and is properly formatted"
    exit 1
fi

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Print loaded configuration
print_config() {
    echo ""
    print_info "Loaded Configuration:"
    echo "  Project ID: ${PROJECT_ID}"
    echo "  Region: ${REGION}"
    echo "  Service Account: ${SERVICE_ACCOUNT}"
    echo "  Timezone: ${TIMEZONE}"
    echo "  Test Service URL: ${TEST_SERVICE}"
    echo "  Prod Service URL: ${PROD_SERVICE}"
    echo ""
}

# Function to create scheduler jobs for an environment
create_scheduler_jobs() {
    local ENV=$1
    local SERVICE_URL=$2

    print_info "Creating Cloud Scheduler jobs for $ENV environment..."
    print_info "Service URL: $SERVICE_URL"
    print_info "Timezone: $TIMEZONE"

    # Job 1: Twice-daily team updates (6am and 6pm)
    print_info "Creating team updates job (6am)..."
    gcloud scheduler jobs create http "cbc-${ENV}-team-updates-morning" \
        --location=${REGION} \
        --schedule="0 6 * * *" \
        --time-zone="${TIMEZONE}" \
        --uri="${SERVICE_URL}/scheduler/trigger-team-updates" \
        --http-method=POST \
        --oidc-service-account-email="${SERVICE_ACCOUNT}" \
        --oidc-token-audience="${SERVICE_URL}" \
        --attempt-deadline=540s \
        --max-retry-attempts=3 \
        --description="Send twice-daily team update emails to area leaders (morning)" \
        --project=${PROJECT_ID} \
        2>&1 | grep -v "already exists" || print_warning "Job may already exist"

    print_info "Creating team updates job (6pm)..."
    gcloud scheduler jobs create http "cbc-${ENV}-team-updates-afternoon" \
        --location=${REGION} \
        --schedule="0 18 * * *" \
        --time-zone="${TIMEZONE}" \
        --uri="${SERVICE_URL}/scheduler/trigger-team-updates" \
        --http-method=POST \
        --oidc-service-account-email="${SERVICE_ACCOUNT}" \
        --oidc-token-audience="${SERVICE_URL}" \
        --attempt-deadline=540s \
        --max-retry-attempts=3 \
        --description="Send twice-daily team update emails to area leaders (afternoon)" \
        --project=${PROJECT_ID} \
        2>&1 | grep -v "already exists" || print_warning "Job may already exist"

    # Job 2: Weekly summaries (Fridays at 11pm)
    print_info "Creating weekly summaries job (Fridays 11pm)..."
    gcloud scheduler jobs create http "cbc-${ENV}-weekly-summaries" \
        --location=${REGION} \
        --schedule="0 23 * * 5" \
        --time-zone="${TIMEZONE}" \
        --uri="${SERVICE_URL}/scheduler/trigger-weekly-summaries" \
        --http-method=POST \
        --oidc-service-account-email="${SERVICE_ACCOUNT}" \
        --oidc-token-audience="${SERVICE_URL}" \
        --attempt-deadline=540s \
        --max-retry-attempts=3 \
        --description="Send weekly summary emails to area leaders (Fridays 11pm)" \
        --project=${PROJECT_ID} \
        2>&1 | grep -v "already exists" || print_warning "Job may already exist"

    # Job 3: Daily admin digest (6pm)
    print_info "Creating admin digest job (6pm)..."
    gcloud scheduler jobs create http "cbc-${ENV}-admin-digest" \
        --location=${REGION} \
        --schedule="0 18 * * *" \
        --time-zone="${TIMEZONE}" \
        --uri="${SERVICE_URL}/scheduler/trigger-admin-digest" \
        --http-method=POST \
        --oidc-service-account-email="${SERVICE_ACCOUNT}" \
        --oidc-token-audience="${SERVICE_URL}" \
        --attempt-deadline=540s \
        --max-retry-attempts=3 \
        --description="Send daily admin digest for unassigned participants (6pm)" \
        --project=${PROJECT_ID} \
        2>&1 | grep -v "already exists" || print_warning "Job may already exist"

    print_info "Scheduler jobs created for $ENV environment!"
}

# Function to list existing jobs
list_jobs() {
    print_info "Listing existing Cloud Scheduler jobs..."
    gcloud scheduler jobs list --location=${REGION} --project=${PROJECT_ID} | grep "cbc-" || print_warning "No CBC scheduler jobs found"
}

# Function to delete all jobs for an environment
delete_jobs() {
    local ENV=$1

    print_warning "Deleting Cloud Scheduler jobs for $ENV environment..."

    gcloud scheduler jobs delete "cbc-${ENV}-team-updates-morning" --location=${REGION} --project=${PROJECT_ID} --quiet 2>/dev/null || true
    gcloud scheduler jobs delete "cbc-${ENV}-team-updates-afternoon" --location=${REGION} --project=${PROJECT_ID} --quiet 2>/dev/null || true
    gcloud scheduler jobs delete "cbc-${ENV}-weekly-summaries" --location=${REGION} --project=${PROJECT_ID} --quiet 2>/dev/null || true
    gcloud scheduler jobs delete "cbc-${ENV}-admin-digest" --location=${REGION} --project=${PROJECT_ID} --quiet 2>/dev/null || true

    print_info "Jobs deleted for $ENV environment"
}

# Main script logic
COMMAND=${1:-both}

# Show configuration before proceeding
print_config

case $COMMAND in
    test)
        print_info "Setting up Cloud Scheduler for TEST environment only"
        create_scheduler_jobs "test" "${TEST_SERVICE}"
        ;;
    production)
        print_info "Setting up Cloud Scheduler for PRODUCTION environment only"
        create_scheduler_jobs "prod" "${PROD_SERVICE}"
        ;;
    both)
        print_info "Setting up Cloud Scheduler for BOTH environments"
        create_scheduler_jobs "test" "${TEST_SERVICE}"
        create_scheduler_jobs "prod" "${PROD_SERVICE}"
        ;;
    list)
        list_jobs
        ;;
    delete-test)
        delete_jobs "test"
        ;;
    delete-prod)
        delete_jobs "prod"
        ;;
    delete-all)
        delete_jobs "test"
        delete_jobs "prod"
        ;;
    *)
        print_error "Invalid command: $COMMAND"
        echo ""
        echo "Usage: $0 [test|production|both|list|delete-test|delete-prod|delete-all]"
        echo ""
        echo "Commands:"
        echo "  test          - Create scheduler jobs for test environment"
        echo "  production    - Create scheduler jobs for production environment"
        echo "  both          - Create scheduler jobs for both environments (default)"
        echo "  list          - List existing scheduler jobs"
        echo "  delete-test   - Delete all test environment jobs"
        echo "  delete-prod   - Delete all production environment jobs"
        echo "  delete-all    - Delete all CBC scheduler jobs"
        exit 1
        ;;
esac

print_info "Done!"
print_info ""
print_info "To verify the jobs were created, run:"
print_info "  gcloud scheduler jobs list --location=${REGION} --project=${PROJECT_ID}"
print_info ""
print_info "To manually trigger a job for testing, run:"
print_info "  gcloud scheduler jobs run cbc-test-team-updates-morning --location=${REGION} --project=${PROJECT_ID}"
