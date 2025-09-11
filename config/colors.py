# Color palette definitions for the Christmas Bird Count Registration system
# Based on the 20 distinct colors from https://sashamaps.net/docs/resources/20-colors/
# These colors are chosen for maximum distinctness and 99.99% accessibility

DISTINCT_COLOURS = {
    'red': '#e6194b',
    'green': '#3cb44b', 
    'yellow': '#ffe119',
    'blue': '#4363d8',
    'orange': '#f58231',
    'purple': '#911eb4',
    'cyan': '#46f0f0',
    'magenta': '#f032e6',
    'lime': '#bcf60c',
    'pink': '#fabebe',
    'teal': '#008080',
    'lavender': '#e6beff',
    'brown': '#9a6324',
    'beige': '#fffac8',
    'maroon': '#800000',
    'mint': '#aaffc3',
    'olive': '#808000',
    'apricot': '#ffd8b1',
    'navy': '#000075',
    'grey': '#808080',
    # Bonus colors
    'white': '#ffffff',
    'black': '#000000'
}

# Map color scheme for registration counts (99.99% accessibility palette)
MAP_COLORS = {
    'low_count': DISTINCT_COLOURS['orange'],      # 0-3 registered
    'med_count': DISTINCT_COLOURS['maroon'],      # 4-8 registered  
    'high_count': DISTINCT_COLOURS['navy'],       # 8+ registered
    'selected': DISTINCT_COLOURS['yellow']        # Yellow for selected area
}