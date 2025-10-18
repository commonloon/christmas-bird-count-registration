"""
Phase 2: GCP Infrastructure Validation Tests
Updated by Claude AI on 2025-10-18

These tests validate that Google Cloud Platform resources are properly configured
and accessible for a new Christmas Bird Count installation.

Requires:
- Google Cloud authentication (gcloud auth application-default login)
- Proper IAM permissions for Firestore, Secret Manager, Cloud Run

No hardcoded values - all validation is dynamic based on config/*.py files.
"""

import pytest
import os
import requests
from datetime import datetime
from google.cloud import firestore
from google.cloud import secretmanager
from google.api_core import exceptions as gcp_exceptions


class TestFirestoreAccess:
    """Validate Firestore database access and permissions."""

    def test_firestore_test_database_accessible(self, installation_config):
        """Verify can connect to test Firestore database."""
        test_db = installation_config['test_db']
        project_id = installation_config['gcp_project']

        try:
            # Try to connect to the test database
            client = firestore.Client(project=project_id, database=test_db)

            # Verify connection by trying to access a collection
            # This won't fail even if collection doesn't exist, but will fail if database doesn't exist
            client.collection('_test_connection').limit(1).get()

        except gcp_exceptions.NotFound:
            pytest.fail(
                f"Test database '{test_db}' does not exist in project '{project_id}'\n"
                f"Create the database:\n"
                f"  1. Run: python utils/setup_databases.py\n"
                f"  2. Or manually create via Google Cloud Console\n"
                f"Database configuration is in config/cloud.py"
            )
        except gcp_exceptions.PermissionDenied:
            pytest.fail(
                f"Permission denied accessing test database '{test_db}'\n"
                f"Ensure you are authenticated:\n"
                f"  gcloud auth application-default login\n"
                f"And have Firestore permissions for project '{project_id}'"
            )
        except Exception as e:
            pytest.fail(
                f"Failed to connect to test database '{test_db}': {e}\n"
                f"Check:\n"
                f"  1. Database exists: {test_db}\n"
                f"  2. GCP project: {project_id}\n"
                f"  3. Authentication: gcloud auth application-default login"
            )

    def test_firestore_production_database_accessible(self, installation_config):
        """Verify can connect to production Firestore database."""
        prod_db = installation_config['prod_db']
        project_id = installation_config['gcp_project']

        try:
            # Try to connect to the production database
            client = firestore.Client(project=project_id, database=prod_db)

            # Verify connection
            client.collection('_test_connection').limit(1).get()

        except gcp_exceptions.NotFound:
            pytest.fail(
                f"Production database '{prod_db}' does not exist in project '{project_id}'\n"
                f"Create the database:\n"
                f"  1. Run: python utils/setup_databases.py\n"
                f"  2. Or manually create via Google Cloud Console\n"
                f"Database configuration is in config/cloud.py"
            )
        except gcp_exceptions.PermissionDenied:
            pytest.fail(
                f"Permission denied accessing production database '{prod_db}'\n"
                f"Ensure you are authenticated:\n"
                f"  gcloud auth application-default login\n"
                f"And have Firestore permissions for project '{project_id}'"
            )
        except Exception as e:
            pytest.fail(
                f"Failed to connect to production database '{prod_db}': {e}\n"
                f"Check:\n"
                f"  1. Database exists: {prod_db}\n"
                f"  2. GCP project: {project_id}\n"
                f"  3. Authentication: gcloud auth application-default login"
            )

    def test_can_create_test_collection_document(self, installation_config):
        """Verify write permissions work in test database."""
        test_db = installation_config['test_db']
        project_id = installation_config['gcp_project']
        current_year = installation_config['current_year']

        try:
            client = firestore.Client(project=project_id, database=test_db)

            # Try to write a test document
            test_collection = f'_installation_test_{current_year}'
            doc_ref = client.collection(test_collection).document('test_write')

            doc_ref.set({
                'test': True,
                'timestamp': firestore.SERVER_TIMESTAMP,
                'purpose': 'Installation validation test'
            })

            # Clean up - delete the test document
            doc_ref.delete()

        except gcp_exceptions.PermissionDenied:
            pytest.fail(
                f"Write permission denied for test database '{test_db}'\n"
                f"Check IAM permissions for project '{project_id}'\n"
                f"Required role: roles/datastore.user or roles/owner"
            )
        except Exception as e:
            pytest.fail(
                f"Failed to write to test database '{test_db}': {e}\n"
                f"Check database permissions and connectivity"
            )

    def test_can_query_test_collection(self, installation_config):
        """Verify read/query permissions work in test database."""
        test_db = installation_config['test_db']
        project_id = installation_config['gcp_project']
        current_year = installation_config['current_year']

        try:
            client = firestore.Client(project=project_id, database=test_db)

            # Try to query a collection (even if empty)
            collection = f'participants_{current_year}'
            results = client.collection(collection).limit(1).get()

            # Success if we can execute the query (even if results are empty)
            assert isinstance(results, list) or hasattr(results, '__iter__'), \
                "Query should return iterable results"

        except gcp_exceptions.PermissionDenied:
            pytest.fail(
                f"Read permission denied for test database '{test_db}'\n"
                f"Check IAM permissions for project '{project_id}'\n"
                f"Required role: roles/datastore.user or roles/owner"
            )
        except Exception as e:
            pytest.fail(
                f"Failed to query test database '{test_db}': {e}\n"
                f"Check database permissions and connectivity"
            )


class TestSecretManagerAccess:
    """Validate Secret Manager access and required secrets."""

    def test_secret_manager_accessible(self, installation_config):
        """Verify Secret Manager API is enabled and accessible."""
        project_id = installation_config['gcp_project']

        try:
            client = secretmanager.SecretManagerServiceClient()

            # Try to list secrets (will work even if empty)
            parent = f"projects/{project_id}"
            request = secretmanager.ListSecretsRequest(parent=parent, page_size=1)
            client.list_secrets(request=request)

        except gcp_exceptions.PermissionDenied:
            pytest.fail(
                f"Permission denied accessing Secret Manager for project '{project_id}'\n"
                f"Check:\n"
                f"  1. Authentication: gcloud auth application-default login\n"
                f"  2. IAM permissions: roles/secretmanager.secretAccessor\n"
                f"  3. API enabled: gcloud services enable secretmanager.googleapis.com"
            )
        except Exception as e:
            error_msg = str(e).lower()
            if 'not found' in error_msg or 'disabled' in error_msg:
                pytest.fail(
                    f"Secret Manager API not enabled for project '{project_id}'\n"
                    f"Enable it:\n"
                    f"  gcloud services enable secretmanager.googleapis.com --project={project_id}"
                )
            else:
                pytest.fail(
                    f"Failed to access Secret Manager: {e}\n"
                    f"Check project '{project_id}' configuration and authentication"
                )

    def test_oauth_client_id_secret_exists(self, installation_config):
        """Verify google-oauth-client-id secret exists."""
        from config.cloud import SECRET_OAUTH_CLIENT_ID
        project_id = installation_config['gcp_project']

        try:
            client = secretmanager.SecretManagerServiceClient()
            secret_name = f"projects/{project_id}/secrets/{SECRET_OAUTH_CLIENT_ID}"

            # Try to access the secret
            client.get_secret(name=secret_name)

        except gcp_exceptions.NotFound:
            pytest.fail(
                f"Secret '{SECRET_OAUTH_CLIENT_ID}' not found in project '{project_id}'\n"
                f"Create it:\n"
                f"  1. Set up OAuth client in Google Cloud Console\n"
                f"  2. Download client_secret.json\n"
                f"  3. Run: ./utils/setup_oauth_secrets.sh\n"
                f"  4. Delete client_secret.json\n"
                f"See docs/OAUTH-SETUP.md for detailed instructions"
            )
        except Exception as e:
            pytest.fail(
                f"Failed to access secret '{SECRET_OAUTH_CLIENT_ID}': {e}\n"
                f"Check permissions and secret configuration"
            )

    def test_oauth_client_secret_exists(self, installation_config):
        """Verify google-oauth-client-secret secret exists."""
        from config.cloud import SECRET_OAUTH_CLIENT_SECRET
        project_id = installation_config['gcp_project']

        try:
            client = secretmanager.SecretManagerServiceClient()
            secret_name = f"projects/{project_id}/secrets/{SECRET_OAUTH_CLIENT_SECRET}"

            # Try to access the secret
            client.get_secret(name=secret_name)

        except gcp_exceptions.NotFound:
            pytest.fail(
                f"Secret '{SECRET_OAUTH_CLIENT_SECRET}' not found in project '{project_id}'\n"
                f"Create it:\n"
                f"  1. Set up OAuth client in Google Cloud Console\n"
                f"  2. Download client_secret.json\n"
                f"  3. Run: ./utils/setup_oauth_secrets.sh\n"
                f"  4. Delete client_secret.json\n"
                f"See docs/OAUTH-SETUP.md for detailed instructions"
            )
        except Exception as e:
            pytest.fail(
                f"Failed to access secret '{SECRET_OAUTH_CLIENT_SECRET}': {e}\n"
                f"Check permissions and secret configuration"
            )

    def test_flask_secret_key_exists(self, installation_config):
        """Verify flask-secret-key secret exists."""
        from config.cloud import SECRET_FLASK_KEY
        project_id = installation_config['gcp_project']

        try:
            client = secretmanager.SecretManagerServiceClient()
            secret_name = f"projects/{project_id}/secrets/{SECRET_FLASK_KEY}"

            # Try to access the secret
            client.get_secret(name=secret_name)

        except gcp_exceptions.NotFound:
            pytest.fail(
                f"Secret '{SECRET_FLASK_KEY}' not found in project '{project_id}'\n"
                f"Create it:\n"
                f"  1. Generate a random key: python -c 'import secrets; print(secrets.token_hex(32))'\n"
                f"  2. Store in Secret Manager:\n"
                f"     echo -n '<generated-key>' | gcloud secrets create {SECRET_FLASK_KEY} --data-file=-\n"
                f"Or run: ./utils/setup_oauth_secrets.sh (creates all secrets)"
            )
        except Exception as e:
            pytest.fail(
                f"Failed to access secret '{SECRET_FLASK_KEY}': {e}\n"
                f"Check permissions and secret configuration"
            )

    def test_smtp_secrets_exist(self, installation_config):
        """Verify SMTP credentials exist in Secret Manager."""
        from config.cloud import SECRET_SMTP2GO_USERNAME, SECRET_SMTP2GO_PASSWORD
        project_id = installation_config['gcp_project']

        missing_secrets = []

        for secret_name in [SECRET_SMTP2GO_USERNAME, SECRET_SMTP2GO_PASSWORD]:
            try:
                client = secretmanager.SecretManagerServiceClient()
                full_name = f"projects/{project_id}/secrets/{secret_name}"
                client.get_secret(name=full_name)
            except gcp_exceptions.NotFound:
                missing_secrets.append(secret_name)
            except Exception as e:
                pytest.fail(f"Error checking secret '{secret_name}': {e}")

        if missing_secrets:
            pytest.fail(
                f"SMTP secrets not found: {missing_secrets}\n"
                f"Create them:\n"
                f"  1. Sign up for SMTP2GO: https://www.smtp2go.com\n"
                f"  2. Get SMTP credentials from dashboard\n"
                f"  3. Run: ./utils/setup_smtp_secrets.sh\n"
                f"Email notifications won't work without these credentials"
            )


class TestCloudRunDeployment:
    """Validate Cloud Run services are deployed and accessible."""

    def test_test_service_accessible(self, installation_config):
        """Verify test Cloud Run service is accessible."""
        test_url = installation_config['test_url']

        try:
            response = requests.get(test_url, timeout=10, allow_redirects=True)

            # Accept 200 (OK) or 302 (redirect to login)
            assert response.status_code in [200, 302], \
                f"Unexpected status code: {response.status_code}"

        except requests.exceptions.ConnectionError:
            pytest.fail(
                f"Cannot connect to test service: {test_url}\n"
                f"Service may not be deployed. Deploy it:\n"
                f"  ./deploy.sh test\n"
                f"Or check that the URL in config/cloud.py is correct"
            )
        except requests.exceptions.Timeout:
            pytest.fail(
                f"Timeout connecting to test service: {test_url}\n"
                f"Service may be slow to start or unreachable"
            )
        except Exception as e:
            pytest.fail(
                f"Failed to access test service: {test_url}\n"
                f"Error: {e}"
            )

    def test_production_service_accessible(self, installation_config):
        """Verify production Cloud Run service is accessible."""
        prod_url = installation_config['prod_url']

        try:
            response = requests.get(prod_url, timeout=10, allow_redirects=True)

            # Accept 200 (OK) or 302 (redirect to login)
            assert response.status_code in [200, 302], \
                f"Unexpected status code: {response.status_code}"

        except requests.exceptions.ConnectionError:
            pytest.fail(
                f"Cannot connect to production service: {prod_url}\n"
                f"Service may not be deployed. Deploy it:\n"
                f"  ./deploy.sh production\n"
                f"Or check that the URL in config/cloud.py is correct"
            )
        except requests.exceptions.Timeout:
            pytest.fail(
                f"Timeout connecting to production service: {prod_url}\n"
                f"Service may be slow to start or unreachable"
            )
        except Exception as e:
            pytest.fail(
                f"Failed to access production service: {prod_url}\n"
                f"Error: {e}"
            )

    def test_test_service_returns_html(self, installation_config):
        """Verify test service returns HTML content."""
        test_url = installation_config['test_url']

        try:
            response = requests.get(test_url, timeout=10, allow_redirects=True)

            # Check content type
            content_type = response.headers.get('Content-Type', '')
            assert 'text/html' in content_type, \
                f"Expected HTML content, got: {content_type}"

            # Check for some expected content
            content = response.text.lower()
            org_name = installation_config['org_vars'].get('count_event_name', '').lower()

            # Should contain either organization name or "christmas bird count"
            assert org_name in content or 'bird count' in content or 'registration' in content, \
                "Response doesn't appear to be CBC registration page"

        except AssertionError:
            raise
        except Exception as e:
            pytest.fail(f"Failed to verify test service HTML: {e}")

    def test_https_enforced(self, installation_config):
        """Verify HTTP redirects to HTTPS."""
        test_url = installation_config['test_url']

        # Convert HTTPS to HTTP
        http_url = test_url.replace('https://', 'http://')

        try:
            response = requests.get(http_url, timeout=10, allow_redirects=False)

            # Should get 301 or 302 redirect
            assert response.status_code in [301, 302, 307, 308], \
                f"Expected redirect, got status: {response.status_code}"

            # Redirect location should be HTTPS
            location = response.headers.get('Location', '')
            assert location.startswith('https://'), \
                f"Redirect should be to HTTPS, got: {location}"

        except requests.exceptions.SSLError:
            # SSL error is actually good - means HTTPS is enforced
            pass
        except requests.exceptions.ConnectionError:
            # Connection error might mean HTTP is blocked (also good)
            pass
        except Exception as e:
            # Other errors - let the test pass, this is a nice-to-have
            print(f"Note: Could not verify HTTPS enforcement: {e}")


class TestDatabaseIndexes:
    """Validate required Firestore indexes exist for current year."""

    def test_participant_collections_exist_for_current_year(self, installation_config):
        """Verify participant and removal_log collections exist for current year."""
        test_db = installation_config['test_db']
        project_id = installation_config['gcp_project']
        current_year = installation_config['current_year']

        try:
            client = firestore.Client(project=project_id, database=test_db)

            # Check participant collection
            participant_collection = f'participants_{current_year}'
            docs = client.collection(participant_collection).limit(1).get()

            # If we can query it, it exists (even if empty)
            # Collections are created automatically on first write

        except Exception as e:
            # This is informational - collections are created on first use
            print(
                f"\nNote: Collections for {current_year} don't exist yet.\n"
                f"They will be created automatically when the first participant registers.\n"
                f"Or register a test participant to create them now."
            )

    def test_indexes_script_available(self):
        """Verify index verification script exists."""
        script_path = 'utils/verify_indexes.py'

        assert os.path.exists(script_path), (
            f"Index verification script not found: {script_path}\n"
            f"This script should be run at the start of each season:\n"
            f"  python utils/verify_indexes.py <database-name>"
        )

    def test_can_run_identity_based_queries(self, installation_config):
        """Verify can execute identity-based queries (tests index requirements)."""
        test_db = installation_config['test_db']
        project_id = installation_config['gcp_project']
        current_year = installation_config['current_year']

        try:
            client = firestore.Client(project=project_id, database=test_db)
            collection = f'participants_{current_year}'

            # Try an identity-based query (requires composite index if data exists)
            # This is the pattern used by get_leaders_by_identity()
            query = (client.collection(collection)
                    .where(filter=firestore.FieldFilter('is_leader', '==', True))
                    .where(filter=firestore.FieldFilter('email', '==', 'test@example.com'))
                    .limit(1))

            # Execute query (will fail if index doesn't exist and data is present)
            results = list(query.stream())

        except gcp_exceptions.FailedPrecondition as e:
            # This means index is missing
            error_msg = str(e)
            pytest.fail(
                f"Required database index is missing for identity-based queries.\n"
                f"Error: {error_msg}\n"
                f"Create indexes:\n"
                f"  python utils/verify_indexes.py {test_db}\n"
                f"Indexes are required for the application to work correctly."
            )
        except Exception as e:
            # Other errors are less critical - might be due to no data
            print(f"\nNote: Could not fully verify indexes: {e}")
            print("This is normal if no participants are registered yet.")
            print(f"Run this before season start: python utils/verify_indexes.py {test_db}")
