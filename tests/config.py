# Test Configuration for Christmas Bird Count Registration System
# Updated by Claude AI on 2025-09-22

"""
Test configuration for functional testing against cloud environments.
Credentials are stored in Google Secret Manager for security.
"""

import os
from datetime import datetime

# Environment Configuration
TEST_CONFIG = {
    # Target URLs for testing
    'test_url': 'https://cbc-test.naturevancouver.ca',
    'production_url': 'https://cbc-registration.naturevancouver.ca',

    # Database names
    'test_database': 'cbc-test',
    'production_database': 'cbc-register',

    # Year strategy
    'current_year': datetime.now().year,
    'isolation_test_year': 2000,  # For historical/isolation testing

    # Network resilience settings
    'retry_attempts': 3,
    'retry_delay_base': 2,  # seconds, for exponential backoff
    'request_timeout': 30,  # seconds for web requests
    'page_load_timeout': 30,  # seconds for page loads
    'oauth_timeout': 60,  # seconds for OAuth flow completion

    # Browser configuration
    'browser': 'chrome',
    'headless': True,  # Set to False for debugging
    'window_size': (1920, 1080),

    # Test data configuration
    'small_dataset_size': 50,  # participants
    'large_dataset_size': 350,  # realistic production scale
    'leader_coverage_percent': 40,  # percentage of areas with leaders

    # Rate limiting considerations
    'batch_size': 10,  # for test data creation to stay under rate limits
    'batch_delay': 2,  # seconds between batches
}

# Test Account Configuration
# Account usernames only - passwords stored in Google Secret Manager
TEST_ACCOUNTS = {
    'admin_primary': {
        'email': 'cbc-test-admin1@naturevancouver.ca',
        'secret_name': 'test-admin1-password',
        'role': 'admin',
        'description': 'Primary admin account for testing'
    },
    'admin_secondary': {
        'email': 'cbc-test-admin2@naturevancouver.ca',
        'secret_name': 'test-admin2-password',
        'role': 'admin',
        'description': 'Secondary admin account for concurrent testing'
    },
    'leader': {
        'email': 'cbc-test-leader1@naturevancouver.ca',
        'secret_name': 'test-leader1-password',
        'role': 'leader',
        'description': 'Area leader account for leader interface testing'
    }
}

# Google Cloud Configuration
GCP_CONFIG = {
    'project_id': 'vancouver-cbc-registration',
    'region': 'us-west1',
    'secret_manager_enabled': True
}

# Test Environment Detection
def get_target_environment():
    """Determine which environment to test against based on settings."""
    return os.getenv('TEST_TARGET', 'test')  # 'test' or 'production'

def get_base_url():
    """Get the base URL for the target test environment."""
    env = get_target_environment()
    if env == 'production':
        return TEST_CONFIG['production_url']
    return TEST_CONFIG['test_url']

def get_database_name():
    """Get the database name for the target test environment."""
    env = get_target_environment()
    if env == 'production':
        return TEST_CONFIG['production_database']
    return TEST_CONFIG['test_database']

# Test Data Paths
TEST_DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
DATASET_CONFIG_DIR = os.path.join(TEST_DATA_DIR, 'datasets')
EXPECTED_RESULTS_DIR = os.path.join(TEST_DATA_DIR, 'expected')

# Logging Configuration
LOGGING_CONFIG = {
    'level': 'INFO',
    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    'handlers': ['console', 'file'],
    'log_file': 'tests.log'
}

# Test Categories
TEST_CATEGORIES = {
    'critical': ['registration', 'data_consistency', 'authentication'],
    'admin': ['admin_operations', 'csv_export', 'participant_management'],
    'security': ['input_sanitization', 'csrf_protection', 'race_conditions'],
    'edge_cases': ['error_handling', 'empty_database', 'large_datasets']
}

# Validation Rules
VALIDATION_RULES = {
    'csv_export': {
        'required_headers': [
            'first_name', 'last_name', 'email', 'phone', 'preferred_area',
            'skill_level', 'experience', 'participation_type', 'has_binoculars',
            'spotting_scope', 'notes_to_organizers', 'interested_in_leadership',
            'interested_in_scribe', 'created_at', 'year'
        ],
        'sort_order': ['preferred_area', 'participation_type', 'first_name'],
        'max_export_time': 30  # seconds for large datasets
    },
    'form_validation': {
        'required_fields': ['first_name', 'last_name', 'email', 'phone'],
        'email_format': r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
        'phone_format': r'^[\d\s\-\(\)\+]{10,20}$'
    }
}