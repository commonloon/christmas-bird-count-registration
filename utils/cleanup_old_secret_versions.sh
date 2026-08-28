#!/bin/bash

# Configuration: Your specific bird count projects
PROJECTS=("comox-spring" "ladner-cbc" "nanaimo-cbc" "vancouver-cbc-registration")

DRY_RUN=false

# Improved Argument Parsing
while [[ $# -gt 0 ]]; do
  case $1 in
    -d|--dry-run)
      DRY_RUN=true
      shift # move to next argument
      ;;
    -h|--help)
      echo "Usage: ./cleanup_secrets.sh [options]"
      echo "Options:"
      echo "  -d, --dry-run    Show which versions would be destroyed without acting."
      echo "  -h, --help       Show this help message."
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

if [ "$DRY_RUN" = true ]; then
  echo ">>> DRY RUN MODE: No secrets will be destroyed. <<<"
else
  echo ">>> ACTION MODE: Old secret versions will be PERMANENTLY destroyed. <<<"
fi

for PROJECT in "${PROJECTS[@]}"; do
  echo ""
  echo "========================================================"
  echo " PROJECT: $PROJECT"
  echo "========================================================"

  # Set project context and suppress 'Updated property' message
  gcloud config set project "$PROJECT" &> /dev/null

  # Get all secret names in the project
  SECRETS=$(gcloud secrets list --format="value(name)")

  if [ -z "$SECRETS" ]; then
    echo " [!] No secrets found in $PROJECT."
    continue
  fi

  for SECRET in $SECRETS; do
    SECRET_ID=$(basename "$SECRET")
    echo " Secret: $SECRET_ID"

    # Identify versions that are ENABLED or DISABLED (not already DESTROYED)
    # The filter 'state=ENABLED OR state=DISABLED' avoids previous syntax errors.
    OLD_VERSIONS=$(gcloud secrets versions list "$SECRET_ID" \
      --filter="state=ENABLED OR state=DISABLED" \
      --format="value(name.basename())" \
      --sort-by="~created" | tail -n +2)

    if [ -z "$OLD_VERSIONS" ]; then
      echo "   -> Only one version exists. Keeping it."
    else
      for VERSION in $OLD_VERSIONS; do
        if [ "$DRY_RUN" = true ]; then
          echo "   [DRY RUN] Would destroy version: $VERSION"
        else
          echo "   [ACTION] Destroying version: $VERSION"
          gcloud secrets versions destroy "$VERSION" --secret="$SECRET_ID" -q
        fi
      done
      echo "   -> Latest version will be kept (not listed above)."
    fi
  done
done

echo ""
echo "========================================================"
echo " Process complete."
echo "========================================================"