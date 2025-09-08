#!/bin/bash

# OAuth Secrets Setup Script for Christmas Bird Count Registration
# This script extracts OAuth credentials from client_secret.json and stores them in Google Secret Manager
# Use Git Bash to run from Windows
set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Setting up OAuth secrets for CBC Registration...${NC}"

# Check if client_secret.json exists
if [ ! -f "client_secret.json" ]; then
    echo -e "${RED}Error: client_secret.json not found in current directory${NC}"
    echo "Please download the OAuth client credentials from Google Cloud Console"
    echo "and save as 'client_secret.json' in this directory."
    exit 1
fi

# Check if we can parse JSON (try jq first, fallback to Python)
JSON_PARSER=""
if command -v jq &> /dev/null; then
    JSON_PARSER="jq"
elif command -v python &> /dev/null; then
    JSON_PARSER="python"
elif command -v python3 &> /dev/null; then
    JSON_PARSER="python3"
else
    echo -e "${RED}Error: Need either jq or Python to parse JSON${NC}"
    echo "jq not found, and Python not available in PATH"
    echo "For Git Bash on Windows, Python is usually available as 'python' or 'python3'"
    exit 1
fi

echo "Using $JSON_PARSER to parse JSON..."

# Check if gcloud is authenticated
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | head -n1 > /dev/null; then
    echo -e "${RED}Error: No active gcloud authentication found${NC}"
    echo "Please run: gcloud auth login"
    exit 1
fi

# Get current project
PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
if [ -z "$PROJECT_ID" ]; then
    echo -e "${RED}Error: No project set in gcloud config${NC}"
    echo "Please run: gcloud config set project YOUR_PROJECT_ID"
    exit 1
fi

echo -e "${YELLOW}Using project: $PROJECT_ID${NC}"

# Parse client_secret.json
echo "Parsing OAuth credentials from client_secret.json..."

if [ "$JSON_PARSER" = "jq" ]; then
    CLIENT_ID=$(jq -r '.web.client_id' client_secret.json)
    CLIENT_SECRET=$(jq -r '.web.client_secret' client_secret.json)
else
    # Use Python to parse JSON
    CLIENT_ID=$($JSON_PARSER -c "import json; f=open('client_secret.json'); data=json.load(f); print(data['web']['client_id']); f.close()" 2>/dev/null)
    CLIENT_SECRET=$($JSON_PARSER -c "import json; f=open('client_secret.json'); data=json.load(f); print(data['web']['client_secret']); f.close()" 2>/dev/null)
fi

# Validate extracted values
if [ "$CLIENT_ID" = "null" ] || [ -z "$CLIENT_ID" ]; then
    echo -e "${RED}Error: Could not extract client_id from client_secret.json${NC}"
    echo "Please ensure the file is a valid OAuth client credentials file"
    exit 1
fi

if [ "$CLIENT_SECRET" = "null" ] || [ -z "$CLIENT_SECRET" ]; then
    echo -e "${RED}Error: Could not extract client_secret from client_secret.json${NC}"
    echo "Please ensure the file is a valid OAuth client credentials file"
    exit 1
fi

echo -e "${GREEN}✓ Successfully extracted OAuth credentials${NC}"
echo "Client ID: ${CLIENT_ID:0:20}..."

# Generate a secure random secret key
echo "Generating Flask secret key..."
FLASK_SECRET=$(openssl rand -base64 32)

# Create secrets in Secret Manager
echo "Creating secrets in Google Secret Manager..."

# Function to create or update secret
create_or_update_secret() {
    local secret_name=$1
    local secret_value=$2

    if gcloud secrets describe "$secret_name" &>/dev/null; then
        echo "Updating existing secret: $secret_name"
        echo "$secret_value" | gcloud secrets versions add "$secret_name" --data-file=-
    else
        echo "Creating new secret: $secret_name"
        echo "$secret_value" | gcloud secrets create "$secret_name" --data-file=-
    fi
}

# Create/update the secrets
create_or_update_secret "google-oauth-client-id" "$CLIENT_ID"
create_or_update_secret "google-oauth-client-secret" "$CLIENT_SECRET"
create_or_update_secret "flask-secret-key" "$FLASK_SECRET"

echo -e "${GREEN}✓ Secrets created successfully${NC}"

# Grant Cloud Run service account access to secrets
echo "Granting Cloud Run access to secrets..."

PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format="value(projectNumber)")
SERVICE_ACCOUNT="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

echo "Service account: $SERVICE_ACCOUNT"

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:$SERVICE_ACCOUNT" \
    --role="roles/secretmanager.secretAccessor" \
    --quiet

echo -e "${GREEN}✓ IAM permissions granted${NC}"

# Verify secrets were created
echo "Verifying secrets..."
for secret in "google-oauth-client-id" "google-oauth-client-secret" "flask-secret-key"; do
    if gcloud secrets describe "$secret" &>/dev/null; then
        echo -e "${GREEN}✓ $secret${NC}"
    else
        echo -e "${RED}✗ $secret${NC}"
    fi
done

echo ""
echo -e "${GREEN}OAuth setup complete!${NC}"
echo ""
echo "Next steps:"
echo "1. Ensure your OAuth client (Web application) has these configured:"
echo "   - Authorized JavaScript origins:"
echo "     * https://cbc-test.naturevancouver.ca" 
echo "     * https://cbc-registration.naturevancouver.ca"
echo "   - Authorized redirect URIs: NONE (leave empty for Google Identity Services)"
echo ""
echo "2. Deploy your services with:"
echo "   ./deploy.sh test"
echo "   ./deploy.sh production"
echo ""
echo -e "${YELLOW}Remember: Keep client_secret.json secure and don't commit it to version control!${NC}"
echo -e "${YELLOW}Delete client_secret.json after running this script.${NC}"