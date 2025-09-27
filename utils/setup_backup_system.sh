#!/bin/bash
# Setup script for Firestore backup system
# Run this once to configure the backup infrastructure

set -e

PROJECT_ID="vancouver-cbc-registration"
BUCKET_NAME="vancouver-cbc-backups"
REGION="us-west1"

echo "Setting up Firestore backup system for project: $PROJECT_ID"
echo "=========================================================="

# 1. Create Cloud Storage bucket for backups
echo "1. Creating backup storage bucket..."
if gsutil ls gs://$BUCKET_NAME 2>/dev/null; then
    echo "   Bucket already exists: gs://$BUCKET_NAME"
else
    gsutil mb -p $PROJECT_ID -c STANDARD -l $REGION gs://$BUCKET_NAME
    echo "   Created bucket: gs://$BUCKET_NAME"
fi

# 2. Enable required APIs
echo "2. Enabling required Google Cloud APIs..."
gcloud services enable firestore.googleapis.com --project=$PROJECT_ID
gcloud services enable cloudfunctions.googleapis.com --project=$PROJECT_ID
gcloud services enable cloudscheduler.googleapis.com --project=$PROJECT_ID
gcloud services enable storage.googleapis.com --project=$PROJECT_ID

# 3. Set up IAM permissions
echo "3. Setting up IAM permissions..."

# Get the Cloud Run service account (used by the application)
SERVICE_ACCOUNT=$(gcloud run services describe cbc-registration --region=$REGION --format="value(spec.template.spec.serviceAccountEmail)" --project=$PROJECT_ID 2>/dev/null || echo "")

if [ -z "$SERVICE_ACCOUNT" ]; then
    echo "   Warning: Could not find Cloud Run service account"
    echo "   You may need to manually grant Firestore export permissions"
else
    echo "   Found service account: $SERVICE_ACCOUNT"

    # Grant necessary permissions
    gcloud projects add-iam-policy-binding $PROJECT_ID \
        --member="serviceAccount:$SERVICE_ACCOUNT" \
        --role="roles/datastore.importExportAdmin"

    gcloud projects add-iam-policy-binding $PROJECT_ID \
        --member="serviceAccount:$SERVICE_ACCOUNT" \
        --role="roles/storage.objectAdmin"

    echo "   Granted backup permissions to service account"
fi

# 4. Test the backup script
echo "4. Testing backup script..."
if python3 utils/backup_firestore.py --dry-run; then
    echo "   Backup script test successful"
else
    echo "   Warning: Backup script test failed - check dependencies"
fi

echo ""
echo "Setup complete! Next steps:"
echo "=========================="
echo ""
echo "Option A - Cloud Scheduler (Recommended):"
echo "  Deploy Cloud Function and set up hourly schedule"
echo "  Fully automated, serverless solution"
echo ""
echo "Option B - Cron Job:"
echo "  Add to crontab: 0 * * * * cd $PWD && python3 utils/backup_firestore.py"
echo "  Requires server with persistent cron service"
echo ""
echo "Option C - Manual:"
echo "  Run: python3 utils/backup_firestore.py"
echo "  For on-demand backups or testing"
echo ""
echo "Backup location: gs://$BUCKET_NAME"
echo "View backups: gsutil ls gs://$BUCKET_NAME/"