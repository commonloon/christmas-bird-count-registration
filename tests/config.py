# Test Configuration for Christmas Bird Count Registration System
# Updated by Claude AI on 2025-09-25

"""
Test configuration for functional workflow testing against cloud environments.
Updated for maintainable functional test suite with page object model.
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
    'browser': 'firefox',  # Primary browser - better OAuth stability than Chrome
    'headless': True,  # Set to False for debugging OAuth flows
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

# Test Categories - Updated for functional workflow testing
TEST_CATEGORIES = {
    'critical': ['registration_workflows', 'admin_dashboard', 'csv_export'],
    'admin': ['participant_management', 'leader_management', 'data_operations'],
    'security': ['input_sanitization', 'csrf_protection', 'authentication'],
    'workflow': ['form_validation', 'navigation', 'data_preservation'],
    'performance': ['large_datasets', 'export_performance', 'page_load_times']
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

# Identity-Based Testing Configuration
IDENTITY_TEST_CONFIG = {
    # Family email scenarios for comprehensive testing
    'family_scenarios': [
        {
            'email': 'smith-family@test-scenarios.ca',
            'description': 'Two-member family with one leader',
            'members': [
                {
                    'first_name': 'John',
                    'last_name': 'Smith',
                    'area': 'A',
                    'role': 'leader',
                    'skill_level': 'Expert',
                    'interested_in_leadership': True
                },
                {
                    'first_name': 'Jane',
                    'last_name': 'Smith',
                    'area': 'B',
                    'role': 'participant',
                    'skill_level': 'Intermediate',
                    'interested_in_leadership': False
                }
            ]
        },
        {
            'email': 'johnson-family@test-scenarios.ca',
            'description': 'Three-member family with multiple leaders',
            'members': [
                {
                    'first_name': 'Bob',
                    'last_name': 'Johnson',
                    'area': 'C',
                    'role': 'leader',
                    'skill_level': 'Expert',
                    'interested_in_leadership': True
                },
                {
                    'first_name': 'Alice',
                    'last_name': 'Johnson',
                    'area': 'D',
                    'role': 'leader',
                    'skill_level': 'Intermediate',
                    'interested_in_leadership': True
                },
                {
                    'first_name': 'Charlie',
                    'last_name': 'Johnson',
                    'area': 'E',
                    'role': 'participant',
                    'skill_level': 'Beginner',
                    'interested_in_leadership': False
                }
            ]
        }
    ],

    # Operations to test for identity-based validation
    'test_operations': [
        'create_participant',
        'promote_to_leader',
        'delete_participant',
        'delete_leader',
        'verify_synchronization',
        'check_isolation'
    ],

    # Identity validation rules
    'identity_rules': {
        'tuple_fields': ['first_name', 'last_name', 'email'],
        'case_sensitivity': False,  # Identity matching is case-insensitive
        'whitespace_handling': 'strip',  # Strip whitespace from all fields
        'duplicate_prevention': 'identity_based',  # Not email-only
        'synchronization_required': True,
        'isolation_required': True  # Operations on one family member don't affect others
    },

    # Test data generation settings
    'test_data': {
        'base_email_domain': 'test-identity.ca',
        'phone_prefix': '555-TEST',
        'default_skill_level': 'Intermediate',
        'default_experience': '1-2 counts',
        'default_participation_type': 'regular',
        'cleanup_pattern': 'test-'  # Pattern for identifying test records to cleanup
    },

    # Expected synchronization behaviors
    'synchronization_expectations': {
        'participant_deletion': {
            'should_deactivate_leader': True,
            'should_preserve_other_family_members': True,
            'should_log_operation': True
        },
        'leader_deletion': {
            'should_reset_participant_flag': True,
            'should_preserve_other_family_members': True,
            'should_log_operation': True
        },
        'duplicate_prevention': {
            'same_identity_different_area': 'prevent',
            'different_identity_same_email': 'allow',
            'validation_method': 'identity_tuple'
        }
    }
}

# Test Categories - Enhanced with identity testing
TEST_CATEGORIES = {
    'critical': ['registration', 'data_consistency', 'authentication', 'identity_synchronization'],
    'admin': ['admin_operations', 'csv_export', 'participant_management', 'leader_management'],
    'security': ['input_sanitization', 'csrf_protection', 'race_conditions'],
    'edge_cases': ['error_handling', 'empty_database', 'large_datasets'],
    'identity': ['family_email_scenarios', 'identity_based_operations', 'synchronization_validation']
}