# Updated by Claude AI on 2025-09-12
# Area configuration for the application
AREA_CONFIG = {
    'A': {
        'name': 'Area A - North Shore Uplands - West',
        'description': 'West of the Capilano River, North of the Trans Canada Highway',
        'difficulty': 'Moderate',
        'terrain': 'Mountainous, some trails',
        'admin_assignment_only': False
    },
    'B': {
        'name': 'Area B - Ambleside/West Van Coastal',
        'description': 'South of Trans Canada, West of Capilano Road, marine boundary',
        'difficulty': 'Easy',
        'terrain': 'Coastal, urban parks',
        'admin_assignment_only': False
    },
    'C': {
        'name': 'Area C - North Shore Uplands - Capilano to Lynn Creek',
        'description': 'North of Trans Canada Highway between Lynn Creek and Capilano River',
        'difficulty': 'Moderate',
        'terrain': 'Forested, residential',
        'admin_assignment_only': False
    },
    'D': {
        'name': 'Area D - North Vancouver East',
        'description': 'South of Trans Canada Highway, east from Capilano Rd',
        'difficulty': 'Easy',
        'terrain': 'Urban, waterfront',
        'admin_assignment_only': False
    },
    'E': {
        'name': 'Area E - Seymour to Cates Park, plus uplands',
        'description': 'East from Lynn Creek, north from Burrard Inlet midpoint',
        'difficulty': 'Moderate',
        'terrain': 'Hillside residential, parks',
        'admin_assignment_only': False
    },
    'F': {
        'name': 'Area F - Burnaby North',
        'description': 'East from Trans Canada, north from Lougheed to Burrard Inlet',
        'difficulty': 'Moderate',
        'terrain': 'University, conservation area',
        'admin_assignment_only': False
    },
    'G': {
        'name': 'Area G - Burnaby Central',
        'description': 'Between Lougheed Highway and Kingsway, east of Boundary Road',
        'difficulty': 'Easy',
        'terrain': 'Suburban residential',
        'admin_assignment_only': False
    },
    'H': {
        'name': 'Area H - Burnaby South',
        'description': 'North from Fraser River midpoint, east from Boundary Road',
        'difficulty': 'Easy',
        'terrain': 'Urban, riverfront',
        'admin_assignment_only': False
    },
    'I': {
        'name': 'Area I - East Vancouver - South',
        'description': 'North from Fraser River, between Fraser Street and Boundary Road',
        'difficulty': 'Easy',
        'terrain': 'Industrial, residential',
        'admin_assignment_only': False
    },
    'J': {
        'name': 'Area J - East Vancouver - Trout Lake',
        'description': 'West from Boundary Road, between Broadway and 41st Avenue',
        'difficulty': 'Easy',
        'terrain': 'Dense residential',
        'admin_assignment_only': False
    },
    'K': {
        'name': 'Area K - East Vancouver - North',
        'description': 'North from Broadway, between Main Street and Boundary Road',
        'difficulty': 'Easy',
        'terrain': 'Urban, light industrial',
        'admin_assignment_only': False
    },
    'L': {
        'name': 'Area L - Downtown Vancouver',
        'description': 'Downtown core plus False Creek Flats, marine boundaries',
        'difficulty': 'Easy',
        'terrain': 'Dense urban, waterfront',
        'admin_assignment_only': False
    },
    'M': {
        'name': 'Area M - Cambie Corridor - QE Park/VanDusen',
        'description': 'East from Granville, between 7th Avenue and Kingsway',
        'difficulty': 'Easy',
        'terrain': 'Dense residential, transit corridor',
        'admin_assignment_only': False
    },
    'N': {
        'name': 'Area N - Cambie Corridor - South',
        'description': 'South from 41st Avenue between Granville and Fraser River',
        'difficulty': 'Easy',
        'terrain': 'Suburban, some industrial',
        'admin_assignment_only': False
    },
    'O': {
        'name': 'Area O - Marpole/Southlands',
        'description': 'South from 33rd between Granville and Camosun to Fraser River',
        'difficulty': 'Easy',
        'terrain': 'Residential, airport vicinity',
        'admin_assignment_only': False
    },
    'P': {
        'name': 'Area P - Kitsilano/Jericho',
        'description': 'Central Vancouver, marine boundary considerations',
        'difficulty': 'Easy',
        'terrain': 'Dense residential, beaches',
        'admin_assignment_only': False
    },
    'Q': {
        'name': 'Area Q - UBC North',
        'description': 'West from Blanca, north from W 16th Avenue, marine boundaries',
        'difficulty': 'Moderate',
        'terrain': 'Beaches, parks, residential',
        'admin_assignment_only': False
    },
    'R': {
        'name': 'Area R - UBC South/Musqueam',
        'description': 'University and endowment lands, Musqueam territory',
        'difficulty': 'Moderate',
        'terrain': 'University campus, forest, beach',
        'admin_assignment_only': False
    },
    'S': {
        'name': 'Area S - Iona',
        'description': 'South shore areas with marine boundaries',
        'difficulty': 'Moderate',
        'terrain': 'Riverfront, mixed development',
        'admin_assignment_only': False
    },
    'T': {
        'name': 'Area T - Airport and surrounds',
        'description': 'Vancouver International Airport and surrounds',
        'difficulty': 'Easy',
        'terrain': 'Airport and surrounds',
        'admin_assignment_only': True
    },
    'U': {
        'name': 'Area U - Northwest Richmond',
        'description': 'Central Richmond areas',
        'difficulty': 'Easy',
        'terrain': 'Suburban, agricultural',
        'admin_assignment_only': False
    },
    'V': {
        'name': 'Area V - Northeast Richmond',
        'description': 'Richmond east of Number 5 Road, river counting coordination needed',
        'difficulty': 'Easy',
        'terrain': 'Agricultural, bog areas',
        'admin_assignment_only': False
    },
    'W': {
        'name': 'Area W - Stanley Park West',
        'description': 'Stanley Park and surrounding marine areas',
        'difficulty': 'Easy',
        'terrain': 'Urban park, seawall, beaches',
        'admin_assignment_only': False
    },
    'X': {
        'name': 'Area X - Stanley Park East',
        'description': 'North and east from Stanley Park Causeway, marine boundaries',
        'difficulty': 'Easy',
        'terrain': 'Urban waterfront, marinas',
        'admin_assignment_only': False
    },
    'Y': {
        'name': 'Area Y - Burrard Inlet/English Bay',
        'description': 'This area is counted from one or more boats',
        'difficulty': 'Moderate',
        'terrain': 'Marine, boat-based counting',
        'admin_assignment_only': True
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

def get_public_areas():
    """Get list of area codes available for public registration (excludes admin-only areas)."""
    return sorted([code for code, config in AREA_CONFIG.items() 
                   if not config.get('admin_assignment_only', False)])