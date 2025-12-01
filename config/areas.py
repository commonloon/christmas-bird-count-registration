# Updated by Claude AI on 2025-11-30
# Area configuration for the application
# Note: admin_assignment_only is now managed in Firestore collection 'area_signup_type'
#       Use AreaSignupTypeModel.get_public_areas() to get areas available for public registration
AREA_CONFIG = {
    'A': {
        'name': 'North Shore Uplands - West',
        'description': 'West of the Capilano River, North of the Trans Canada Highway',
        'difficulty': 'Moderate',
        'terrain': 'Mountainous, some trails'
    },
    'B': {
        'name': 'Ambleside/West Van Coastal',
        'description': 'South of Trans Canada, West of Capilano Road, marine boundary',
        'difficulty': 'Easy',
        'terrain': 'Coastal, urban parks'
    },
    'C': {
        'name': 'North Shore Uplands - Capilano to Lynn Creek',
        'description': 'North of Trans Canada Highway between Lynn Creek and Capilano River',
        'difficulty': 'Moderate',
        'terrain': 'Forested, residential'
    },
    'D': {
        'name': 'North Vancouver East',
        'description': 'South of Trans Canada Highway, east from Capilano Rd',
        'difficulty': 'Easy',
        'terrain': 'Urban, waterfront'
    },
    'E': {
        'name': 'Seymour to Cates Park, plus uplands',
        'description': 'East from Lynn Creek, north from Burrard Inlet midpoint',
        'difficulty': 'Moderate',
        'terrain': 'Hillside residential, parks'
    },
    'F': {
        'name': 'Burnaby North',
        'description': 'East from Trans Canada, north from Lougheed to Burrard Inlet',
        'difficulty': 'Moderate',
        'terrain': 'University, conservation area'
    },
    'G': {
        'name': 'Burnaby Central',
        'description': 'Between Lougheed Highway and Kingsway, east of Boundary Road',
        'difficulty': 'Easy',
        'terrain': 'Suburban residential'
    },
    'H': {
        'name': 'Burnaby South',
        'description': 'North from Fraser River midpoint, east from Boundary Road',
        'difficulty': 'Easy',
        'terrain': 'Urban, riverfront'
    },
    'I': {
        'name': 'East Vancouver - South',
        'description': 'North from Fraser River, between Fraser Street and Boundary Road',
        'difficulty': 'Easy',
        'terrain': 'Industrial, residential'
    },
    'J': {
        'name': 'East Vancouver - Trout Lake',
        'description': 'West from Boundary Road, between Broadway and 41st Avenue',
        'difficulty': 'Easy',
        'terrain': 'Dense residential'
    },
    'K': {
        'name': 'East Vancouver - North',
        'description': 'North from Broadway, between Main Street and Boundary Road',
        'difficulty': 'Easy',
        'terrain': 'Urban, light industrial'
    },
    'L': {
        'name': 'Downtown Vancouver',
        'description': 'Downtown core plus False Creek Flats, marine boundaries',
        'difficulty': 'Easy',
        'terrain': 'Dense urban, waterfront'
    },
    'M': {
        'name': 'Cambie Corridor - QE Park/VanDusen',
        'description': 'East from Granville, between 7th Avenue and Kingsway',
        'difficulty': 'Easy',
        'terrain': 'Dense residential, transit corridor'
    },
    'N': {
        'name': 'Cambie Corridor - South',
        'description': 'South from 41st Avenue between Granville and Fraser River',
        'difficulty': 'Easy',
        'terrain': 'Suburban, some industrial'
    },
    'O': {
        'name': 'Marpole/Southlands',
        'description': 'South from 33rd between Granville and Camosun to Fraser River',
        'difficulty': 'Easy',
        'terrain': 'Residential, airport vicinity'
    },
    'P': {
        'name': 'Kitsilano/Jericho',
        'description': 'Central Vancouver, marine boundary considerations',
        'difficulty': 'Easy',
        'terrain': 'Dense residential, beaches'
    },
    'Q': {
        'name': 'UBC North',
        'description': 'West from Blanca, north from W 16th Avenue, marine boundaries',
        'difficulty': 'Moderate',
        'terrain': 'Beaches, parks, residential'
    },
    'R': {
        'name': 'UBC South/Musqueam',
        'description': 'University and endowment lands, Musqueam territory',
        'difficulty': 'Moderate',
        'terrain': 'University campus, forest, beach'
    },
    'S': {
        'name': 'Iona',
        'description': 'South shore areas with marine boundaries',
        'difficulty': 'Moderate',
        'terrain': 'Riverfront, mixed development'
    },
    'T': {
        'name': 'Airport and surrounds',
        'description': 'Vancouver International Airport and surrounds',
        'difficulty': 'Easy',
        'terrain': 'Airport and surrounds'
    },
    'U': {
        'name': 'Northwest Richmond',
        'description': 'Central Richmond areas',
        'difficulty': 'Easy',
        'terrain': 'Suburban, agricultural'
    },
    'V': {
        'name': 'Northeast Richmond',
        'description': 'Richmond east of Number 5 Road, river counting coordination needed',
        'difficulty': 'Easy',
        'terrain': 'Agricultural, bog areas'
    },
    'W': {
        'name': 'Stanley Park West',
        'description': 'Stanley Park and surrounding marine areas',
        'difficulty': 'Easy',
        'terrain': 'Urban park, seawall, beaches'
    },
    'X': {
        'name': 'Stanley Park East',
        'description': 'North and east from Stanley Park Causeway, marine boundaries',
        'difficulty': 'Easy',
        'terrain': 'Urban waterfront, marinas'
    },
    'Y': {
        'name': 'Burrard Inlet/English Bay',
        'description': 'This area is counted from one or more boats',
        'difficulty': 'Moderate',
        'terrain': 'Marine, boat-based counting'
    }
}

def get_area_info(letter_code):
    """Get configuration info for a specific area."""
    return AREA_CONFIG.get(letter_code.upper(), {
        'name': f'Area {letter_code}',
        'description': 'Area description not available',
        'difficulty': 'Unknown',
        'terrain': 'Unknown'
    })

def get_all_areas():
    """Get list of all available area codes."""
    return sorted(AREA_CONFIG.keys())
