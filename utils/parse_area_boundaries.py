# utils/parse_area_boundaries.py
# Updated by Claude AI on 2026-08-31
#
# One-off CLI wrapper for converting a KML export into the legacy
# static/data/area_boundaries_<slug>.json + config/areas.py file format.
# The actual KML-parsing logic lives in services/kml_import.py (reused by
# the /bigbird/circles/<slug>/areas KML-upload route, which writes directly
# to the circle_areas.boundary_geojson DB column instead of these files) -
# this script is kept only for local/offline inspection of a KML export.
#
# Usage:
#   python parse_area_boundaries.py input.kml
#   python parse_area_boundaries.py input.kml --output custom_output.json
#
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.kml_import import (  # noqa: E402
    parse_kml_string, calculate_map_center_and_bounds, filter_main_areas, KmlParseError
)


def parse_kml_file(kml_file_path):
    """Read a KML file from disk and parse it via services.kml_import.parse_kml_string."""
    with open(kml_file_path, 'r', encoding='utf-8') as file:
        kml_content = file.read()
    return parse_kml_string(kml_content)


def estimate_max_participants(area_code, description):
    """
    Estimate maximum participants for each area based on size and complexity.
    These can be adjusted by administrators later.
    """
    # Default values based on typical CBC area sizes (letter codes)
    defaults = {
        'A': 15, 'B': 12, 'C': 15, 'D': 12, 'E': 18, 'F': 16,
        'G': 14, 'H': 12, 'I': 10, 'J': 12, 'K': 14, 'L': 8,
        'M': 12, 'N': 10, 'O': 12, 'P': 14, 'Q': 16, 'R': 14,
        'S': 18, 'T': 16, 'U': 14, 'V': 12, 'W': 10, 'X': 8
    }

    # Check if it's in the defaults dictionary
    if area_code in defaults:
        return defaults[area_code]

    # For numeric codes or unknown codes, return default
    return 12


def save_areas_to_json(areas, output_path):
    """
    Save parsed area data to JSON file for use by web application.
    Includes map configuration (center, bounds, zoom) calculated from area coordinates.
    """
    # Calculate map configuration
    map_config = calculate_map_center_and_bounds(areas)

    # Create output structure with metadata
    output_data = {
        'map_config': map_config,
        'areas': areas
    }

    with open(output_path, 'w', encoding='utf-8') as file:
        json.dump(output_data, file, indent=2, ensure_ascii=False)

    print(f"Saved {len(areas)} areas to {output_path}")
    print(f"Map center: {map_config['center']}")
    print(f"Map bounds: {map_config['bounds']}")
    print(f"Suggested zoom: {map_config['zoom']}")


def generate_area_summary(areas):
    """
    Generate summary statistics about the parsed areas.
    """
    total_max = sum(area['max_participants'] for area in areas)

    print(f"\nArea Summary:")
    print(f"Total areas: {len(areas)}")
    print(f"Total maximum participants: {total_max}")
    print(f"Average max per area: {total_max / len(areas):.1f}")

    print(f"\nAreas by code:")
    for area in areas:
        coord_count = len(area['geometry']['coordinates'][0])
        print(f"  {area['letter_code']}: {area['name']} "
              f"(max: {area['max_participants']}, {coord_count} boundary points)")


def generate_areas_config_file(areas, output_path):
    """
    Generate a Python configuration file for config/areas.py.
    Creates AREA_CONFIG dictionary with area metadata.
    """
    from datetime import datetime

    lines = [
        "# Updated by Claude AI on " + datetime.now().strftime('%Y-%m-%d'),
        "# Area configuration - generated from KML parsing",
        "# Copy this content to config/areas.py or use as reference",
        "AREA_CONFIG = {"
    ]

    for area in areas:
        code = area['letter_code']
        name = area['name']
        description = area.get('description', '')

        # Try to infer difficulty and terrain from name/description
        # These are defaults and should be reviewed/customized
        difficulty = 'Easy'  # Default
        terrain = 'Mixed terrain'  # Default

        # Basic heuristics for terrain/difficulty
        name_lower = name.lower()
        if 'mountain' in name_lower or 'hill' in name_lower:
            difficulty = 'Moderate'
            terrain = 'Mountainous, trails'
        elif 'marsh' in name_lower or 'wetland' in name_lower or 'bog' in name_lower:
            difficulty = 'Moderate'
            terrain = 'Wetland, marshes'
        elif 'island' in name_lower:
            terrain = 'Island, agricultural'
        elif 'coast' in name_lower or 'beach' in name_lower or 'shore' in name_lower:
            terrain = 'Coastal, beaches'
        elif 'urban' in name_lower or 'downtown' in name_lower or 'city' in name_lower:
            terrain = 'Urban, residential'
        elif 'farm' in name_lower or 'agricultural' in name_lower:
            terrain = 'Agricultural, rural'
        elif 'richmond' in name_lower or 'delta' in name_lower or 'ladner' in name_lower:
            terrain = 'Suburban, agricultural'

        lines.append(f"    '{code}': {{")
        lines.append(f"        'name': '{name}',")
        lines.append(f"        'description': '{description}',")
        lines.append(f"        'difficulty': '{difficulty}',")
        lines.append(f"        'terrain': '{terrain}',")
        lines.append(f"        'admin_assignment_only': False")
        lines.append(f"    }},")

    lines.append("}")
    lines.append("")
    lines.append("")
    lines.append("def get_area_info(letter_code):")
    lines.append('    """Get configuration info for a specific area."""')
    lines.append("    return AREA_CONFIG.get(letter_code.upper(), {")
    lines.append("        'name': f'Area {letter_code}',")
    lines.append("        'description': 'Area description not available',")
    lines.append("        'difficulty': 'Unknown',")
    lines.append("        'terrain': 'Unknown'")
    lines.append("    })")
    lines.append("")
    lines.append("")
    lines.append("def get_all_areas():")
    lines.append('    """Get list of all available area codes."""')
    lines.append("    return sorted(AREA_CONFIG.keys())")
    lines.append("")
    lines.append("")
    lines.append("def get_public_areas():")
    lines.append('    """Get list of area codes available for public registration (excludes admin-only areas)."""')
    lines.append("    return sorted([code for code, config in AREA_CONFIG.items()")
    lines.append("                   if not config.get('admin_assignment_only', False)])")
    lines.append("")

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    print(f"\nGenerated Python config: {output_path}")
    print("NOTE: Review and customize the 'difficulty' and 'terrain' values as needed.")


# Main execution script for one-time KML parsing
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Parse KML file and convert area boundaries to GeoJSON format with map configuration',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python parse_area_boundaries.py "Vancouver CBC Areas.kml"
  python parse_area_boundaries.py "Ladner CBC with Area Zones.kml"
  python parse_area_boundaries.py "Fraser Estuary KBA eBird Survey.kml" --output kba_boundaries.json
  python parse_area_boundaries.py input.kml -o ../static/data/area_boundaries.json
        """
    )

    parser.add_argument(
        'kml_file',
        help='Path to the KML file containing area boundaries'
    )

    parser.add_argument(
        '-o', '--output',
        default='../static/data/area_boundaries.json',
        help='Output JSON file path (default: ../static/data/area_boundaries.json)'
    )

    args = parser.parse_args()

    try:
        # Validate input file exists
        if not os.path.exists(args.kml_file):
            print(f"Error: KML file not found: {args.kml_file}")
            print("Please check the file path and try again.")
            sys.exit(1)

        print(f"Parsing KML file: {args.kml_file}")
        print(f"Output will be saved to: {args.output}")
        print()

        # Create output directory if it doesn't exist
        output_dir = os.path.dirname(args.output)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
            print(f"Created directory: {output_dir}")

        # Parse and save
        all_areas = parse_kml_file(args.kml_file)

        # Filter to main areas only (exclude sub-areas with hyphens like B-1, C-2)
        original_count = len(all_areas)
        areas = filter_main_areas(all_areas)
        filtered_count = original_count - len(areas)

        if filtered_count > 0:
            print(f"Filtered out {filtered_count} sub-areas (keeping {len(areas)} main areas only)")
            print()

        if not areas:
            print("\nWarning: No main areas found (all areas were sub-areas).")
            print("If you need sub-areas, modify the filtering logic in the script.")
            sys.exit(1)

        # This CLI's output format still carries max_participants (config/areas.py's
        # legacy shape) even though the live app has no capacity limits and the
        # DB-backed KML-upload route doesn't set it.
        for area in areas:
            area['max_participants'] = estimate_max_participants(area['letter_code'], area['description'])

        # Generate both JSON and Python config files
        save_areas_to_json(areas, args.output)

        # Generate Python config file alongside JSON
        config_output = args.output.replace('.json', '_areas.py')
        generate_areas_config_file(areas, config_output)

        generate_area_summary(areas)

        print(f"\n{'='*60}")
        print("SUCCESS! Generated files:")
        print(f"{'='*60}")
        print(f"1. Map boundaries (JSON):  {args.output}")
        print(f"   -> Copy to: static/data/area_boundaries.json")
        print()
        print(f"2. Area configuration (Python):  {config_output}")
        print(f"   -> Review/customize difficulty and terrain values")
        print(f"   -> Copy to: config/areas.py")
        print(f"{'='*60}")
        sys.exit(0)

    except FileNotFoundError as e:
        print(f"File error: {e}")
        sys.exit(1)
    except KmlParseError as e:
        print(f"Error parsing KML file: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)