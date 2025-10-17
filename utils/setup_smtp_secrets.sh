#!/bin/bash
# Setup SMTP2GO secrets for email functionality
# This script prompts for SMTP2GO credentials and stores them in Google Secret Manager
#
# The application currently uses SMTP2GO for email delivery.
# Secret names: smtp2go-username, smtp2go-password
#
# For SMTP2GO credentials, sign up at https://www.smtp2go.com

set -e  # Exit on error

echo "=== SMTP2GO Secret Manager Setup ==="
echo ""
echo "This script will create secrets for SMTP2GO email functionality."
echo "You'll need SMTP2GO credentials from https://www.smtp2go.com"
echo ""

# Check if secrets already exist
if gcloud secrets describe smtp2go-username &>/dev/null; then
    echo "WARNING: smtp2go-username secret already exists."
    read -p "Do you want to update it? (y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Skipping smtp2go-username"
        SKIP_USERNAME=true
    fi
fi

if gcloud secrets describe smtp2go-password &>/dev/null; then
    echo "WARNING: smtp2go-password secret already exists."
    read -p "Do you want to update it? (y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Skipping smtp2go-password"
        SKIP_PASSWORD=true
    fi
fi

# Prompt for username if needed
if [ "$SKIP_USERNAME" != "true" ]; then
    echo ""
    read -p "Enter SMTP2GO username: " SMTP_USERNAME

    if [ -z "$SMTP_USERNAME" ]; then
        echo "ERROR: SMTP2GO username cannot be empty"
        exit 1
    fi

    echo -n "$SMTP_USERNAME" | gcloud secrets create smtp2go-username --data-file=- 2>/dev/null || \
        echo -n "$SMTP_USERNAME" | gcloud secrets versions add smtp2go-username --data-file=-

    echo "✓ SMTP2GO username stored in Secret Manager"
fi

# Prompt for password if needed
if [ "$SKIP_PASSWORD" != "true" ]; then
    echo ""
    read -s -p "Enter SMTP2GO password: " SMTP_PASSWORD
    echo

    if [ -z "$SMTP_PASSWORD" ]; then
        echo "ERROR: SMTP2GO password cannot be empty"
        exit 1
    fi

    echo -n "$SMTP_PASSWORD" | gcloud secrets create smtp2go-password --data-file=- 2>/dev/null || \
        echo -n "$SMTP_PASSWORD" | gcloud secrets versions add smtp2go-password --data-file=-

    echo "✓ SMTP2GO password stored in Secret Manager"
fi

echo ""
echo "=== SMTP2GO Secrets Setup Complete ==="
echo ""
echo "Secrets created:"
gcloud secrets list --filter="name:smtp2go"
