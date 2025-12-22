# Updated by Claude AI on 2025-12-22
# Area configuration for Nanaimo Christmas Bird Count
# Note: admin_assignment_only is now managed in Firestore collection 'area_signup_type'
#       Use AreaSignupTypeModel.get_public_areas() to get areas available for public registration

AREA_CONFIG = {
    '1': {
        'name': 'North Coast',
        'description': 'Area 1 North Coast',
        'difficulty': 'Moderate',
        'terrain': 'Coastal'
    },
    '2': {
        'name': 'Brannen Lake',
        'description': 'Area 2 Brannen Lake',
        'difficulty': 'Easy',
        'terrain': 'Lake, wetland'
    },
    '3': {
        'name': 'North Nanaimo',
        'description': 'Area 3 North Nanaimo',
        'difficulty': 'Moderate',
        'terrain': 'Mixed'
    },
    '4A': {
        'name': 'Stephenson Point',
        'description': 'Area 4A Stephenson Point',
        'difficulty': 'Easy',
        'terrain': 'Coastal'
    },
    '4B': {
        'name': '- Departure Bay',
        'description': 'Area 4B - Departure Bay',
        'difficulty': 'Easy',
        'terrain': 'Coastal, urban'
    },
    '5': {
        'name': 'East Wellington',
        'description': 'Area 5 East Wellington',
        'difficulty': 'Easy',
        'terrain': 'Suburban, residential'
    },
    '6': {
        'name': 'Buttertubs',
        'description': 'Area 6 Buttertubs',
        'difficulty': 'Easy',
        'terrain': 'Urban park, marsh'
    },
    '7': {
        'name': 'Downtown',
        'description': 'Area 7 Downtown',
        'difficulty': 'Easy',
        'terrain': 'Urban, waterfront'
    },
    '8': {
        'name': 'Newcastle Island',
        'description': 'Area 8 Newcastle Island',
        'difficulty': 'Moderate',
        'terrain': 'Island, provincial marine park'
    },
    '9A': {
        'name': 'Mid-Nanaimo Harbour',
        'description': 'Area 9A Mid-Nanaimo Harbour',
        'difficulty': 'Moderate',
        'terrain': 'Marine, requires boat'
    },
    '9B': {
        'name': 'Northumberland Channel',
        'description': 'Area 9B Northumberland Channel',
        'difficulty': 'Moderate',
        'terrain': 'Mixed'
    },
    '9C': {
        'name': 'Departure Bay & Outer Islets',
        'description': 'Area 9C Departure Bay & Outer Islets',
        'difficulty': 'Moderate',
        'terrain': 'Marine, requires boat'
    },
    '10': {
        'name': 'Gabriola Island',
        'description': 'Area 10 Gabriola Island',
        'difficulty': 'Moderate',
        'terrain': 'Island, requires ferry'
    },
    '11': {
        'name': 'Nanaimo River Estuary',
        'description': 'Area 11 Nanaimo River Estuary',
        'difficulty': 'Moderate',
        'terrain': 'Estuary, wetland'
    },
    '12': {
        'name': 'Cable Bay tp Boat Harbour',
        'description': 'Area 12 Cable Bay to Boat Harbour',
        'difficulty': 'Moderate',
        'terrain': 'Coastal'
    },
    '13': {
        'name': 'Cedar',
        'description': 'Area 13 Cedar',
        'difficulty': 'Easy',
        'terrain': 'Rural, residential'
    },
    '14': {
        'name': 'Cinnebar & S. Wellington',
        'description': 'Area 14 Cinnabar & S. Wellington',
        'difficulty': 'Easy',
        'terrain': 'Suburban, wetland'
    },
    '15': {
        'name': 'Nanaimo River_Morden Colliery',
        'description': 'Area 15 Nanaimo River/Morden Colliery',
        'difficulty': 'Moderate',
        'terrain': 'River, historical site'
    },
    '16': {
        'name': 'Mt. Benson',
        'description': 'Area 16 Mt. Benson',
        'difficulty': 'Difficult',
        'terrain': 'Mountainous, forested'
    },
    '17': {
        'name': 'Harewood Plains',
        'description': 'Area 17 Harewood Plains',
        'difficulty': 'Easy',
        'terrain': 'Urban, plains'
    },
    '18': {
        'name': 'Westwood Lake',
        'description': 'Area 18 Westwood Lake',
        'difficulty': 'Easy',
        'terrain': 'Lake, park'
    },
    '19': {
        'name': 'Protection Island',
        'description': 'Area 19 Protection Island',
        'difficulty': 'Moderate',
        'terrain': 'Island, requires boat'
    },
    '20': {
        'name': 'Mudge Island',
        'description': 'Area 20 Mudge Island',
        'difficulty': 'Moderate',
        'terrain': 'Island, requires boat'
    },
}

def get_area_info(letter_code):
    """Get configuration info for a specific area.

    Args:
        letter_code: Area code (e.g., '1', '4A', '16')

    Returns:
        Dictionary with area configuration, or empty dict if not found
    """
    return AREA_CONFIG.get(letter_code, {})


def get_all_areas():
    """Return list of all configured area codes.

    Returns:
        List of area codes as strings
    """
    return list(AREA_CONFIG.keys())
