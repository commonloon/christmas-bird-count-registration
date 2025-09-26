# Test Scenarios Data
# Updated by Claude AI on 2025-09-25

"""
Centralized test data scenarios for consistent and maintainable testing.
"""

import time
from datetime import datetime


def generate_unique_email(base="test"):
    """Generate unique email address for testing."""
    timestamp = int(time.time() * 1000)  # Millisecond precision
    return f"{base}-{timestamp}@test-functional.ca"

def generate_unique_identity(base_first="Test", base_last="User", base_email="test"):
    """Generate unique identity (first_name, last_name, email) for testing."""
    timestamp = int(time.time() * 1000)  # Millisecond precision
    return {
        'first_name': f"{base_first}{timestamp % 10000}",  # Keep names readable
        'last_name': f"{base_last}{timestamp % 10000}",
        'email': f"{base_email}-{timestamp}@test-functional.ca"
    }


# Core participant test scenarios
TEST_SCENARIOS = {
    'participants': {
        'regular_newbie': {
            'personal': {
                'first_name': 'John',
                'last_name': 'Newbie',
                'email': None,  # Will be generated dynamically
                'phone': '555-123-4567',
                'phone2': ''
            },
            'experience': {
                'skill_level': 'Newbie',
                'experience': 'None'
            },
            'participation': {
                'type': 'regular',
                'area': 'B'
            },
            'equipment': {
                'has_binoculars': False,
                'spotting_scope': False
            },
            'interests': {
                'leadership': False,
                'scribe': False
            },
            'notes': 'First time participant test',
            'expected_constraints': []
        },

        'regular_intermediate': {
            'personal': {
                'first_name': 'Jane',
                'last_name': 'Birder',
                'email': None,  # Will be generated dynamically
                'phone': '555-234-5678',
                'phone2': '555-234-5679'
            },
            'experience': {
                'skill_level': 'Intermediate',
                'experience': '1-2 counts'
            },
            'participation': {
                'type': 'regular',
                'area': 'C'
            },
            'equipment': {
                'has_binoculars': True,
                'spotting_scope': False
            },
            'interests': {
                'leadership': True,
                'scribe': False
            },
            'notes': 'Interested in leadership role',
            'expected_constraints': []
        },

        'regular_expert_leader': {
            'personal': {
                'first_name': 'Expert',
                'last_name': 'Leader',
                'email': None,  # Will be generated dynamically
                'phone': '555-345-6789',
                'phone2': ''
            },
            'experience': {
                'skill_level': 'Expert',
                'experience': '3+ counts'
            },
            'participation': {
                'type': 'regular',
                'area': 'D'
            },
            'equipment': {
                'has_binoculars': True,
                'spotting_scope': True
            },
            'interests': {
                'leadership': True,
                'scribe': False
            },
            'notes': 'Experienced participant ready to lead',
            'expected_constraints': []
        },

        'regular_scribe_interested': {
            'personal': {
                'first_name': 'Sam',
                'last_name': 'Scribe',
                'email': None,  # Will be generated dynamically
                'phone': '555-456-7890',
                'phone2': ''
            },
            'experience': {
                'skill_level': 'Beginner',
                'experience': 'None'
            },
            'participation': {
                'type': 'regular',
                'area': 'E'
            },
            'equipment': {
                'has_binoculars': True,
                'spotting_scope': False
            },
            'interests': {
                'leadership': False,
                'scribe': True
            },
            'notes': 'Interested in scribe role',
            'expected_constraints': []
        },

        'feeder_expert': {
            'personal': {
                'first_name': 'Feed',
                'last_name': 'Counter',
                'email': None,  # Will be generated dynamically
                'phone': '555-567-8901',
                'phone2': ''
            },
            'experience': {
                'skill_level': 'Expert',
                'experience': '3+ counts'
            },
            'participation': {
                'type': 'FEEDER',
                'area': 'F'  # Must be specific area, not UNASSIGNED
            },
            'equipment': {
                'has_binoculars': True,
                'spotting_scope': False
            },
            'interests': {
                'leadership': False,  # Should be disabled for FEEDER
                'scribe': False
            },
            'notes': 'Experienced feeder counter',
            'expected_constraints': ['no_unassigned', 'no_leadership']
        },

        'feeder_beginner': {
            'personal': {
                'first_name': 'Home',
                'last_name': 'Feeder',
                'email': None,  # Will be generated dynamically
                'phone': '555-678-9012',
                'phone2': ''
            },
            'experience': {
                'skill_level': 'Beginner',
                'experience': 'None'
            },
            'participation': {
                'type': 'FEEDER',
                'area': 'G'
            },
            'equipment': {
                'has_binoculars': False,
                'spotting_scope': False
            },
            'interests': {
                'leadership': False,
                'scribe': False
            },
            'notes': 'First time feeder counter',
            'expected_constraints': ['no_unassigned', 'no_leadership']
        },

        'unassigned_volunteer': {
            'personal': {
                'first_name': 'Flexible',
                'last_name': 'Volunteer',
                'email': None,  # Will be generated dynamically
                'phone': '555-789-0123',
                'phone2': ''
            },
            'experience': {
                'skill_level': 'Intermediate',
                'experience': '1-2 counts'
            },
            'participation': {
                'type': 'regular',
                'area': 'UNASSIGNED'  # "Wherever I'm needed most"
            },
            'equipment': {
                'has_binoculars': True,
                'spotting_scope': False
            },
            'interests': {
                'leadership': False,
                'scribe': True
            },
            'notes': 'Available for any area that needs help',
            'expected_constraints': []
        },

        'complete_profile': {
            'personal': {
                'first_name': 'Complete',
                'last_name': 'Profile',
                'email': None,  # Will be generated dynamically
                'phone': '555-890-1234',
                'phone2': '555-890-1235'
            },
            'experience': {
                'skill_level': 'Expert',
                'experience': '3+ counts'
            },
            'participation': {
                'type': 'regular',
                'area': 'H'
            },
            'equipment': {
                'has_binoculars': True,
                'spotting_scope': True
            },
            'interests': {
                'leadership': True,
                'scribe': True
            },
            'notes': 'Complete profile with all options selected. Long notes to test field limits and display. This person is very enthusiastic about birding and wants to help in any way possible.',
            'expected_constraints': []
        }
    },

    'form_validation': {
        'missing_required_fields': {
            'personal': {
                'first_name': '',  # Required field missing
                'last_name': 'Test',
                'email': 'invalid@test.ca',
                'phone': '',
                'phone2': ''
            },
            'experience': {
                'skill_level': '',  # Required field missing
                'experience': 'None'
            },
            'participation': {
                'type': '',  # Required field missing
                'area': 'I'
            },
            'equipment': {
                'has_binoculars': False,
                'spotting_scope': False
            },
            'interests': {
                'leadership': False,
                'scribe': False
            },
            'notes': '',
            'expected_errors': ['first_name', 'skill_level', 'participation_type']
        },

        'invalid_email_formats': [
            'invalid-email',
            'test@',
            '@test.com',
            'test..test@example.com',
            'test@.com',
            'test@com.',
            ''
        ],

        'field_length_limits': {
            'personal': {
                'first_name': 'A' * 150,  # Exceeds 100 char limit
                'last_name': 'B' * 150,   # Exceeds 100 char limit
                'email': 'test@' + 'a' * 300 + '.com',  # Exceeds 254 char limit
                'phone': '5' * 25,        # Exceeds 20 char limit
                'phone2': '4' * 25        # Exceeds 20 char limit
            },
            'notes': 'N' * 1500,  # Exceeds 1000 char limit
            'expected_errors': ['first_name', 'last_name', 'email', 'phone', 'phone2', 'notes']
        }
    },

    'admin_operations': {
        'promotion_candidate': {
            'personal': {
                'first_name': 'Promo',
                'last_name': 'Candidate',
                'email': None,  # Will be generated dynamically
                'phone': '555-111-2222',
                'phone2': ''
            },
            'experience': {
                'skill_level': 'Expert',
                'experience': '3+ counts'
            },
            'participation': {
                'type': 'regular',
                'area': 'J'
            },
            'equipment': {
                'has_binoculars': True,
                'spotting_scope': True
            },
            'interests': {
                'leadership': True,
                'scribe': False
            },
            'notes': 'Ready for leadership promotion',
            'promotion_target_area': 'J'
        },

        'reassignment_candidate': {
            'personal': {
                'first_name': 'Reassign',
                'last_name': 'Candidate',
                'email': None,  # Will be generated dynamically
                'phone': '555-222-3333',
                'phone2': ''
            },
            'experience': {
                'skill_level': 'Intermediate',
                'experience': '1-2 counts'
            },
            'participation': {
                'type': 'regular',
                'area': 'K'
            },
            'equipment': {
                'has_binoculars': True,
                'spotting_scope': False
            },
            'interests': {
                'leadership': False,
                'scribe': False
            },
            'notes': 'Available for area reassignment',
            'reassignment_target_area': 'L'
        },

        'deletion_candidate': {
            'personal': {
                'first_name': 'Delete',
                'last_name': 'Candidate',
                'email': None,  # Will be generated dynamically
                'phone': '555-333-4444',
                'phone2': ''
            },
            'experience': {
                'skill_level': 'Beginner',
                'experience': 'None'
            },
            'participation': {
                'type': 'regular',
                'area': 'M'
            },
            'equipment': {
                'has_binoculars': False,
                'spotting_scope': False
            },
            'interests': {
                'leadership': False,
                'scribe': False
            },
            'notes': 'Test participant for deletion',
            'deletion_reason': 'Test deletion workflow'
        }
    }
}


def get_test_participant(scenario_type, scenario_name, custom_overrides=None):
    """
    Get a test participant with dynamic email generation.

    Args:
        scenario_type: Type of scenario (e.g., 'participants', 'form_validation')
        scenario_name: Name of specific scenario
        custom_overrides: Dict of custom values to override defaults

    Returns:
        dict: Complete participant data with unique email
    """
    if scenario_type not in TEST_SCENARIOS:
        raise ValueError(f"Unknown scenario type: {scenario_type}")

    if scenario_name not in TEST_SCENARIOS[scenario_type]:
        raise ValueError(f"Unknown scenario name: {scenario_name} in {scenario_type}")

    # Deep copy the scenario data
    import copy
    participant_data = copy.deepcopy(TEST_SCENARIOS[scenario_type][scenario_name])

    # Generate unique email if not set
    if 'personal' in participant_data and participant_data['personal'].get('email') is None:
        base_name = f"{scenario_type}-{scenario_name}"
        participant_data['personal']['email'] = generate_unique_email(base_name)

    # Apply custom overrides
    if custom_overrides:
        _deep_update(participant_data, custom_overrides)

    return participant_data


def _deep_update(base_dict, update_dict):
    """Recursively update nested dictionary."""
    for key, value in update_dict.items():
        if isinstance(value, dict) and key in base_dict and isinstance(base_dict[key], dict):
            _deep_update(base_dict[key], value)
        else:
            base_dict[key] = value


# Predefined test datasets for batch operations
TEST_DATASETS = {
    'small_mixed': [
        'regular_newbie',
        'regular_intermediate',
        'feeder_expert',
        'unassigned_volunteer'
    ],

    'large_realistic': [
        'regular_newbie',
        'regular_intermediate',
        'regular_expert_leader',
        'regular_scribe_interested',
        'feeder_expert',
        'feeder_beginner',
        'unassigned_volunteer',
        'complete_profile'
    ] * 5,  # 40 total participants

    'leadership_focused': [
        'regular_expert_leader',
        'regular_intermediate',
        'promotion_candidate'
    ],

    'feeder_focused': [
        'feeder_expert',
        'feeder_beginner'
    ]
}


def get_test_dataset(dataset_name):
    """
    Get a complete test dataset.

    Args:
        dataset_name: Name of predefined dataset

    Returns:
        list: List of participant data dictionaries
    """
    if dataset_name not in TEST_DATASETS:
        raise ValueError(f"Unknown dataset: {dataset_name}")

    participants = []
    scenario_names = TEST_DATASETS[dataset_name]

    for i, scenario_name in enumerate(scenario_names):
        # Determine scenario type
        scenario_type = 'participants'
        if scenario_name in TEST_SCENARIOS.get('admin_operations', {}):
            scenario_type = 'admin_operations'

        # Get participant with unique identifiers
        participant = get_test_participant(scenario_type, scenario_name)

        # Make names unique for large datasets
        if scenario_names.count(scenario_name) > 1:
            participant['personal']['first_name'] += str(i + 1)
            participant['personal']['last_name'] += str(i + 1)

        participants.append(participant)

    return participants