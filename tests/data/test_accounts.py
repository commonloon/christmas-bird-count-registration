# Test Account Configuration
# Updated by Claude AI on 2025-09-25

"""
Test account credentials and configuration for authentication testing.
"""

# Test account information
TEST_ACCOUNTS = {
    'admin1': {
        'email': 'cbc-test-admin1@naturevancouver.ca',
        'password_secret': 'test-admin1-password',
        'role': 'admin',
        'description': 'Primary admin test account'
    },

    'admin2': {
        'email': 'cbc-test-admin2@naturevancouver.ca',
        'password_secret': 'test-admin2-password',
        'role': 'admin',
        'description': 'Secondary admin test account for concurrent testing'
    },

    'leader1': {
        'email': 'cbc-test-leader1@naturevancouver.ca',
        'password_secret': 'test-leader1-password',
        'role': 'leader',
        'description': 'Area leader test account',
        'assigned_areas': ['A']  # Will be assigned area A for testing
    }
}


def get_test_account(account_name):
    """
    Get test account information.

    Args:
        account_name: Name of test account

    Returns:
        dict: Account information
    """
    if account_name not in TEST_ACCOUNTS:
        raise ValueError(f"Unknown test account: {account_name}")

    return TEST_ACCOUNTS[account_name].copy()


def get_test_password(account_name):
    """
    Get test account password from Google Secret Manager.

    Args:
        account_name: Name of test account

    Returns:
        str: Account password

    Raises:
        Exception: If password cannot be retrieved
    """
    try:
        from google.cloud import secretmanager

        account = get_test_account(account_name)
        secret_name = account['password_secret']

        client = secretmanager.SecretManagerServiceClient()
        project_id = "vancouver-cbc-registration"
        name = f"projects/{project_id}/secrets/{secret_name}/versions/latest"

        response = client.access_secret_version(request={"name": name})
        password = response.payload.data.decode("UTF-8").strip()

        return password

    except Exception as e:
        raise Exception(f"Could not retrieve password for {account_name}: {e}")


def get_all_test_accounts():
    """
    Get all available test accounts.

    Returns:
        dict: All test account information
    """
    return TEST_ACCOUNTS.copy()